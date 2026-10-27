"""Sleep phase step 2: merge candidate lessons into memory as proposed operations.

The merge model never edits memory directly: it emits ADD / MERGE / UPDATE / DELETE
operations, which the commit gate then accepts, rejects or sends to review.
"""

from __future__ import annotations

import concurrent.futures as cf
import json
from typing import Any, Callable

from common.config import model_cfg, price, results_root
from common.io import read_json, write_json
from common.llm import chat_json
from memory.store import CATEGORIES, Memory

MERGE_SYSTEM = """You curate the long-term memory of a legal AI agent. Memory holds reusable lessons:
"checklist" items (what a deliverable must contain) and "practice_note"s (how to do the work).

You receive the EXISTING lessons of one category (with usage statistics) and NEW candidate lessons written by a reviewer after graded runs.
Produce a list of operations:
- ADD: create a new lesson from one or more candidates that say something not already covered. Combine overlapping candidates into one well-worded lesson.
- MERGE: fold candidates and/or several existing lessons into ONE lesson (the first id in lesson_ids survives; others are retired). Give the full new text.
- UPDATE: rewrite one existing lesson to add the new detail, exception or edge case from candidates (lessons may grow more precise over time, e.g. adding a weekend rule to a deadline lesson).
- DELETE: retire an existing lesson that is redundant, wrong, overly specific, or whose statistics show it is often harmful/irrelevant and rarely helpful.
Existing lessons not mentioned are kept unchanged. Candidates not referenced by any operation are dropped (use this for narrow, duplicate or task-specific candidates).

Rules for lesson text: generalisable to other clients and matters; NO party names, amounts, dates, clause/section numbers, document names or other matter facts; imperative; one coherent behaviour per lesson; at most 120 words.
Keep the category compact: at most {max_n} active lessons after your operations.
Every operation must cite the candidate_ids it uses. Return JSON only."""


def _merge_chunk(cfg: dict[str, Any], category: str, existing: list[dict[str, Any]],
                 cands: list[dict[str, Any]], max_n: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ex_txt = "\n".join(
        f"- {l['lesson_id']} ({l['type']}; sources={len(l['source_tasks'])}; used={l['times_retrieved']}, "
        f"helpful={l['times_helpful']}, harmful={l['times_harmful']}, unhelpful={l['times_unhelpful']}; "
        f"scope={l['scope'].get('task_type', 'general')}): {l['text']}" for l in existing) or "(none)"
    c_txt = "\n".join(f"- {c['candidate_id']} ({c['type']}; scope={c.get('task_type_scope', 'general')}; "
                      f"from {c['source_tasks'][0]}): {c['text']}" for c in cands)
    schema = ('{"operations": [{"action": "ADD|MERGE|UPDATE|DELETE", "lesson_ids": ["L0001"], '
              '"candidate_ids": ["c01_..."], "type": "checklist|practice_note", '
              '"task_type_scope": "general|issues_list|legal_memo|contract_review|redline|due_diligence|timeline_analysis", '
              '"text": "full lesson text (omit for DELETE)", "reason": "short"}]}')
    user = (f"# Category: {category}\n\n# Existing lessons\n{ex_txt}\n\n# New candidate lessons\n{c_txt}\n\n"
            f"JSON schema: {schema}")
    m = model_cfg(cfg, "sleep")
    parsed, raw = chat_json([{"role": "system", "content": MERGE_SYSTEM.replace("{max_n}", str(max_n))},
                             {"role": "user", "content": user}],
                            model=m["model"], provider=m["provider"], role="sleep_merge", max_tokens=12000)
    ops = [o for o in ((parsed or {}).get("operations") or []) if isinstance(o, dict)]
    trace = {"category": category, "n_existing": len(existing), "n_candidates": len(cands), "prompt": user,
             "raw_response": raw["content"][:40000], "input_tokens": raw["usage"]["input_tokens"],
             "output_tokens": raw["usage"]["output_tokens"],
             "cost_usd": price(cfg, m["model"], raw["usage"]["input_tokens"], raw["usage"]["output_tokens"])}
    return ops, trace


def propose_operations(cfg: dict[str, Any], lineage: str, cycle: int, memory: Memory,
                       reviews: list[dict[str, Any]], log: Callable[[str], None] = print) -> list[dict[str, Any]]:
    """Return normalised operations: {action, lesson_ids, candidates (full dicts), type, category, text, scope}."""
    out_path = results_root(cfg) / "lessons" / lineage / f"cycle_{cycle:02d}" / "merge_operations.json"
    if out_path.exists():
        return read_json(out_path)["operations"]
    cands = [c for r in reviews for c in r["candidates"]]
    by_cid = {c["candidate_id"]: c for c in cands}
    ops_out: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []

    if not cfg["sleep"].get("merge", True):
        # Ablation F: no curation — every candidate is appended as its own lesson (exact duplicates collapsed).
        seen: dict[str, dict[str, Any]] = {}
        for c in cands:
            key = c["text"].strip().lower()
            if key in seen:
                seen[key]["candidates"].append(c)
                continue
            seen[key] = {"action": "ADD", "lesson_ids": [], "candidates": [c], "type": c["type"],
                         "category": c["category"] if c["category"] in CATEGORIES else "general", "text": c["text"],
                         "scope": {"task_type": c.get("task_type_scope", "general"),
                                   "practice_area": c.get("practice_area_scope", "general")}}
        ops_out = list(seen.values())
    else:
        chunk = int(cfg["sleep"].get("merge_chunk", 40))
        max_n = int(cfg["sleep"].get("max_lessons_per_category", 40))
        groups: dict[str, list[dict[str, Any]]] = {c: [] for c in CATEGORIES}
        for c in cands:
            groups[c["category"] if c["category"] in CATEGORIES else "general"].append(c)

        def run_category(cat: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            # Chunks within a category run sequentially against a working copy so later chunks see earlier merges.
            work = memory.copy()
            cat_ops, cat_traces = [], []
            n_tmp = 0
            items = groups[cat]
            for s in range(0, len(items), chunk):
                part = items[s:s + chunk]
                existing = [l for l in work.active() if l["category"] == cat]
                ops, tr = _merge_chunk(cfg, cat, existing, part, max_n)
                tr["chunk"] = s // chunk
                cat_traces.append(tr)
                for o in ops:
                    norm = _normalise(o, cat, by_cid, work)
                    if norm:
                        if norm["action"] == "ADD":
                            # Provisional id so later chunks can refine this lesson; mapped to a real id
                            # (or dropped) when gated operations are applied.
                            n_tmp += 1
                            norm["provisional_id"] = f"tmp_{cycle:02d}_{cat}_{n_tmp}"
                        cat_ops.append(norm)
                        _apply_provisional(work, norm, cycle)
            return cat_ops, cat_traces

        with cf.ThreadPoolExecutor(len(CATEGORIES)) as ex:
            for cat_ops, cat_traces in ex.map(run_category, [c for c in CATEGORIES if groups[c]]):
                ops_out.extend(cat_ops)
                traces.extend(cat_traces)
    used = {c["candidate_id"] for o in ops_out for c in o["candidates"]}
    dropped = [c for c in cands if c["candidate_id"] not in used]
    write_json(out_path, {"cycle": cycle, "lineage": lineage, "n_candidates": len(cands),
                          "n_dropped_by_merge": len(dropped), "operations": ops_out,
                          "dropped_candidates": dropped, "merge_traces": traces})
    log(f"[sleep:{lineage}] cycle {cycle}: {len(ops_out)} proposed ops, {len(dropped)} candidates dropped by merge")
    return ops_out


def _normalise(o: dict[str, Any], cat: str, by_cid: dict[str, dict], work: Memory) -> dict[str, Any] | None:
    action = str(o.get("action", "")).upper()
    if action not in ("ADD", "MERGE", "UPDATE", "DELETE"):
        return None
    lids = [i for i in (o.get("lesson_ids") or []) if i in work.lessons and work.lessons[i]["status"] == "active"]
    cands = [by_cid[i] for i in (o.get("candidate_ids") or []) if i in by_cid]
    text = str(o.get("text") or "").strip()
    if action in ("MERGE", "UPDATE") and not lids:
        action = "ADD"
    if action == "ADD" and (not text or not cands):
        return None
    if action in ("MERGE", "UPDATE") and not text:
        return None
    if action == "DELETE" and not lids:
        return None
    base = work.lessons[lids[0]] if lids else None
    return {"action": action, "lesson_ids": lids, "candidates": cands,
            "type": o.get("type") or (base["type"] if base else (cands[0]["type"] if cands else "practice_note")),
            "category": cat, "text": text, "reason": str(o.get("reason", ""))[:400],
            "scope": {"task_type": o.get("task_type_scope") or (base["scope"]["task_type"] if base else "general"),
                      "practice_area": "general"}}


def _apply_provisional(work: Memory, op: dict[str, Any], cycle: int) -> None:
    """Apply to a scratch copy so later chunks see the effect (the real apply happens after the gate)."""
    from memory.versioning import apply_operation
    apply_operation(work, op, cycle, new_id=op.get("provisional_id"))
