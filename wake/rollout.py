"""Wake phase: run the agent over a set of tasks under one memory condition.

Every run is cached on disk (results/<exp>/trajectories/<run_name>/<task_id>.json), so an
interrupted experiment resumes where it stopped. The agent never sees rubrics, grades or
judge feedback during the wake phase.
"""

from __future__ import annotations

import concurrent.futures as cf
import time
import traceback
from pathlib import Path
from typing import Any, Callable

from agents.legal_agent import LegalAgent
from common.config import results_root
from common.io import read_json, write_json
from data.issue_library import HOUSE_STANDARDS
from grading.rubric import task_dir
from memory.store import Memory, memory_tokens, render_memory

ORACLE_GUIDANCE = ("# Partner's standing guidance\nThe supervising partner expects every deliverable to meet these "
                   "standards where applicable:\n" + "\n".join(f"- {v}" for v in HOUSE_STANDARDS.values()))


def select_memory(cfg: dict[str, Any], task: dict[str, Any], memory: Memory | None, mode: str,
                  k: int, run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if mode in ("none", "oracle") or memory is None:
        return [], None
    if mode in ("full", "placebo"):
        return memory.active(), None
    if mode == "retrieved":
        from memory.retrieval import retrieve
        lessons, trace = retrieve(cfg, task, memory, k)
        return lessons, trace
    raise ValueError(mode)


def run_one(cfg: dict[str, Any], task: dict[str, Any], memory: Memory | None, mode: str, k: int,
            run_dir: Path, run_meta: dict[str, Any]) -> dict[str, Any]:
    out = run_dir / f"{task['task_id']}.json"
    if out.exists():
        return read_json(out)
    lessons, retrieval_trace = select_memory(cfg, task, memory, mode, k, run_dir)
    if retrieval_trace is not None:
        write_json(run_dir.parent.parent / "retrieval" / run_dir.name / f"{task['task_id']}.json", retrieval_trace)
    agent = LegalAgent(cfg)
    res = agent.run(task, task_dir(task) / "documents", lessons,
                    extra_guidance=ORACLE_GUIDANCE if mode == "oracle" else "")
    res.update(run_meta)
    res["memory_mode"] = mode
    res["retrieval_k"] = k if mode == "retrieved" else None
    res["memory_version"] = memory.version if memory is not None else None
    res["n_memory_lessons"] = len(lessons)
    res["memory_tokens"] = memory_tokens(render_memory(lessons)) + (memory_tokens(ORACLE_GUIDANCE) if mode == "oracle" else 0)
    res["injected_lesson_ids"] = [l["lesson_id"] for l in lessons]
    res["cohort"], res["practice_area"], res["task_type"] = task["cohort"], task["practice_area"], task["task_type"]
    res["split"] = task["split"]
    if retrieval_trace is not None:
        res["retrieval_cost_usd"] = retrieval_trace.get("cost_usd", 0.0)
        res["retrieval_input_tokens"] = retrieval_trace.get("input_tokens", 0)
    write_json(out, res)
    return res


def rollout(cfg: dict[str, Any], run_name: str, tasks: list[dict[str, Any]], memory: Memory | None,
            mode: str, k: int = 0, run_meta: dict[str, Any] | None = None,
            log: Callable[[str], None] = print) -> list[dict[str, Any]]:
    run_dir = results_root(cfg) / "trajectories" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {"run_name": run_name, **(run_meta or {})}
    workers = int(cfg["wake"]["workers"])
    done: dict[str, dict[str, Any]] = {}
    # Retry rounds: provider quotas (429 "Too much usage") can last a long time. A batch is only returned
    # complete; otherwise the cycle aborts rather than learning from a partial set of tasks.
    for rnd in range(int(cfg["wake"].get("retry_rounds", 36))):
        todo = [t for t in tasks if t["task_id"] not in done]
        if not todo:
            break
        if rnd:
            log(f"[wake:{run_name}] retry round {rnd}: {len(todo)} tasks outstanding; waiting 300s")
            time.sleep(300)
        with cf.ThreadPoolExecutor(workers) as ex:
            futs = {ex.submit(run_one, cfg, t, memory, mode, k, run_dir, meta): t for t in todo}
            for i, f in enumerate(cf.as_completed(futs), 1):
                t = futs[f]
                try:
                    done[t["task_id"]] = f.result()
                except Exception:  # noqa: BLE001 — retried next round
                    log(f"[wake:{run_name}] {t['task_id']} FAILED\n{traceback.format_exc()[-600:]}")
                if i % 10 == 0 or i == len(todo):
                    log(f"[wake:{run_name}] {len(done)}/{len(tasks)} done")
    missing = [t["task_id"] for t in tasks if t["task_id"] not in done]
    if missing:
        raise RuntimeError(f"wake {run_name}: {len(missing)} tasks never completed: {missing[:10]}")
    results = list(done.values())
    order = {t["task_id"]: i for i, t in enumerate(tasks)}
    return sorted(results, key=lambda r: order[r["task_id"]])
