# Wake-sleep legal agent — findings (ws_2026_001)

The protocol follows Niko Grupen, [The Return of Wake-Sleep](https://x.com/nikogrupen/status/2108226990792900876) (8 October 2026). Numbers below are from our own synthetic benchmark and stack, experiment `ws_2026_001`.

All numbers come from `REPORT_TABLES.md` / `summary.json`. Held-out test = 46 tasks (20 familiar, 20 new, 6 negative control). Single seed, one run per task per condition.

## Headline results (test, rubric pass / all-pass)
| Condition | Rubric | All-pass | Cost/task |
|---|---:|---:|---:|
| Vanilla | 54.7% | 2.2% | $0.135 |
| Full memory v10 | 78.4% | 34.8% | $0.407 |
| Retrieved K=50 (K chosen on validation) | 79.5% | 30.4% | $0.384 |
| Budget-matched full memory | 71.4% | 26.1% | $0.193 |
| Oracle partner guidance | 68.1% | 13.0% | $0.188 |
| Placebo memory | 53.6% | 6.5% | $0.179 |

- Learned memory beats vanilla: +23.7 pp rubric (95% CI +15.2 to +32.0, dz 0.81, Wilcoxon p<0.001); all-pass 2.2% -> 34.8% (McNemar p=0.0001).
- Placebo memory gives no gain (-1.1 pp), so the gain is not just from extra prompt text.
- Learned memory beat the hand-written oracle guidance (68.1%). Oracle was run once and has only 289k tokens/task, so it is not cost-comparable with full memory.
- Retrieved K=50 is statistically indistinguishable from full memory (+1.0 pp, p=0.95) at similar cost. Retrieval saved little because K=50 is nearly the whole memory (31 lessons are active in v10, so K=50 loads all of them; the retrieved condition is effectively full memory).

## Generalization
- Familiar matters: +31 pp. New matters: +10.6 pp (full) / +14.9 pp (retrieved). Gains transfer, but much less than on familiar matters.
- Negative controls (research tasks): +36 to +42 pp. These were meant to check for harm and show none, but they are only 6 tasks.

## Cost
Memory raises tokens/task about 3x (207k -> 634k) and cost about 3x. Part of the gain is more work: tool calls 23 -> 32, calculations 5 -> 11, draft revisions 5 -> 9. Budget-matched memory (step and token capped to vanilla's budget) keeps +16.6 pp, so most but not all of the gain survives equal compute.

## Ablations (test; compared with the matching main-lineage memory version)
- No grading (C): 62.7%, -12.8 pp vs full v3 (p=0.0004). Grader feedback matters most.
- No commit gate (B): 74.9% vs 75.5%, no difference. At this scale the gate did not change outcomes; it costs less (836k vs 583k tokens/task — actually the ungated memory was larger and more expensive).
- No merge (F): 79.3% vs 71.1% for full v2 (+8.3 pp, p=0.018). The un-merged memory (1030 lessons in v2) did better, but at ~2.5x the cost ($1.02 vs $0.42/task). Merging buys cost, not accuracy, in this setup.
- Memory reset every 2 cycles (G): 70.8% vs 76.7% for full v4 (-5.9 pp, p=0.013). Accumulating memory helps.

## Learning curve (validation, 40 tasks) — important caveat
Most of the gain appears after the FIRST sleep phase: v0 55.7% -> v1 79.3%. After that validation is flat/noisy (v10 75.3%, v9 72.0%) with no clear upward trend over 10 cycles, and memory shrank from 52 to 24-31 lessons. So the data support "one cycle of learning gives most of the benefit", not steady compounding improvement. The test result for v10 (78.4%) vs validation (75.3%) is consistent with that.

## Memory quality
- Hard leakage hits: 0 in every version; 1-6 soft hits (period mentions).
- Lessons are procedural (bottom-line section, risk ratings, recompute dates/figures).
- Many candidates are rejected by the gate (138 cumulative at v10) and 23 sit in a review queue.

## Caveats (read before citing)
1. Synthetic tasks built by an LLM from templates; the "house standards" appear only in rubrics, so memory can learn them from grades by design. Real-world legal transfer is untested.
2. LLM judges (GLM-5, Kimi-K2.5; a criterion passes only if both agree). No human expert validation. Judge agreement was not re-audited here.
3. Test set is small (46; only 6 negative controls). Per-subset CIs are wide; the "new matters" subset p-values for several conditions are not significant. One seed, no repeated runs, so run-to-run noise on agents at temperature 0 is not measured. The learning-curve fluctuations of a few pp are within noise.
4. The ablations ran with 4 cycles or fewer (no_merge, memory_reset ran 2 and 4 cycles) and no per-cycle validation, so they are compared to main-lineage memory at the same version (v2/v3/v4), not v10. They also used 6 workers vs 16.
5. Costs use assumed list prices; only relative comparisons are meaningful.
6. Oracle Cohen's dz on the negative-control subset is meaningless (SD 0). Ignore it.
7. Operational: Bedrock throttling over ~3 days caused rollbacks of partial cycles; cycles were re-run from cached per-task results. Runs of the same condition were made at different times; provider behaviour could drift.
8. Only the vanilla/full/retrieved/oracle/placebo conditions were evaluated at v10; the ablation numbers are not directly comparable to the v10 numbers.
9. Retrieval conclusion (K=50 best) is weakened by the fact that K=50 ≈ full memory.
