"""One wake-sleep cycle: wake (train) -> grade -> sleep (review, merge) -> commit gate -> memory v{cycle}.

Usage: python -m experiments.run_cycle --config config/base.yaml --cycle 1 [--lineage main]
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.config import load_config, results_root  # noqa: E402
from common.io import read_json, write_json, write_jsonl  # noqa: E402
from experiments.common import evaluate_condition, make_logger, make_row, summarise  # noqa: E402
from grading.grade_runs import grade_run  # noqa: E402
from grading.rubric import load_tasks  # noqa: E402
from memory.commit_gate import gate_operations  # noqa: E402
from memory.store import Memory  # noqa: E402
from memory.versioning import apply_operation, load_version, save_version  # noqa: E402
from sleep.evaluator import apply_feedback  # noqa: E402
from sleep.lesson_generator import generate_lessons  # noqa: E402
from sleep.merger import propose_operations  # noqa: E402
from wake.rollout import rollout  # noqa: E402


def commit(cfg: dict[str, Any], lineage: str, cycle: int, base: Memory, ops: list[dict[str, Any]],
           log: Callable[[str], None]) -> tuple[Memory, dict[str, Any]]:
    """Gate the proposed operations and apply the accepted ones to produce the next memory version."""
    existing_texts = [l["text"] for l in base.active()]
    decisions, gate_traces = gate_operations(cfg, ops, base.lessons, existing_texts)
    new = base.copy()
    new.version = cycle
    new.cycle = cycle
    id_map: dict[str, str | None] = {}
    added, modified, removed, rejected, review = [], [], [], [], []
    for op, d in zip(ops, decisions):
        op = dict(op)
        mapped = []
        for lid in op["lesson_ids"]:
            if lid.startswith("tmp_"):
                if id_map.get(lid):
                    mapped.append(id_map[lid])
            elif lid in new.lessons and new.lessons[lid]["status"] == "active":
                mapped.append(lid)
        op["lesson_ids"] = mapped
        if op["action"] in ("MERGE", "UPDATE") and not mapped:
            op["action"] = "ADD"
        if op["action"] == "DELETE" and not mapped:
            continue
        rec = {"action": op["action"], "lesson_ids": mapped, "text": op.get("text", ""), "type": op["type"],
               "category": op["category"], "candidate_ids": [c["candidate_id"] for c in op["candidates"]],
               "source_tasks": sorted({t for c in op["candidates"] for t in c["source_tasks"]}),
               "decision": d["decision"], "reason": d.get("reason", ""), "gate_verdict": d.get("verdict"),
               "leakage": d.get("leakage")}
        if d["decision"] != "COMMIT":
            (rejected if d["decision"] == "REJECT" else review).append(rec)
            if op.get("provisional_id"):
                id_map[op["provisional_id"]] = None
            continue
        if op["action"] == "DELETE":
            before = [dict(new.lessons[i]) for i in mapped]
            apply_operation(new, op, cycle)
            removed.extend({"lesson_id": b["lesson_id"], "text": b["text"], "reason": op.get("reason", "")} for b in before)
            continue
        before_text = {i: new.lessons[i]["text"] for i in mapped}
        lid = apply_operation(new, op, cycle)
        rec["lesson_id"] = lid
        if op.get("provisional_id"):
            id_map[op["provisional_id"]] = lid
        if op["action"] == "ADD":
            added.append(rec)
        else:
            rec["before"] = before_text
            modified.append(rec)
            for absorbed in mapped[1:]:
                removed.append({"lesson_id": absorbed, "text": before_text.get(absorbed, ""), "reason": f"merged into {lid}"})
    diff = {
        "cycle": cycle, "lineage": lineage, "from_version": base.version, "to_version": new.version,
        "n_active_before": len(base.active()), "n_active_after": len(new.active()),
        "counts": {"added": len(added), "modified": len(modified), "removed": len(removed),
                   "rejected": len(rejected), "review_queue": len(review), "proposed": len(ops)},
        "added": added, "modified": modified, "removed": removed, "rejected": rejected, "review_queue": review,
        "gate_traces": gate_traces,
    }
    log(f"[commit:{lineage}] cycle {cycle}: {diff['counts']} -> {len(new.active())} active lessons")
    return new, diff


def run_cycle(cfg: dict[str, Any], lineage: str, cycle: int, memory: Memory, log: Callable[[str], None],
              eval_validation: bool = True) -> Memory:
    train = load_tasks("train")[: cfg.get("limit_train") or None]
    val = load_tasks("validation")[: cfg.get("limit_validation") or None]
    tag = f"{lineage}/cycle_{cycle:02d}"
    val_future = None
    pool = cf.ThreadPoolExecutor(1)
    if eval_validation:  # validation with the same memory runs alongside sleep (it never feeds learning)
        val_future = pool.submit(evaluate_condition, cfg, f"{tag}/validation", f"{lineage}_v{memory.version}",
                                 val, memory, "full" if memory.version > 0 else "none", 0, log)
    # ---- WAKE
    results = rollout(cfg, f"{tag}/train", train, memory, "full" if memory.version > 0 else "none",
                      run_meta={"condition": f"{lineage}_train", "cycle": cycle}, log=log)
    # ---- GRADE (always computed for reporting; the no-grading ablation simply withholds it from sleep)
    grades = grade_run(cfg, f"{tag}/train", train, results, log=log)
    train_rows = [make_row(r, grades.get(r["task_id"]), f"{lineage}_train") for r in results]
    # ---- SLEEP
    reviews = generate_lessons(cfg, lineage, cycle, train, results, grades, memory.lessons, log=log)
    base = memory.copy()
    reset_every = int(cfg.get("reset_every") or 0)
    feedback = apply_feedback(base, results, reviews) if memory.version > 0 else {}
    if reset_every and cycle % reset_every == 0:
        log(f"[sleep:{lineage}] cycle {cycle}: memory reset before merge (ablation)")
        nid = base.next_id
        base = Memory(version=base.version, cycle=base.cycle, next_id=nid)
    existing = load_version(cfg, lineage, cycle)
    if existing is not None:  # resumed after a later step failed: never re-gate a committed version
        from memory.versioning import memory_dir
        new, diff = existing, read_json(memory_dir(cfg, lineage) / f"memory_v{cycle}_diff.json")
        log(f"[sleep:{lineage}] cycle {cycle}: memory v{cycle} already committed; reusing")
    else:
        ops = propose_operations(cfg, lineage, cycle, base, reviews, log=log)
        new, diff = commit(cfg, lineage, cycle, base, ops, log)
        diff["helpfulness_feedback"] = feedback
        save_version(cfg, lineage, new, diff)
    rq = results_root(cfg) / "lessons" / lineage / "review_queue.jsonl"
    prev = [r for r in (read_json(rq.with_suffix(".json")) if rq.with_suffix(".json").exists() else [])
            if r.get("cycle") != cycle]
    write_json(rq.with_suffix(".json"), prev + [{**r, "cycle": cycle} for r in diff["review_queue"]])
    val_rows = val_future.result() if val_future else []
    pool.shutdown()
    summary = {
        "lineage": lineage, "cycle": cycle, "memory_in": memory.version, "memory_out": new.version,
        "train": summarise(train_rows), "validation_with_memory_in": summarise(val_rows),
        "memory_counts": diff["counts"], "n_active": len(new.active()),
        "n_candidates": sum(len(r["candidates"]) for r in reviews),
        "sleep_cost_usd": sum(r["cost_usd"] for r in reviews), "helpfulness_feedback": feedback,
    }
    cyc_dir = results_root(cfg) / "cycles" / lineage
    write_json(cyc_dir / f"cycle_{cycle:02d}.json", summary)
    write_jsonl(cyc_dir / f"cycle_{cycle:02d}_train_rows.jsonl", train_rows)
    if val_rows:
        write_jsonl(cyc_dir / f"cycle_{cycle:02d}_validation_rows.jsonl", val_rows)
    log(f"[cycle:{lineage}] {cycle} done: train={summary['train'].get('rubric_pass_rate'):.3f} "
        f"val(v{memory.version})={summary['validation_with_memory_in'].get('rubric_pass_rate', float('nan')):.3f} "
        f"memory v{new.version}: {len(new.active())} lessons")
    return new


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/base.yaml")
    ap.add_argument("--cycle", type=int, required=True)
    ap.add_argument("--lineage", default="main")
    ap.add_argument("--no-validation", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config)
    log = make_logger(cfg, args.lineage)
    mem = load_version(cfg, args.lineage, args.cycle - 1)
    if mem is None:
        if args.cycle != 1:
            sys.exit(f"memory v{args.cycle - 1} for lineage {args.lineage} not found")
        mem = Memory()
        save_version(cfg, args.lineage, mem, None)
    run_cycle(cfg, args.lineage, args.cycle, mem, log, eval_validation=not args.no_validation)


if __name__ == "__main__":
    main()
