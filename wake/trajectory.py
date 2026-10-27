"""Trajectory event log for one agent run."""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

from agents.tools import ANALYSIS_TOOLS, DRAFTING_TOOLS, RESEARCH_TOOLS


class Trajectory:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.events: list[dict[str, Any]] = []
        self.t0 = time.time()
        self.draft_exists = False

    def log(self, event: str, **data: Any) -> None:
        self.events.append({"t_ms": int((time.time() - self.t0) * 1000),
                            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                            "event": event, **data})

    def tool_call(self, step: int, name: str, args: dict[str, Any]) -> str:
        """Log a tool call plus its typed sub-event; returns its behavioural class."""
        if name in RESEARCH_TOOLS:
            klass = "verification" if self.draft_exists else "research"
        elif name in ANALYSIS_TOOLS:
            klass = "verification" if self.draft_exists else "analysis"
        elif name in DRAFTING_TOOLS:
            klass = "editing" if (name == "edit_draft" or self.draft_exists) else "drafting"
        elif name == "read_draft":
            klass = "verification"
        else:
            klass = "control"
        self.log("tool_call", step=step, tool=name, arguments=args, action_class=klass)
        sub = {"read_document": "document_read", "search_documents": "document_search",
               "calculate": "code_execution", "edit_draft": "draft_edited"}.get(name)
        if name == "write_draft":
            sub = "draft_edited" if self.draft_exists else "draft_created"
            self.draft_exists = True
        if name == "edit_draft":
            self.draft_exists = True
        if sub:
            self.log(sub, step=step, tool=name)
        return klass

    def summary(self) -> dict[str, int]:
        calls = [e for e in self.events if e["event"] == "tool_call"]
        out: dict[str, int] = {"tool_calls": len(calls)}
        for k in ("research", "analysis", "drafting", "editing", "verification", "control"):
            out[f"{k}_actions"] = sum(1 for e in calls if e["action_class"] == k)
        for tool in ("list_documents", "read_document", "search_documents", "calculate", "write_draft",
                     "edit_draft", "read_draft", "finish"):
            out[f"n_{tool}"] = sum(1 for e in calls if e["tool"] == tool)
        out["draft_revisions"] = out["n_write_draft"] + out["n_edit_draft"]
        return out
