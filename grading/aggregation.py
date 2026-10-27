"""Aggregate dual-judge verdicts into criterion, rubric and all-pass scores."""

from __future__ import annotations

from typing import Any


def aggregate(task: dict[str, Any], rubric: dict[str, Any], judgements: list[dict[str, Any]],
              rule: str = "both_pass", judges: list[str] | None = None) -> dict[str, Any]:
    js = [j for j in judgements if not judges or j["judge"] in judges]
    crits = []
    for c in rubric["criteria"]:
        verdicts = {j["judge"]: next(r for r in j["results"] if r["criterion_id"] == c["id"]) for j in js}
        passes = [v["result"] == "PASS" for v in verdicts.values()]
        if rule == "both_pass":
            ok = all(passes) and bool(passes)
        elif rule == "any_pass":
            ok = any(passes)
        else:  # majority
            ok = sum(passes) * 2 > len(passes)
        crits.append({
            "criterion_id": c["id"], "kind": c["kind"], "source": c["source"], "text": c["text"],
            "pass": ok, "judge_pass_fraction": sum(passes) / max(1, len(passes)),
            "agree": len(set(passes)) <= 1,
            "verdicts": {k: {"result": v["result"], "reason": v["reason"]} for k, v in verdicts.items()},
        })
    n = len(crits)
    w = sum(c.get("weight", 1) for c in rubric["criteria"])
    passed = sum(cr["pass"] * c.get("weight", 1) for cr, c in zip(crits, rubric["criteria"]))
    per_judge = {}
    for j in js:
        pj = [r["result"] == "PASS" for r in j["results"]]
        per_judge[j["judge"]] = {"rubric_score": sum(pj) / max(1, n), "all_pass": all(pj)}
    return {
        "task_id": task["task_id"], "cohort": task["cohort"], "practice_area": task["practice_area"],
        "task_type": task["task_type"], "split": task["split"], "rule": rule,
        "criteria": crits, "n_criteria": n, "n_passed": sum(c["pass"] for c in crits),
        "rubric_score": passed / max(1, w), "all_pass": all(c["pass"] for c in crits),
        "mean_judge_score": sum(c["judge_pass_fraction"] for c in crits) / max(1, n),
        "agreement": sum(c["agree"] for c in crits) / max(1, n),
        "per_judge": per_judge,
        "house_standard_score": _mean([c["pass"] for c in crits if c["kind"] == "house_standard"]),
        "substantive_score": _mean([c["pass"] for c in crits if c["kind"] == "substantive"]),
    }


def _mean(xs: list[bool]) -> float | None:
    return sum(xs) / len(xs) if xs else None
