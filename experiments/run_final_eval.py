"""Held-out evaluation of every condition. Resumable; each phase can run on its own.

Phases:
  baseline     vanilla agent on test
  full         full final main memory on test
  ksweep       retrieved memory, K in {3,5,10,20,50}, on VALIDATION (selects K*)
  retrieved    retrieved memory with K* on test
  oracle       partner guidance (house standards) on test — approximate upper bound
  budget       full memory under a budget matched to vanilla (steps + input tokens from validation vanilla)
  placebo      ablation A: same-size memory of generic lessons written without any experience
  ablations    final memory of each ablation lineage on test, plus main at the matching cycle

Usage: python -m experiments.run_final_eval --phases baseline,full,ksweep,retrieved,oracle,budget,placebo,ablations
"""

from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.config import load_config, model_cfg, results_root  # noqa: E402
from common.io import read_jsonl, write_json, write_jsonl  # noqa: E402
from common.llm import chat_json  # noqa: E402
from experiments.common import evaluate_condition, make_logger, summarise, write_metadata  # noqa: E402
from grading.rubric import load_tasks  # noqa: E402
from memory.store import CATEGORIES, Memory, new_lesson  # noqa: E402
from memory.versioning import latest_version, load_version, save_version  # noqa: E402

K_VALUES = [3, 5, 10, 20, 50]
ABLATIONS = ["no_commit_gate", "no_grading", "no_merge", "memory_reset"]


def rows_path(cfg: dict[str, Any], name: str) -> Path:
    return results_root(cfg) / "eval_rows" / f"{name.replace('/', '__')}.jsonl"


def run(cfg, name, condition, tasks, memory, mode, k=0, log=print, agent_over: dict | None = None):
    p = rows_path(cfg, name)
    c = cfg
    if agent_over:
        c = {**cfg, "agent": {**cfg["agent"], **agent_over}}
    rows = evaluate_condition(c, name, condition, tasks, memory, mode, k, log)
    write_jsonl(p, rows)
    s = summarise(rows)
    log(f"[eval] {name}: rubric={s.get('rubric_pass_rate', 0):.3f} all_pass={s.get('all_pass_rate', 0):.3f} "
        f"tokens={s.get('tokens_per_task', 0):,.0f} cost=${s.get('cost_per_task', 0):.4f}")
    return rows


def make_placebo(cfg: dict[str, Any], n: int, log) -> Memory:
    existing = load_version(cfg, "placebo", 1)
    if existing is not None:
        return existing
    m = model_cfg(cfg, "sleep")
    per_cat = max(1, round(n / len(CATEGORIES)))
    lessons: list[dict[str, Any]] = []
    for cat in CATEGORIES:
        user = (f"Write {per_cat} generic best-practice lessons for a junior lawyer, category '{cat}' "
                "(analysis = reading/checking/calculating, drafting = structure and content of written work, "
                "review = checking own work, general = anything else). Base them only on general professional "
                "knowledge — you have NOT seen any of this firm's work, rubrics or feedback. Mix 'checklist' items "
                "(what a deliverable must contain) and 'practice_note's (how to work). Each at most 60 words.\n"
                'JSON: {"lessons": [{"type": "checklist|practice_note", "text": "..."}]}')
        parsed, _ = chat_json([{"role": "user", "content": user}], model=m["model"], provider=m["provider"],
                              role="placebo", max_tokens=8000, temperature=0.7)
        for l in (parsed or {}).get("lessons", [])[:per_cat]:
            lessons.append({"cat": cat, **l})
    mem = Memory(version=1, cycle=0)
    for l in lessons:
        lid = mem.alloc_id()
        mem.lessons[lid] = new_lesson(lid, text=str(l["text"]), type_=l.get("type", "practice_note"),
                                      category=l["cat"], cycle=0, source_tasks=[], evidence=[], confidence=0.5)
    save_version(cfg, "placebo", mem, {"note": "placebo memory: generic lessons, no experience", "n": len(lessons)})
    log(f"[placebo] built {len(lessons)} lessons (target {n})")
    return mem


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/base.yaml")
    ap.add_argument("--phases", default="baseline,full,ksweep,retrieved,oracle,budget,placebo,ablations")
    ap.add_argument("--k", type=int, default=None, help="force K for the retrieved phase")
    args = ap.parse_args()
    cfg = load_config(args.config)
    log = make_logger(cfg, "final_eval")
    phases = args.phases.split(",")
    test = load_tasks("test")[: cfg.get("limit_test") or None]
    val = load_tasks("validation")[: cfg.get("limit_validation") or None]
    vfinal = latest_version(cfg, "main")
    final = load_version(cfg, "main", vfinal)
    write_metadata(cfg, "final_eval", {"phases": phases, "main_memory_version": vfinal})
    log(f"[final_eval] main memory v{vfinal}: {len(final.active()) if final else 0} lessons; phases={phases}")

    if "baseline" in phases:
        run(cfg, "eval/test/vanilla", "vanilla", test, None, "none", log=log)
    if "full" in phases:
        run(cfg, f"eval/test/full_v{vfinal}", "full_memory", test, final, "full", log=log)
    k_star = args.k
    if "ksweep" in phases:
        res = {}
        for k in K_VALUES:
            rows = run(cfg, f"eval/validation/retrieved_v{vfinal}_k{k}", f"retrieved_k{k}", val, final, "retrieved", k, log)
            res[k] = summarise(rows)
        best = max(K_VALUES, key=lambda k: (round(res[k]["rubric_pass_rate"], 3), -res[k]["cost_per_task"]))
        write_json(results_root(cfg) / "retrieval" / "k_sweep_validation.json",
                   {"memory_version": vfinal, "results": res, "k_star": best,
                    "rule": "max validation rubric pass rate (3 d.p.), ties -> lower cost"})
        log(f"[ksweep] K* = {best}")
        k_star = k_star or best
    if "retrieved" in phases:
        if k_star is None:
            from common.io import read_json
            k_star = read_json(results_root(cfg) / "retrieval" / "k_sweep_validation.json")["k_star"]
        run(cfg, f"eval/test/retrieved_v{vfinal}_k{k_star}", f"retrieved_k{k_star}", test, final, "retrieved", k_star, log)
    if "oracle" in phases:
        run(cfg, "eval/test/oracle", "oracle", test, None, "oracle", log=log)
    if "budget" in phases:
        vrows = read_jsonl(results_root(cfg) / "cycles" / "main" / "cycle_01_validation_rows.jsonl")
        vrows = [r for r in vrows if r.get("steps")]
        steps = int(st.median(r["steps"] for r in vrows))
        toks = int(st.median(r["input_tokens"] for r in vrows))
        write_json(results_root(cfg) / "ablations" / "budget_matched_params.json",
                   {"max_steps": steps, "max_input_tokens": toks, "source": "median of vanilla validation runs"})
        log(f"[budget] matched budget: max_steps={steps}, max_input_tokens={toks}")
        run(cfg, f"eval/test/budget_matched_v{vfinal}", "budget_matched", test, final, "full", log=log,
            agent_over={"max_steps": steps, "max_input_tokens": toks})
    if "placebo" in phases:
        pm = make_placebo(cfg, len(final.active()), log)
        run(cfg, "eval/test/placebo", "placebo_memory", test, pm, "placebo", log=log)
    if "ablations" in phases:
        for ab in ABLATIONS:
            lin = f"ablation_{ab}"
            v = latest_version(cfg, lin)
            if v <= 0:
                log(f"[ablations] {lin} has no memory yet; skipping")
                continue
            run(cfg, f"eval/test/{lin}_v{v}", ab, test, load_version(cfg, lin, v), "full", log=log)
            mv = load_version(cfg, "main", v)
            run(cfg, f"eval/test/full_v{v}", f"full_memory_v{v}", test, mv, "full", log=log)
    log("[final_eval] done")


if __name__ == "__main__":
    main()
