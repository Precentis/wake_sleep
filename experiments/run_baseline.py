"""Thin wrapper: python -m experiments.run_baseline [--config ...] (phases: baseline). See run_final_eval.py."""

import sys

from experiments.run_final_eval import main

if __name__ == "__main__":
    if "--phases" not in sys.argv:
        sys.argv += ["--phases", "baseline"]
    main()
