"""Sleep phase step 1: review each graded training run and propose candidate lessons."""

from __future__ import annotations

import concurrent.futures as cf
import time
import json
import traceback
from typing import Any, Callable

from common.config import model_cfg, price, results_root
from common.io import read_json, write_json
from common.llm import chat_json

REVIEW_SYSTEM = """You are the review model in a wake-sleep learning loop for a legal AI agent.
You read one completed agent run (its tool-use trajectory, its final deliverable and, when available, the expert-rubric verdicts) and write LESSONS that will make the agent do better on FUTURE, DIFFERENT matters.

Two lesson types:
- "checklist": something a deliverable must contain (e.g. "Before finalising an issues list, give every issue a risk rating").
- "practice_note": how to do part of the work (e.g. "Recompute every derived figure yourself with the calculator before relying on it").

Categories: "analysis" (reading, checking, calculating), "drafting" (structure and content of the deliverable), "review" (checking own work before finishing), "general" (anything else).

HARD RULES for lesson text:
- Must generalise to other clients and matters. NEVER include party/company/person names, transaction names, specific amounts, specific dates, specific clause or section numbers, document file names, or other facts unique to this matter.
- State the reusable behaviour, not the answer to this task. Bad: "Flag that the cap of $4.5m is wrong". Good: "Recompute caps expressed as a percentage of price and flag any mismatch with the stated figure".
- One behaviour per lesson, imperative mood, at most 60 words.
Return JSON only."""


def _compress_trajectory(result: dict[str, Any], limit: int = 60) -> str:
    lines = []
    for c in result["tool_calls"][:limit]:
        args = c["arguments"]
        if c["tool"] in ("write_draft",):
            a = f"<{len(str(args.get('content', '')).split())} words>"
        elif c["tool"] == "edit_draft":
            a = f"find={str(args.get('find', ''))[:60]!r} -> {str(args.get('replace', ''))[:60]!r}"
        else:
            a = json.dumps(args)[:160]
        lines.append(f"{c['step']:>2}. [{c['action_class']}] {c['tool']}({a})")
    if len(result["tool_calls"]) > limit:
        lines.append(f"... {len(result['tool_calls']) - limit} more calls")
    return "\n".join(lines) or "(no tool calls)"


def review_run(cfg: dict[str, Any], lineage: str, cycle: int, task: dict[str, Any], result: dict[str, Any],
               grade: dict[str, Any] | None, injected: list[dict[str, Any]], with_feedback: bool) -> dict[str, Any]:
    out = results_root(cfg) / "lessons" / lineage / f"cycle_{cycle:02d}" / "reviews" / f"{task['task_id']}.json"
    if out.exists():
        return read_json(out)
    parts = [
        f"# Task\nType: {task['task_type']} | Practice area: {task['practice_area']}\n{task['instructions']}",
        f"# Trajectory ({result['steps']} model steps, {len(result['tool_calls'])} tool calls)\n{_compress_trajectory(result)}",
        f"# Final deliverable\n{(result['deliverable'] or '(empty)')[:12000]}",
    ]
    if grade is not None:
        crit = "\n".join(
            f"- {c['criterion_id']} [{'PASS' if c['pass'] else 'FAIL'}] {c['text']}\n    judges: "
            + " | ".join(f"{v['result']}: {v['reason'][:220]}" for v in c["verdicts"].values())
            for c in grade["criteria"])
        parts.append(f"# Expert rubric verdicts ({grade['n_passed']}/{grade['n_criteria']} passed)\n{crit}")
        ask = ("Analyse each FAILED criterion: what went wrong, what the agent should have done, and whether the failure "
               "is procedural (reusable) or task-specific. Then write reusable candidate lessons that would prevent "
               "the procedural failures on other matters.")
    else:
        ask = ("No grades are available. Critically assess the deliverable and the work process yourself, as a "
               "demanding supervising partner would, and write reusable candidate lessons for improving the work.")
    if with_feedback and injected:
        parts.append("# Lessons the agent had in memory during this run\n"
                     + "\n".join(f"- [{l['lesson_id']}] {l['text']}" for l in injected))
        ask += (" Also judge the memory lessons: list ONLY those that clearly HELPED (the agent visibly applied them "
                "and it paid off), were HARMFUL (applying them hurt), or were applied but IRRELEVANT. Omit the rest.")
    schema = ('{"failures": [{"criterion_id": "C1", "what_went_wrong": "...", "should_have": "...", '
              '"failure_kind": "procedural|content|task_specific"}], '
              '"candidate_lessons": [{"type": "checklist|practice_note", "category": "analysis|drafting|review|general", '
              '"text": "...", "evidence": ["C1"], "task_type_scope": "general|' + task["task_type"]
              + '", "confidence": 0.0-1.0}], '
              '"lesson_feedback": [{"lesson_id": "L0001", "label": "HELPFUL|HARMFUL|IRRELEVANT", "reason": "..."}]}')
    user = "\n\n".join(parts) + f"\n\n# Your job\n{ask}\nWrite at most 6 candidate lessons.\nJSON schema: {schema}"
    m = model_cfg(cfg, "sleep")
    parsed, raw = chat_json([{"role": "system", "content": REVIEW_SYSTEM}, {"role": "user", "content": user}],
                            model=m["model"], provider=m["provider"], role="sleep_review", max_tokens=6000)
    parsed = parsed if isinstance(parsed, dict) else {}
    cands = []
    for i, c in enumerate(parsed.get("candidate_lessons") or []):
        if not isinstance(c, dict) or not str(c.get("text", "")).strip():
            continue
        cands.append({
            "candidate_id": f"c{cycle:02d}_{task['task_id']}_{i}",
            "type": c.get("type", "practice_note"), "category": c.get("category", "general"),
            "text": str(c["text"]).strip(), "source_tasks": [task["task_id"]],
            "evidence": [f"{task['task_id']}:{e}" for e in (c.get("evidence") or [])],
            "task_type_scope": c.get("task_type_scope", "general"),
            "practice_area_scope": "general" if c.get("task_type_scope", "general") == "general" else task["practice_area"],
            "confidence": float(c.get("confidence") or 0.5),
        })
    rec = {
        "task_id": task["task_id"], "cycle": cycle, "lineage": lineage, "graded": grade is not None,
        "failures": parsed.get("failures") or [], "candidates": cands,
        "lesson_feedback": [f for f in (parsed.get("lesson_feedback") or []) if isinstance(f, dict)],
        "input_tokens": raw["usage"]["input_tokens"], "output_tokens": raw["usage"]["output_tokens"],
        "cost_usd": price(cfg, m["model"], raw["usage"]["input_tokens"], raw["usage"]["output_tokens"]),
        "prompt": user, "raw_response": raw["content"][:30000],
    }
    write_json(out, rec)
    return rec


def generate_lessons(cfg: dict[str, Any], lineage: str, cycle: int, tasks: list[dict[str, Any]],
                     results: list[dict[str, Any]], grades: dict[str, dict[str, Any]], memory_lessons: dict[str, dict],
                     log: Callable[[str], None] = print) -> list[dict[str, Any]]:
    by_id = {t["task_id"]: t for t in tasks}
    use_grades = cfg["sleep"].get("generate_from_grades", True)
    with_fb = cycle >= int(cfg["sleep"].get("helpfulness_from_cycle", 2))
    reviews: list[dict[str, Any]] = []

    def job(r: dict[str, Any]) -> dict[str, Any]:
        injected = [memory_lessons[i] for i in r.get("injected_lesson_ids", []) if i in memory_lessons]
        return review_run(cfg, lineage, cycle, by_id[r["task_id"]], r,
                          grades.get(r["task_id"]) if use_grades else None, injected, with_fb)

    eligible = [r for r in results if (not use_grades or r["task_id"] in grades)]
    got: dict[str, dict[str, Any]] = {}
    for rnd in range(36):
        todo = [r for r in eligible if r["task_id"] not in got]
        if not todo:
            break
        if rnd:
            log(f"[sleep:{lineage}] review retry round {rnd}: {len(todo)} outstanding; waiting 300s")
            time.sleep(300)
        with cf.ThreadPoolExecutor(int(cfg["sleep"]["workers"])) as ex:
            futs = {ex.submit(job, r): r["task_id"] for r in todo}
            for f in cf.as_completed(futs):
                try:
                    got[futs[f]] = f.result()
                except Exception:  # noqa: BLE001
                    log(f"[sleep:{lineage}] review {futs[f]} FAILED\n{traceback.format_exc()[-600:]}")
    if len(got) < len(eligible):
        raise RuntimeError(f"sleep {lineage} cycle {cycle}: only {len(got)}/{len(eligible)} reviews")
    reviews = list(got.values())
    log(f"[sleep:{lineage}] cycle {cycle}: {len(reviews)} reviews, "
        f"{sum(len(r['candidates']) for r in reviews)} candidate lessons")
    return sorted(reviews, key=lambda r: r["task_id"])
