"""Grade a wake run with the configured judges; cached per task under results/<exp>/grades/<run_name>/."""

from __future__ import annotations

import concurrent.futures as cf
import time
import traceback
from typing import Any, Callable

from common.config import results_root
from common.io import read_json, write_json
from grading.aggregation import aggregate
from grading.judge import grade_one
from grading.rubric import load_rubric


def grade_task(cfg: dict[str, Any], run_name: str, task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    out = results_root(cfg) / "grades" / run_name / f"{task['task_id']}.json"
    if out.exists():
        g = read_json(out)
    else:
        judgements = [grade_one(cfg, j, task, result["deliverable"]) for j in cfg["grading"]["judges"]]
        g = {"task_id": task["task_id"], "run_name": run_name, "judgements": judgements}
        write_json(out, g)
    agg = aggregate(task, load_rubric(task), g["judgements"], rule=cfg["grading"].get("aggregation", "both_pass"))
    agg["judge_cost_usd"] = sum(j["cost_usd"] for j in g["judgements"])
    return agg


def grade_run(cfg: dict[str, Any], run_name: str, tasks: list[dict[str, Any]], results: list[dict[str, Any]],
              log: Callable[[str], None] = print) -> dict[str, dict[str, Any]]:
    by_id = {t["task_id"]: t for t in tasks}
    out: dict[str, dict[str, Any]] = {}
    for rnd in range(36):
        todo = [r for r in results if r["task_id"] not in out]
        if not todo:
            break
        if rnd:
            log(f"[grade:{run_name}] retry round {rnd}: {len(todo)} outstanding; waiting 300s")
            time.sleep(300)
        with cf.ThreadPoolExecutor(int(cfg["grading"]["workers"])) as ex:
            futs = {ex.submit(grade_task, cfg, run_name, by_id[r["task_id"]], r): r["task_id"] for r in todo}
            for f in cf.as_completed(futs):
                tid = futs[f]
                try:
                    out[tid] = f.result()
                except Exception:  # noqa: BLE001
                    log(f"[grade:{run_name}] {tid} FAILED\n{traceback.format_exc()[-600:]}")
    if len(out) < len(results):
        raise RuntimeError(f"grade {run_name}: only {len(out)}/{len(results)} graded")
    log(f"[grade:{run_name}] graded {len(out)}/{len(results)}")
    return out
