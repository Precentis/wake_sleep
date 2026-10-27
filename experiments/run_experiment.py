"""Full wake-sleep experiment for one lineage (main or an ablation). Resumable.

Usage:
  python -m experiments.run_experiment --config config/base.yaml --cycles 10
  python -m experiments.run_experiment --config config/ablations/no_commit_gate.yaml --lineage ablation_no_commit_gate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.config import load_config, results_root  # noqa: E402
from common.llm import USAGE  # noqa: E402
from experiments.common import evaluate_condition, make_logger, write_metadata  # noqa: E402
from experiments.run_cycle import run_cycle  # noqa: E402
from grading.rubric import load_tasks  # noqa: E402
from memory.store import Memory  # noqa: E402
from memory.versioning import latest_version, load_version, save_version  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/base.yaml")
    ap.add_argument("--cycles", type=int, default=None)
    ap.add_argument("--lineage", default=None)
    ap.add_argument("--no-validation", action="store_true", help="skip per-cycle validation evals (ablations)")
    args = ap.parse_args()
    cfg = load_config(args.config)
    lineage = args.lineage or ("main" if not cfg.get("ablation") else f"ablation_{cfg['ablation']}")
    cycles = args.cycles or int(cfg["cycles"])
    log = make_logger(cfg, lineage)
    write_metadata(cfg, lineage, {"lineage": lineage, "cycles": cycles})
    if latest_version(cfg, lineage) < 0:
        save_version(cfg, lineage, Memory(), None)
    for cycle in range(1, cycles + 1):
        if (results_root(cfg) / "cycles" / lineage / f"cycle_{cycle:02d}.json").exists():
            log(f"[{lineage}] cycle {cycle} already complete; skipping")
            continue
        mem = load_version(cfg, lineage, cycle - 1)
        log(f"[{lineage}] === cycle {cycle} (memory v{mem.version}, {len(mem.active())} lessons) ===")
        run_cycle(cfg, lineage, cycle, mem, log, eval_validation=not args.no_validation)
        log(f"[{lineage}] usage so far: {USAGE}")
    if not args.no_validation:
        final = load_version(cfg, lineage, cycles)
        evaluate_condition(cfg, f"{lineage}/final_v{cycles}/validation", f"{lineage}_v{cycles}",
                           load_tasks("validation"), final, "full", 0, log)
    (results_root(cfg) / "cycles" / lineage / "DONE").write_text(f"{cycles}\n")
    log(f"[{lineage}] finished {cycles} cycles. usage: {USAGE}")


if __name__ == "__main__":
    main()
