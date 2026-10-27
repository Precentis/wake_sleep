"""Shared experiment plumbing: logging, metadata, evaluate-a-condition, task-result rows."""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.config import ROOT, results_root  # noqa: E402
from common.io import write_json  # noqa: E402
from grading.grade_runs import grade_run  # noqa: E402
from memory.store import Memory  # noqa: E402
from wake.rollout import rollout  # noqa: E402

_log_lock = threading.Lock()


def make_logger(cfg: dict[str, Any], name: str) -> Callable[[str], None]:
    path = results_root(cfg) / "logs" / f"{name}.log"
    path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        line = f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}"
        with _log_lock:
            print(line, flush=True)
            with open(path, "a") as f:
                f.write(line + "\n")
    return log


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def write_metadata(cfg: dict[str, Any], name: str, extra: dict[str, Any] | None = None) -> None:
    m = cfg["models"]
    meta = {
        "experiment_id": cfg["experiment_id"], "run": name,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "agent_model": m["agent"]["model"], "judge_model": [m[j]["model"] for j in cfg["grading"]["judges"]],
        "sleep_model": m["sleep"]["model"], "commit_model": m["commit"]["model"],
        "retrieval_model": m["retrieval"]["model"], "dataset_author_model": m["author"]["model"],
        "embedding_model": cfg["embedding_model"], "dataset_version": cfg["dataset_version"],
        "temperature": cfg["agent"]["temperature"], "retrieval_k": cfg["memory"].get("retrieval_k"),
        "max_tokens": cfg["agent"]["max_tokens_per_call"], "max_steps": cfg["agent"]["max_steps"],
        "git_commit": git_commit(), "prompt_version": cfg["prompt_version"], "seed": cfg["seed"],
        "config": cfg, **(extra or {}),
    }
    write_json(results_root(cfg) / "metadata" / f"{name.replace('/', '__')}.json", meta)


def make_row(res: dict[str, Any], g: dict[str, Any] | None, condition: str) -> dict[str, Any]:
    b = res.get("behaviour", {})
    row = {
        "condition": condition, "run_name": res.get("run_name"), "task_id": res["task_id"], "split": res.get("split"),
        "cohort": res.get("cohort"), "practice_area": res.get("practice_area"), "task_type": res.get("task_type"),
        "memory_mode": res.get("memory_mode"), "memory_version": res.get("memory_version"),
        "retrieval_k": res.get("retrieval_k"), "n_memory_lessons": res.get("n_memory_lessons", 0),
        "memory_tokens": res.get("memory_tokens", 0),
        "input_tokens": res["input_tokens"], "output_tokens": res["output_tokens"],
        "total_tokens": res["input_tokens"] + res["output_tokens"], "llm_calls": res["llm_calls"],
        "steps": res["steps"], "latency_ms": res["latency_ms"],
        "agent_cost_usd": res["cost_usd"], "retrieval_cost_usd": res.get("retrieval_cost_usd", 0.0),
        "cost_usd": res["cost_usd"] + res.get("retrieval_cost_usd", 0.0),
        "finished_cleanly": res.get("finished_cleanly"), "budget_hit": res.get("budget_hit"),
        "deliverable_words": len((res.get("deliverable") or "").split()),
        **{k: v for k, v in b.items()},
    }
    if g:
        row.update({
            "rubric_score": g["rubric_score"], "all_pass": g["all_pass"], "n_passed": g["n_passed"],
            "n_criteria": g["n_criteria"], "house_standard_score": g["house_standard_score"],
            "substantive_score": g["substantive_score"], "judge_agreement": g["agreement"],
            "mean_judge_score": g["mean_judge_score"],
            **{f"{j}_rubric_score": v["rubric_score"] for j, v in g["per_judge"].items()},
            **{f"{j}_all_pass": v["all_pass"] for j, v in g["per_judge"].items()},
            "judge_cost_usd": g.get("judge_cost_usd", 0.0),
            "criteria_pass": {c["criterion_id"]: c["pass"] for c in g["criteria"]},
            "criteria_source": {c["criterion_id"]: c["source"] for c in g["criteria"]},
        })
    return row


def evaluate_condition(cfg: dict[str, Any], run_name: str, condition: str, tasks: list[dict[str, Any]],
                       memory: Memory | None, mode: str, k: int = 0, log: Callable[[str], None] = print
                       ) -> list[dict[str, Any]]:
    """Wake + grade one condition on a task set; returns task-result rows (cached on disk)."""
    results = rollout(cfg, run_name, tasks, memory, mode, k, run_meta={"condition": condition}, log=log)
    grades = grade_run(cfg, run_name, tasks, results, log=log)
    return [make_row(r, grades.get(r["task_id"]), condition) for r in results]


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    graded = [r for r in rows if "rubric_score" in r]
    n = len(graded)
    if not n:
        return {"n": 0}
    mean = lambda k: sum((r.get(k) or 0) for r in graded) / n  # noqa: E731
    return {"n": n, "rubric_pass_rate": mean("rubric_score"), "all_pass_rate": mean("all_pass"),
            "house_standard_score": sum(r["house_standard_score"] or 0 for r in graded) / n,
            "substantive_score": sum(r["substantive_score"] or 0 for r in graded) / n,
            "tokens_per_task": mean("total_tokens"), "input_tokens_per_task": mean("input_tokens"),
            "cost_per_task": mean("cost_usd"), "latency_s_per_task": mean("latency_ms") / 1000,
            "tool_calls_per_task": mean("tool_calls")}
