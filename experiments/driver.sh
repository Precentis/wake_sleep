#!/bin/zsh
# Runs every training lineage to completion (re-launching after quota aborts), then all held-out evals and the report.
cd "${0:A:h}/.."
PY=../../legal-memory-retrieval/.venv/bin/python
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
run_until_done() {  # $1 config, $2 lineage, $3 cycles, $4 extra flag
  local R=results/ws_2026_001/cycles/$2
  for attempt in {1..20}; do
    [[ -f $R/DONE ]] && return 0
    $PY -m experiments.run_experiment --config $1 $4 >> results/$2.out 2>&1
    sleep 120
  done
}
run_until_done config/base.yaml main 10 "" &
run_until_done config/ablations/no_commit_gate.yaml ablation_no_commit_gate 3 --no-validation &
run_until_done config/ablations/no_grading.yaml ablation_no_grading 3 --no-validation &
run_until_done config/ablations/no_merge.yaml ablation_no_merge 2 --no-validation &
run_until_done config/ablations/memory_reset.yaml ablation_memory_reset 4 --no-validation &
wait
echo "$(date) training lineages finished; starting final eval"
for attempt in {1..10}; do
  $PY -m experiments.run_final_eval --config config/base.yaml && break
  sleep 300
done
$PY -m analysis.reports --config config/base.yaml
echo "$(date) driver done"
