"""Tool-using legal agent (OpenAI-compatible function calling)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent
from agents.tools import TOOL_SPECS, Workspace, calculate
from common.config import price
from common.llm import chat
from memory.store import render_memory
from wake.trajectory import Trajectory

SYSTEM_PROMPT = """You are a senior associate at Harbour International Chambers, a law firm. You complete one piece of legal work for a supervising partner.

You work inside a matter workspace using tools:
- list_documents / read_document / search_documents to review the matter documents;
- calculate for arithmetic and date computations;
- write_draft / edit_draft / read_draft to produce the deliverable (Markdown);
- finish to submit.

Work like a careful lawyer: read the documents before you write, base every statement on the documents, and do not invent facts. The deliverable is whatever is in the draft when you call finish, so make sure the draft is complete. You have a limited number of steps; do not end without a complete draft."""

BUDGET_MSG = ("You have reached your work budget. If the draft is not complete, call write_draft now with the complete "
              "final deliverable; then call finish.")


class LegalAgent(BaseAgent):
    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.mcfg = cfg["models"]["agent"]
        a = cfg["agent"]
        self.max_steps = int(a.get("max_steps", 30))
        self.max_input_tokens = int(a.get("max_input_tokens", 0) or 0)
        self.max_tokens = int(a.get("max_tokens_per_call", 8192))
        self.temperature = float(a.get("temperature", 0))

    def run(self, task: dict[str, Any], documents: str | Path, memory: list[dict[str, Any]],
            tools: list[dict[str, Any]] | None = None, extra_guidance: str = "") -> dict[str, Any]:
        tools = tools or TOOL_SPECS
        ws = Workspace(Path(documents))
        traj = Trajectory(task["task_id"])
        mem_text = render_memory(memory)
        system = SYSTEM_PROMPT + (f"\n\n{mem_text}" if mem_text else "") + (f"\n\n{extra_guidance}" if extra_guidance else "")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"# Task\n{task['instructions']}\n\nDocuments in the matter folder: "
                                        f"{', '.join(ws.docs)}"},
        ]
        traj.log("agent_start", task_id=task["task_id"], n_memory_lessons=len(memory),
                 memory_lesson_ids=[l["lesson_id"] for l in memory], system_prompt=system,
                 user_prompt=messages[1]["content"])
        in_tok = out_tok = llm_calls = 0
        docs_read: list[str] = []
        queries: list[str] = []
        tool_calls_log: list[dict[str, Any]] = []
        t0 = time.time()
        finished = False
        budget_hit = False
        nudged_no_draft = False
        step = 0
        hard_cap = self.max_steps + 3
        while step < hard_cap and not finished:
            step += 1
            over_budget = step > self.max_steps or (self.max_input_tokens and in_tok >= self.max_input_tokens)
            if over_budget and not budget_hit:
                budget_hit = True
                messages.append({"role": "user", "content": BUDGET_MSG})
                traj.log("budget_exhausted", step=step, input_tokens=in_tok)
            r = chat(messages, model=self.mcfg["model"], provider=self.mcfg["provider"], role="agent",
                     temperature=self.temperature, max_tokens=self.max_tokens, tools=tools)
            llm_calls += 1
            in_tok += r["usage"]["input_tokens"]
            out_tok += r["usage"]["output_tokens"]
            content = r["content"] or ""
            calls = r["tool_calls"] or []
            traj.log("assistant_message", step=step, content=content, n_tool_calls=len(calls),
                     usage=r["usage"], finish_reason=r["finish_reason"])
            asst: dict[str, Any] = {"role": "assistant", "content": content or None}
            if calls:
                asst["tool_calls"] = [{"id": c.get("id") or f"call_{step}_{i}", "type": "function",
                                       "function": {"name": c["function"]["name"],
                                                    "arguments": c["function"].get("arguments") or "{}"}}
                                      for i, c in enumerate(calls)]
            messages.append(asst)
            if not calls:
                if ws.draft.strip():
                    finished = True
                    traj.log("agent_finish", step=step, reason="no_tool_call_with_draft")
                    break
                if len(content.strip()) > 400 and nudged_no_draft:
                    ws.write_draft(content)
                    traj.log("draft_created", step=step, tool="implicit_from_message")
                    finished = True
                    traj.log("agent_finish", step=step, reason="message_as_deliverable")
                    break
                nudged_no_draft = True
                messages.append({"role": "user", "content": "Use the tools: record the deliverable with write_draft, then call finish."})
                continue
            for c in asst["tool_calls"]:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"]["arguments"] or "{}")
                    if not isinstance(args, dict):
                        args = {}
                except json.JSONDecodeError:
                    args = {}
                klass = traj.tool_call(step, name, args)
                result = self._dispatch(ws, name, args)
                if name == "read_document":
                    docs_read.append(str(args.get("name")))
                if name == "search_documents":
                    queries.append(str(args.get("query")))
                tool_calls_log.append({"step": step, "tool": name, "arguments": args, "action_class": klass})
                traj.log("tool_result", step=step, tool=name, result=result)
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
                if name == "finish":
                    if ws.draft.strip():
                        finished = True
                        traj.log("agent_finish", step=step, reason="finish_tool", summary=args.get("summary", ""))
                    else:
                        messages[-1]["content"] = "ERROR: the draft is empty. Call write_draft with the deliverable first."
        if not finished:
            traj.log("agent_finish", step=step, reason="step_cap", draft_words=len(ws.draft.split()))
        latency_ms = (time.time() - t0) * 1000
        return {
            "task_id": task["task_id"],
            "deliverable": ws.draft,
            "trajectory": traj.events,
            "tool_calls": tool_calls_log,
            "documents_read": docs_read,
            "search_queries": queries,
            "behaviour": traj.summary(),
            "steps": step,
            "llm_calls": llm_calls,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "latency_ms": round(latency_ms),
            "cost_usd": round(price(self.cfg, self.mcfg["model"], in_tok, out_tok), 6),
            "finished_cleanly": finished,
            "budget_hit": budget_hit,
            "draft_versions": len(ws.draft_versions),
        }

    @staticmethod
    def _dispatch(ws: Workspace, name: str, args: dict[str, Any]) -> str:
        try:
            if name == "list_documents":
                return ws.list_documents()
            if name == "read_document":
                return ws.read_document(args.get("name", ""), args.get("start_line", 1), args.get("num_lines", 200))
            if name == "search_documents":
                return ws.search_documents(args.get("query", ""))
            if name == "calculate":
                return calculate(args.get("expression", ""))
            if name == "write_draft":
                return ws.write_draft(args.get("content", ""))
            if name == "edit_draft":
                return ws.edit_draft(args.get("find", ""), args.get("replace", ""))
            if name == "read_draft":
                return ws.read_draft()
            if name == "finish":
                return "Submitted."
            return f"ERROR: unknown tool {name}"
        except Exception as e:  # noqa: BLE001 — tool errors are returned to the agent
            return f"ERROR: {type(e).__name__}: {e}"
