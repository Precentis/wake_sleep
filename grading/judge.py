"""LLM judge: grades one deliverable against its rubric, criterion by criterion.

Judges are blind to the experimental condition, the agent's memory, previous scores and
each other's verdicts: they see only the task instructions, documents, deliverable, rubric.
"""

from __future__ import annotations

import json
from typing import Any

from common.config import model_cfg, price
from common.llm import chat_json
from grading.rubric import load_documents_text, load_rubric

JUDGE_SYSTEM = """You are an exacting senior partner grading a junior lawyer's deliverable against an expert rubric.
For EACH rubric criterion decide PASS or FAIL:
- PASS only if the deliverable itself clearly satisfies the criterion (substance and any specific figures, dates or references it requires). Equivalent wording is fine; correct values are required.
- FAIL if the point is missing, wrong, vague, or only implied.
Judge only the deliverable text; the matter documents are provided so you can check accuracy.
Reply with JSON only: {"results": [{"criterion_id": "C1", "result": "PASS"|"FAIL", "confidence": 0.0-1.0, "reason": "one or two sentences"}]}"""


def grade_one(cfg: dict[str, Any], judge_role: str, task: dict[str, Any], deliverable: str) -> dict[str, Any]:
    rubric = load_rubric(task)
    crit = "\n".join(f"{c['id']}: {c['text']}" for c in rubric["criteria"])
    user = (
        f"# Task instructions\n{task['instructions']}\n\n# Matter documents\n{load_documents_text(task)}\n\n"
        f"# Deliverable to grade\n<<<DELIVERABLE\n{deliverable or '(empty deliverable)'}\nDELIVERABLE>>>\n\n"
        f"# Rubric criteria\n{crit}\n\nGrade every criterion ({len(rubric['criteria'])} total). JSON only."
    )
    m = model_cfg(cfg, judge_role)
    parsed, raw = chat_json([{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}],
                            model=m["model"], provider=m["provider"], role=judge_role, max_tokens=8000,
                            temperature=0.0)
    by_id = {}
    for r in (parsed.get("results") if isinstance(parsed, dict) else parsed) or []:
        cid = str(r.get("criterion_id", "")).strip()
        res = str(r.get("result", "")).upper()
        by_id[cid] = {"criterion_id": cid, "result": "PASS" if res.startswith("PASS") else "FAIL",
                      "confidence": float(r.get("confidence") or 0.0), "reason": str(r.get("reason", ""))[:600]}
    results = [by_id.get(c["id"], {"criterion_id": c["id"], "result": "FAIL", "confidence": 0.0,
                                   "reason": "judge returned no verdict", "missing": True})
               for c in rubric["criteria"]]
    return {
        "judge": judge_role, "model": m["model"], "results": results,
        "input_tokens": raw["usage"]["input_tokens"], "output_tokens": raw["usage"]["output_tokens"],
        "cost_usd": price(cfg, m["model"], raw["usage"]["input_tokens"], raw["usage"]["output_tokens"]),
        "latency_ms": round(raw["latency_ms"]),
        # Prompt minus the documents (reconstructible from the task folder) for the trace archive.
        "prompt_without_documents": user.split("# Matter documents")[0] + "# Matter documents\n[see task documents]\n"
        + "# Deliverable" + user.split("# Deliverable", 1)[1],
        "raw_response": json.dumps(parsed)[:20000],
    }
