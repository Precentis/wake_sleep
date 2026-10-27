"""Run every ablation lineage (training cycles) in parallel processes, then their test evaluations.

Usage: python -m experiments.run_ablations [--only no_commit_gate,no_merge] [--skip-train]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABLATIONS = ["no_commit_gate", "no_grading", "no_merge", "memory_reset"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=",".join(ABLATIONS))
    ap.add_argument("--skip-train", action="store_true")
    args = ap.parse_args()
    names = args.only.split(",")
    if not args.skip_train:
        procs = [subprocess.Popen([sys.executable, "-m", "experiments.run_experiment", "--config",
                                   f"config/ablations/{n}.yaml", "--no-validation"], cwd=ROOT,
                                  stdout=open(ROOT / "results" / f"ablation_{n}.out", "a"), stderr=subprocess.STDOUT)
                 for n in names]
        codes = [p.wait() for p in procs]
        print("ablation training exit codes:", dict(zip(names, codes)))
    subprocess.run([sys.executable, "-m", "experiments.run_final_eval", "--phases", "placebo,ablations"], cwd=ROOT,
                   check=False)


if __name__ == "__main__":
    main()
