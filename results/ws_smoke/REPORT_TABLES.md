# Wake-sleep experiment — generated tables

## Main results (held-out test, 46 tasks)

| Condition | All-pass | Rubric pass | House-std pass | Substantive pass | Tokens/task | Cost/task (USD, assumed prices) | Latency (s) | Tool calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Vanilla | 0.0% | 41.7% | 33.3% | 50.0% | 299,834 | 0.1932 | 156 | 29.8 |
| Full memory (v2) | 25.0% | 45.8% | 50.0% | 41.7% | 552,883 | 0.3551 | 274 | 40.5 |
| Retrieved memory (K=50) | 25.0% | 45.8% | 50.0% | 41.7% | 459,186 | 0.2966 | 250 | 33.8 |
| Budget-matched full memory | 25.0% | 41.7% | 41.7% | 41.7% | 225,237 | 0.1458 | 136 | 24.0 |
| Oracle (partner guidance) | 25.0% | 45.8% | 50.0% | 41.7% | 534,170 | 0.3439 | 288 | 40.0 |
| Placebo memory (A) | 25.0% | 41.7% | 41.7% | 41.7% | 462,008 | 0.2941 | 194 | 37.0 |

## Generalization (test, rubric pass rate)

| Condition | Familiar | New matters | Negative control | Δ Familiar | Δ New |
|---|---:|---:|---:|---:|---:|
| Vanilla | — | 41.7% | — | — | — |
| Full memory (v2) | — | 45.8% | — | — | +4.2 pp |
| Retrieved memory (K=50) | — | 45.8% | — | — | +4.2 pp |
| Budget-matched full memory | — | 41.7% | — | — | -0.0 pp |
| Oracle (partner guidance) | — | 45.8% | — | — | +4.2 pp |
| Placebo memory (A) | — | 41.7% | — | — | -0.0 pp |

## Paired statistics vs vanilla (per-task rubric score difference; McNemar on all-pass)

| Comparison | Subset | n | Mean Δ | Median Δ | SD | 95% CI | Cohen dz | Wilcoxon p | improved/worse/tied | all-pass A→B | McNemar p |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---|---:|
| Full memory (v2) | overall | 4 | +4.2 pp | +8.3 pp | 16.0 | [-8.3, +16.7] | 0.26 | 1.0000 | 2/1/1 | 0.0%→25.0% | 1.0000 |
| Full memory (v2) | new | 4 | +4.2 pp | +8.3 pp | 16.0 | [-8.3, +16.7] | 0.26 | 1.0000 | 2/1/1 | 0.0%→25.0% | 1.0000 |
| Retrieved memory (K=50) | overall | 4 | +4.2 pp | +16.7 pp | 25.0 | [-20.8, +16.7] | 0.17 | 0.8750 | 3/1/0 | 0.0%→25.0% | 1.0000 |
| Retrieved memory (K=50) | new | 4 | +4.2 pp | +16.7 pp | 25.0 | [-20.8, +16.7] | 0.17 | 0.8750 | 3/1/0 | 0.0%→25.0% | 1.0000 |
| Budget-matched full memory | overall | 4 | -0.0 pp | +8.3 pp | 23.6 | [-20.8, +16.7] | -0.00 | 1.0000 | 2/1/1 | 0.0%→25.0% | 1.0000 |
| Budget-matched full memory | new | 4 | -0.0 pp | +8.3 pp | 23.6 | [-20.8, +16.7] | -0.00 | 1.0000 | 2/1/1 | 0.0%→25.0% | 1.0000 |
| Oracle (partner guidance) | overall | 4 | +4.2 pp | +8.3 pp | 16.0 | [-8.3, +16.7] | 0.26 | 1.0000 | 2/1/1 | 0.0%→25.0% | 1.0000 |
| Oracle (partner guidance) | new | 4 | +4.2 pp | +8.3 pp | 16.0 | [-8.3, +16.7] | 0.26 | 1.0000 | 2/1/1 | 0.0%→25.0% | 1.0000 |
| Placebo memory (A) | overall | 4 | -0.0 pp | +8.3 pp | 23.6 | [-20.8, +16.7] | -0.00 | 1.0000 | 2/1/1 | 0.0%→25.0% | 1.0000 |
| Placebo memory (A) | new | 4 | -0.0 pp | +8.3 pp | 23.6 | [-20.8, +16.7] | -0.00 | 1.0000 | 2/1/1 | 0.0%→25.0% | 1.0000 |
| Retrieved vs Full | overall | 4 | -0.0 pp | +0.0 pp | 27.2 | [-25.0, +25.0] | -0.00 | 1.0000 | 1/1/2 | —→— | — |

## Learning curve (validation, 40 tasks)

| Memory version | Lessons | Memory tokens | Rubric (all) | Familiar | New | All-pass | Input tokens/task | Cost/task |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v0 | 0 | 0 | 44.4% | — | 44.4% | 0.0% | 205,284 | 0.1373 |
| v1 | 23 | 1,148 | 55.6% | — | 55.6% | 0.0% | 265,966 | 0.1777 |
| v2 | 30 | 1,563 | 68.6% | 74.8% | 62.4% | 12.5% | 345,240 | 0.2307 |

## Memory growth (main lineage)

| Version | Active | Added | Modified | Removed | Rejected | Review queue | Avg words | Memory tokens | Checklist / Practice | Leakage hard / soft |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| v0 | 0 | — | — | — | — | — | 0.0 | 0 | 0 / 0 | 0 / 0 |
| v1 | 23 | 23 | 0 | 0 | 0 | 3 | 22.7 | 1,148 | 11 / 12 | 0 / 0 |
| v2 | 30 | 10 | 3 | 3 | 10 | 1 | 23.7 | 1,563 | 17 / 13 | 0 / 0 |

## Retrieval K sweep (validation)

| K | Rubric pass | All-pass | Input tokens/task | Cost/task |
|---:|---:|---:|---:|---:|
| 3 | 50.0% | 0.0% | 388,701 | 0.2545 |
| 5 | 38.9% | 0.0% | 260,691 | 0.1735 |
| 10 | 66.7% | 0.0% | 408,757 | 0.2679 |
| 20 | 77.8% | 0.0% | 446,839 | 0.2953 |
| 50 | 77.8% | 33.3% | 364,981 | 0.2445 |

K* = 50 (max validation rubric pass rate (3 d.p.), ties -> lower cost)

## Behaviour (test, per task)

| Condition | Tool calls | Research | Analysis | Drafting | Editing | Verification | Doc reads | Searches | Calculations | Draft revisions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Vanilla | 29.8 | 9.5 | 5.2 | 1.0 | 5.5 | 7.5 | 6.2 | 6.8 | 6.5 | 6.5 |
| Full memory (v2) | 40.5 | 14.0 | 10.5 | 1.0 | 8.5 | 5.5 | 6.0 | 9.0 | 12.5 | 9.5 |
| Retrieved memory (K=50) | 33.8 | 12.2 | 7.0 | 1.0 | 6.0 | 6.5 | 5.0 | 9.5 | 8.2 | 7.0 |
| Budget-matched full memory | 24.0 | 12.2 | 8.0 | 1.0 | 0.5 | 1.2 | 4.8 | 7.2 | 8.0 | 1.5 |
| Oracle (partner guidance) | 40.0 | 11.0 | 11.0 | 1.0 | 7.5 | 8.5 | 5.0 | 7.0 | 15.0 | 8.5 |
| Placebo memory (A) | 37.0 | 13.0 | 4.8 | 1.0 | 4.5 | 12.8 | 7.8 | 9.2 | 10.5 | 5.5 |

## Judge robustness

| Condition | Both-pass rubric | Judge 1 only | Judge 2 only | Criterion agreement |
|---|---:|---:|---:|---:|
| Vanilla | 41.7% | 45.8% | 45.8% | 91.7% |
| Full memory (v2) | 45.8% | 45.8% | 50.0% | 95.8% |
| Retrieved memory (K=50) | 45.8% | 50.0% | 50.0% | 91.7% |
| Budget-matched full memory | 41.7% | 45.8% | 50.0% | 87.5% |
| Oracle (partner guidance) | 45.8% | 50.0% | 58.3% | 83.3% |
| Placebo memory (A) | 41.7% | 54.2% | 54.2% | 75.0% |

All graded criterion pairs: n=608, raw agreement 88.8%, Cohen's κ = 0.752
