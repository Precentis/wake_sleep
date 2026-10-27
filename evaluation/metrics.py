"""Metric aggregation over task-result rows."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

BEHAVIOUR_KEYS = ["tool_calls", "research_actions", "analysis_actions", "drafting_actions", "editing_actions",
                  "verification_actions", "n_read_document", "n_search_documents", "n_calculate", "n_read_draft",
                  "draft_revisions", "steps", "llm_calls"]
COST_KEYS = ["input_tokens", "output_tokens", "total_tokens", "cost_usd", "latency_ms", "memory_tokens",
             "n_memory_lessons", "judge_cost_usd"]


def _mean(rows: list[dict[str, Any]], k: str) -> float | None:
    vals = [r[k] for r in rows if r.get(k) is not None]
    return sum(vals) / len(vals) if vals else None


def condition_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    g = [r for r in rows if "rubric_score" in r]
    out: dict[str, Any] = {"n_tasks": len(rows), "n_graded": len(g)}
    if not g:
        return out
    out["all_pass_rate"] = _mean(g, "all_pass")
    out["rubric_pass_rate"] = _mean(g, "rubric_score")
    out["house_standard_pass_rate"] = _mean(g, "house_standard_score")
    out["substantive_pass_rate"] = _mean(g, "substantive_score")
    out["judge_agreement"] = _mean(g, "judge_agreement")
    for j in ("judge_1", "judge_2"):
        out[f"{j}_rubric_pass_rate"] = _mean(g, f"{j}_rubric_score")
        out[f"{j}_all_pass_rate"] = _mean(g, f"{j}_all_pass")
    for k in COST_KEYS + BEHAVIOUR_KEYS:
        out[f"{k}_per_task"] = _mean(rows, k)
    out["latency_s_per_task"] = (out["latency_ms_per_task"] or 0) / 1000
    out["finished_cleanly_rate"] = _mean(rows, "finished_cleanly")
    # Criterion pass rate by source (issue template or house standard).
    by_src: dict[str, list[bool]] = defaultdict(list)
    for r in g:
        for cid, ok in r["criteria_pass"].items():
            by_src[r["criteria_source"][cid]].append(ok)
    out["pass_rate_by_criterion_source"] = {k: sum(v) / len(v) for k, v in sorted(by_src.items())}
    return out


def by_group(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[str(r.get(key))].append(r)
    return {k: condition_metrics(v) for k, v in sorted(groups.items())}
