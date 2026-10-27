# Wake-sleep experiment — generated tables

## Main results (held-out test, 46 tasks)

| Condition | All-pass | Rubric pass | House-std pass | Substantive pass | Tokens/task | Cost/task (USD, assumed prices) | Latency (s) | Tool calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Vanilla | 2.2% | 54.7% | 46.7% | 59.9% | 207,201 | 0.1351 | 148 | 23.0 |
| Full memory (v10) | 34.8% | 78.4% | 84.8% | 73.8% | 633,720 | 0.4072 | 297 | 31.8 |
| Retrieved memory (K=50) | 30.4% | 79.5% | 85.5% | 75.1% | 598,806 | 0.3844 | 280 | 31.0 |
| Budget-matched full memory | 26.1% | 71.4% | 76.8% | 67.8% | 295,118 | 0.1925 | 190 | 20.3 |
| Oracle (partner guidance) | 13.0% | 68.1% | 75.4% | 63.1% | 289,743 | 0.1880 | 512 | 27.2 |
| Placebo memory (A) | 6.5% | 53.6% | 48.2% | 56.7% | 276,981 | 0.1791 | 158 | 24.6 |
| No commit gate (B) | 30.4% | 74.9% | 79.7% | 71.5% | 836,242 | 0.5332 | 319 | 35.5 |
| Full memory (v3) [ablation reference] | 26.1% | 75.5% | 81.2% | 71.2% | 583,415 | 0.3746 | 283 | 33.8 |
| No grading (C) | 8.7% | 62.7% | 62.7% | 62.3% | 386,266 | 0.2497 | 221 | 27.8 |
| No merge (F) | 41.3% | 79.3% | 82.6% | 77.2% | 1,622,907 | 1.0168 | 334 | 29.4 |
| Full memory (v2) [ablation reference] | 19.6% | 71.1% | 75.4% | 68.7% | 654,089 | 0.4187 | 266 | 36.6 |
| Memory reset (G) | 21.7% | 70.8% | 70.7% | 70.0% | 700,113 | 0.4513 | 260 | 34.9 |
| Full memory (v4) [ablation reference] | 28.3% | 76.7% | 84.1% | 71.3% | 665,352 | 0.4265 | 218 | 35.1 |

## Generalization (test, rubric pass rate)

| Condition | Familiar | New matters | Negative control | Δ Familiar | Δ New |
|---|---:|---:|---:|---:|---:|
| Vanilla | 57.1% | 55.5% | 44.4% | — | — |
| Full memory (v10) | 88.5% | 66.1% | 86.1% | +31.3 pp | +10.6 pp |
| Retrieved memory (K=50) | 88.2% | 70.4% | 80.6% | +31.1 pp | +14.9 pp |
| Budget-matched full memory | 82.5% | 58.3% | 77.8% | +25.4 pp | +2.9 pp |
| Oracle (partner guidance) | 73.4% | 59.9% | 77.8% | +16.2 pp | +4.4 pp |
| Placebo memory (A) | 59.5% | 51.4% | 41.7% | +2.4 pp | -4.0 pp |
| No commit gate (B) | 89.3% | 58.1% | 83.3% | +32.1 pp | +2.6 pp |
| Full memory (v3) [ablation reference] | 89.0% | 60.5% | 80.6% | +31.9 pp | +5.0 pp |
| No grading (C) | 68.8% | 55.5% | 66.7% | +11.7 pp | +0.0 pp |
| No merge (F) | 88.2% | 69.3% | 83.3% | +31.1 pp | +13.8 pp |
| Full memory (v2) [ablation reference] | 82.4% | 58.6% | 75.0% | +25.3 pp | +3.1 pp |
| Memory reset (G) | 84.0% | 59.6% | 63.9% | +26.9 pp | +4.2 pp |
| Full memory (v4) [ablation reference] | 90.1% | 62.1% | 80.6% | +32.9 pp | +6.7 pp |

## Paired statistics vs vanilla (per-task rubric score difference; McNemar on all-pass)

| Comparison | Subset | n | Mean Δ | Median Δ | SD | 95% CI | Cohen dz | Wilcoxon p | improved/worse/tied | all-pass A→B | McNemar p |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---|---:|
| Full memory (v10) | overall | 46 | +23.7 pp | +20.8 pp | 29.2 | [+15.2, +32.0] | 0.81 | 0.0000 | 33/4/9 | 2.2%→34.8% | 0.0001 |
| Full memory (v10) | familiar | 20 | +31.3 pp | +28.6 pp | 34.6 | [+15.9, +45.5] | 0.91 | 0.0014 | 18/1/1 | 5.0%→65.0% | 0.0005 |
| Full memory (v10) | new | 20 | +10.6 pp | +0.0 pp | 21.4 | [+1.8, +20.2] | 0.50 | 0.0223 | 9/3/8 | 0.0%→5.0% | 1.0000 |
| Full memory (v10) | negative_control | 6 | +41.7 pp | +41.7 pp | 9.1 | [+36.1, +47.2] | 4.56 | 0.0312 | 6/0/0 | 0.0%→33.3% | 0.5000 |
| Retrieved memory (K=50) | overall | 46 | +24.7 pp | +28.6 pp | 26.3 | [+17.2, +32.1] | 0.94 | 0.0000 | 33/6/7 | 2.2%→30.4% | 0.0010 |
| Retrieved memory (K=50) | familiar | 20 | +31.1 pp | +31.0 pp | 26.0 | [+20.2, +42.5] | 1.20 | 0.0004 | 16/1/3 | 5.0%→45.0% | 0.0215 |
| Retrieved memory (K=50) | new | 20 | +14.9 pp | +16.7 pp | 27.5 | [+3.2, +26.7] | 0.54 | 0.0209 | 11/5/4 | 0.0%→20.0% | 0.1250 |
| Retrieved memory (K=50) | negative_control | 6 | +36.1 pp | +33.3 pp | 6.8 | [+33.3, +41.7] | 5.31 | 0.0312 | 6/0/0 | 0.0%→16.7% | 1.0000 |
| Budget-matched full memory | overall | 46 | +16.6 pp | +16.7 pp | 31.6 | [+7.1, +25.3] | 0.53 | 0.0006 | 34/8/4 | 2.2%→26.1% | 0.0034 |
| Budget-matched full memory | familiar | 20 | +25.4 pp | +28.6 pp | 34.0 | [+10.2, +39.2] | 0.75 | 0.0028 | 17/3/0 | 5.0%→40.0% | 0.0391 |
| Budget-matched full memory | new | 20 | +2.9 pp | +14.3 pp | 28.6 | [-9.8, +14.3] | 0.10 | 0.4374 | 11/5/4 | 0.0%→15.0% | 0.2500 |
| Budget-matched full memory | negative_control | 6 | +33.3 pp | +33.3 pp | 10.5 | [+25.0, +41.7] | 3.16 | 0.0312 | 6/0/0 | 0.0%→16.7% | 1.0000 |
| Oracle (partner guidance) | overall | 46 | +13.3 pp | +12.5 pp | 21.6 | [+6.9, +19.6] | 0.62 | 0.0005 | 25/8/13 | 2.2%→13.0% | 0.1250 |
| Oracle (partner guidance) | familiar | 20 | +16.2 pp | +13.4 pp | 24.8 | [+5.6, +26.8] | 0.66 | 0.0229 | 13/4/3 | 5.0%→20.0% | 0.3750 |
| Oracle (partner guidance) | new | 20 | +4.4 pp | +0.0 pp | 16.5 | [-2.5, +11.9] | 0.27 | 0.1823 | 6/4/10 | 0.0%→5.0% | 1.0000 |
| Oracle (partner guidance) | negative_control | 6 | +33.3 pp | +33.3 pp | 0.0 | [+33.3, +33.3] | 4475713293441402.00 | 0.0312 | 6/0/0 | 0.0%→16.7% | 1.0000 |
| Placebo memory (A) | overall | 46 | -1.1 pp | +0.0 pp | 19.0 | [-6.6, +4.3] | -0.06 | 0.6570 | 14/15/17 | 2.2%→6.5% | 0.5000 |
| Placebo memory (A) | familiar | 20 | +2.4 pp | +0.0 pp | 16.5 | [-4.7, +9.4] | 0.14 | 0.6941 | 7/5/8 | 5.0%→10.0% | 1.0000 |
| Placebo memory (A) | new | 20 | -4.0 pp | +0.0 pp | 22.8 | [-14.2, +5.6] | -0.18 | 0.5929 | 6/8/6 | 0.0%→5.0% | 1.0000 |
| Placebo memory (A) | negative_control | 6 | -2.8 pp | +0.0 pp | 12.5 | [-11.1, +5.6] | -0.22 | 1.0000 | 1/2/3 | 0.0%→0.0% | 1.0000 |
| No commit gate (B) | overall | 46 | +20.2 pp | +25.0 pp | 27.6 | [+12.0, +27.9] | 0.73 | 0.0000 | 35/9/2 | 2.2%→30.4% | 0.0010 |
| No commit gate (B) | familiar | 20 | +32.1 pp | +28.6 pp | 23.2 | [+22.1, +42.3] | 1.39 | 0.0004 | 19/1/0 | 5.0%→50.0% | 0.0117 |
| No commit gate (B) | new | 20 | +2.6 pp | +7.1 pp | 25.6 | [-8.5, +13.2] | 0.10 | 0.3591 | 10/8/2 | 0.0%→10.0% | 0.5000 |
| No commit gate (B) | negative_control | 6 | +38.9 pp | +33.3 pp | 8.6 | [+33.3, +44.4] | 4.52 | 0.0312 | 6/0/0 | 0.0%→33.3% | 0.5000 |
| Full memory (v3) [ablation reference] | overall | 46 | +20.8 pp | +16.7 pp | 23.1 | [+14.2, +27.3] | 0.90 | 0.0000 | 34/4/8 | 2.2%→26.1% | 0.0010 |
| Full memory (v3) [ablation reference] | familiar | 20 | +31.9 pp | +25.0 pp | 21.0 | [+23.4, +41.3] | 1.52 | 0.0001 | 19/0/1 | 5.0%→45.0% | 0.0078 |
| Full memory (v3) [ablation reference] | new | 20 | +5.0 pp | +0.0 pp | 18.6 | [-3.1, +12.7] | 0.27 | 0.1722 | 9/4/7 | 0.0%→5.0% | 1.0000 |
| Full memory (v3) [ablation reference] | negative_control | 6 | +36.1 pp | +33.3 pp | 6.8 | [+33.3, +41.7] | 5.31 | 0.0312 | 6/0/0 | 0.0%→33.3% | 0.5000 |
| No grading (C) | overall | 46 | +8.0 pp | +6.2 pp | 21.8 | [+1.7, +14.3] | 0.37 | 0.0289 | 23/12/11 | 2.2%→8.7% | 0.3750 |
| No grading (C) | familiar | 20 | +11.7 pp | +6.2 pp | 24.4 | [+1.5, +22.3] | 0.48 | 0.0561 | 10/5/5 | 5.0%→10.0% | 1.0000 |
| No grading (C) | new | 20 | +0.0 pp | +0.0 pp | 18.5 | [-7.9, +8.0] | 0.00 | 1.0000 | 7/7/6 | 0.0%→10.0% | 0.5000 |
| No grading (C) | negative_control | 6 | +22.2 pp | +16.7 pp | 13.6 | [+16.7, +33.3] | 1.63 | 0.0312 | 6/0/0 | 0.0%→0.0% | 1.0000 |
| No merge (F) | overall | 46 | +24.6 pp | +28.6 pp | 23.5 | [+17.7, +31.1] | 1.05 | 0.0000 | 35/5/6 | 2.2%→41.3% | 0.0000 |
| No merge (F) | familiar | 20 | +31.1 pp | +28.6 pp | 16.0 | [+24.1, +37.8] | 1.95 | 0.0002 | 18/0/2 | 5.0%→60.0% | 0.0010 |
| No merge (F) | new | 20 | +13.8 pp | +14.3 pp | 28.3 | [+2.0, +26.4] | 0.49 | 0.0521 | 11/5/4 | 0.0%→25.0% | 0.0625 |
| No merge (F) | negative_control | 6 | +38.9 pp | +33.3 pp | 8.6 | [+33.3, +44.4] | 4.52 | 0.0312 | 6/0/0 | 0.0%→33.3% | 0.5000 |
| Full memory (v2) [ablation reference] | overall | 46 | +16.3 pp | +16.7 pp | 21.7 | [+10.1, +22.4] | 0.75 | 0.0000 | 30/7/9 | 2.2%→19.6% | 0.0215 |
| Full memory (v2) [ablation reference] | familiar | 20 | +25.3 pp | +25.0 pp | 20.8 | [+16.5, +34.3] | 1.22 | 0.0004 | 16/1/3 | 5.0%→30.0% | 0.1250 |
| Full memory (v2) [ablation reference] | new | 20 | +3.1 pp | +0.0 pp | 18.4 | [-4.9, +11.0] | 0.17 | 0.3938 | 8/6/6 | 0.0%→10.0% | 0.5000 |
| Full memory (v2) [ablation reference] | negative_control | 6 | +30.6 pp | +33.3 pp | 6.8 | [+25.0, +33.3] | 4.49 | 0.0312 | 6/0/0 | 0.0%→16.7% | 1.0000 |
| Memory reset (G) | overall | 46 | +16.0 pp | +16.7 pp | 22.6 | [+9.7, +22.5] | 0.71 | 0.0001 | 29/6/11 | 2.2%→21.7% | 0.0039 |
| Memory reset (G) | familiar | 20 | +26.9 pp | +25.0 pp | 21.6 | [+17.8, +36.5] | 1.24 | 0.0003 | 17/1/2 | 5.0%→40.0% | 0.0156 |
| Memory reset (G) | new | 20 | +4.2 pp | +0.0 pp | 20.6 | [-4.5, +13.1] | 0.20 | 0.3063 | 7/5/8 | 0.0%→10.0% | 0.5000 |
| Memory reset (G) | negative_control | 6 | +19.4 pp | +16.7 pp | 12.5 | [+11.1, +27.8] | 1.55 | 0.0625 | 5/0/1 | 0.0%→0.0% | 1.0000 |
| Full memory (v4) [ablation reference] | overall | 46 | +21.9 pp | +16.7 pp | 23.3 | [+15.3, +28.5] | 0.94 | 0.0000 | 33/4/9 | 2.2%→28.3% | 0.0005 |
| Full memory (v4) [ablation reference] | familiar | 20 | +32.9 pp | +28.6 pp | 22.0 | [+23.9, +42.7] | 1.50 | 0.0002 | 18/0/2 | 5.0%→55.0% | 0.0020 |
| Full memory (v4) [ablation reference] | new | 20 | +6.7 pp | +0.0 pp | 18.8 | [-1.4, +14.8] | 0.35 | 0.0687 | 9/4/7 | 0.0%→5.0% | 1.0000 |
| Full memory (v4) [ablation reference] | negative_control | 6 | +36.1 pp | +33.3 pp | 6.8 | [+33.3, +41.7] | 5.31 | 0.0312 | 6/0/0 | 0.0%→16.7% | 1.0000 |
| No commit gate (B) vs full v3 | overall | 46 | -0.6 pp | +0.0 pp | 14.1 | [-4.6, +3.4] | -0.04 | 0.6761 | 12/13/21 | 26.1%→30.4% | 0.6875 |
| No grading (C) vs full v3 | overall | 46 | -12.8 pp | -16.7 pp | 19.3 | [-18.2, -7.2] | -0.66 | 0.0004 | 8/32/6 | 26.1%→8.7% | 0.0215 |
| No merge (F) vs full v2 | overall | 46 | +8.3 pp | +6.2 pp | 20.6 | [+2.2, +14.3] | 0.40 | 0.0183 | 23/8/15 | 19.6%→41.3% | 0.0213 |
| Memory reset (G) vs full v4 | overall | 46 | -5.9 pp | -6.2 pp | 17.4 | [-10.6, -0.6] | -0.34 | 0.0127 | 7/23/16 | 28.3%→21.7% | 0.4531 |
| Retrieved vs Full | overall | 46 | +1.0 pp | +0.0 pp | 19.2 | [-4.2, +6.8] | 0.05 | 0.9481 | 11/11/24 | —→— | — |

## Learning curve (validation, 40 tasks)

| Memory version | Lessons | Memory tokens | Rubric (all) | Familiar | New | All-pass | Input tokens/task | Cost/task |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v0 | 0 | 0 | 55.7% | 62.4% | 48.9% | 2.5% | 283,637 | 0.1866 |
| v1 | 52 | 6,144 | 79.3% | 88.9% | 69.8% | 32.5% | 778,051 | 0.5041 |
| v2 | 44 | 5,815 | 76.8% | 91.4% | 62.3% | 32.5% | 679,970 | 0.4419 |
| v3 | 35 | 5,247 | 76.4% | 88.0% | 64.8% | 27.5% | 706,844 | 0.4604 |
| v4 | 38 | 7,034 | 79.1% | 92.2% | 66.1% | 40.0% | 744,772 | 0.4843 |
| v5 | 34 | 7,567 | 75.4% | 87.3% | 63.5% | 27.5% | 709,101 | 0.4630 |
| v6 | 29 | 7,247 | 73.9% | 90.6% | 57.1% | 27.5% | 803,681 | 0.5225 |
| v7 | 31 | 8,612 | 76.0% | 86.8% | 65.1% | 25.0% | 884,335 | 0.5737 |
| v8 | 30 | 7,625 | 77.8% | 85.5% | 70.1% | 30.0% | 623,727 | 0.4078 |
| v9 | 24 | 7,032 | 72.0% | 87.0% | 57.0% | 30.0% | 585,559 | 0.3825 |
| v10 | 31 | 7,926 | 75.3% | 85.0% | 65.5% | 22.5% | 637,437 | 0.4159 |

## Memory growth (main lineage)

| Version | Active | Added | Modified | Removed | Rejected | Review queue | Avg words | Memory tokens | Checklist / Practice | Leakage hard / soft |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| v0 | 0 | — | — | — | — | — | 0.0 | 0 | 0 / 0 | 0 / 0 |
| v1 | 52 | 61 | 39 | 9 | 26 | 114 | 58.2 | 6,144 | 29 / 23 | 0 / 0 |
| v2 | 44 | 23 | 28 | 31 | 104 | 52 | 65.3 | 5,815 | 31 / 13 | 0 / 3 |
| v3 | 35 | 11 | 18 | 20 | 122 | 35 | 76.1 | 5,247 | 24 / 11 | 0 / 2 |
| v4 | 38 | 15 | 17 | 12 | 118 | 44 | 95.1 | 7,034 | 26 / 12 | 0 / 1 |
| v5 | 34 | 22 | 17 | 26 | 128 | 35 | 114.6 | 7,567 | 22 / 12 | 0 / 2 |
| v6 | 29 | 12 | 10 | 17 | 129 | 50 | 127.8 | 7,247 | 20 / 9 | 0 / 3 |
| v7 | 31 | 18 | 20 | 16 | 125 | 25 | 142.7 | 8,612 | 21 / 10 | 0 / 5 |
| v8 | 30 | 8 | 0 | 9 | 127 | 40 | 130.7 | 7,625 | 19 / 11 | 0 / 5 |
| v9 | 24 | 7 | 4 | 13 | 131 | 28 | 151.0 | 7,032 | 16 / 8 | 0 / 4 |
| v10 | 31 | 15 | 1 | 8 | 138 | 23 | 131.8 | 7,926 | 21 / 10 | 0 / 6 |

## Retrieval K sweep (validation)

| K | Rubric pass | All-pass | Input tokens/task | Cost/task |
|---:|---:|---:|---:|---:|
| 3 | 61.0% | 7.5% | 244,763 | 0.1644 |
| 5 | 62.8% | 12.5% | 306,859 | 0.2054 |
| 10 | 70.6% | 20.0% | 546,562 | 0.3625 |
| 20 | 70.7% | 15.0% | 562,889 | 0.3723 |
| 50 | 76.1% | 30.0% | 688,435 | 0.4492 |

K* = 50 (max validation rubric pass rate (3 d.p.), ties -> lower cost)

## Behaviour (test, per task)

| Condition | Tool calls | Research | Analysis | Drafting | Editing | Verification | Doc reads | Searches | Calculations | Draft revisions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Vanilla | 23.0 | 8.6 | 3.9 | 1.0 | 3.9 | 4.6 | 4.3 | 4.8 | 5.2 | 4.9 |
| Full memory (v10) | 31.8 | 8.5 | 7.6 | 1.0 | 8.1 | 5.8 | 4.2 | 4.7 | 10.6 | 9.1 |
| Retrieved memory (K=50) | 31.0 | 8.8 | 8.3 | 1.0 | 7.5 | 4.7 | 4.2 | 4.7 | 10.3 | 8.5 |
| Budget-matched full memory | 20.3 | 8.7 | 7.5 | 1.0 | 1.3 | 1.2 | 4.4 | 3.5 | 7.8 | 2.3 |
| Oracle (partner guidance) | 27.2 | 8.9 | 8.4 | 1.0 | 3.8 | 4.3 | 4.7 | 4.8 | 9.8 | 4.8 |
| Placebo memory (A) | 24.6 | 9.5 | 4.3 | 1.0 | 4.1 | 4.9 | 4.8 | 5.5 | 5.9 | 5.1 |
| No commit gate (B) | 35.5 | 9.9 | 7.7 | 1.0 | 8.9 | 7.2 | 4.9 | 6.7 | 10.6 | 9.9 |
| Full memory (v3) [ablation reference] | 33.8 | 9.3 | 7.2 | 1.0 | 8.3 | 7.2 | 4.8 | 5.3 | 10.5 | 9.3 |
| No grading (C) | 27.8 | 10.5 | 5.4 | 1.0 | 6.5 | 3.5 | 4.4 | 6.4 | 5.8 | 7.5 |
| No merge (F) | 29.4 | 7.5 | 6.6 | 1.0 | 7.3 | 6.1 | 4.3 | 4.0 | 9.3 | 8.3 |
| Full memory (v2) [ablation reference] | 36.6 | 9.2 | 7.7 | 1.0 | 9.3 | 8.5 | 4.6 | 6.4 | 11.4 | 10.3 |
| Memory reset (G) | 34.9 | 10.4 | 8.0 | 1.0 | 9.8 | 4.7 | 5.1 | 5.7 | 9.5 | 10.8 |
| Full memory (v4) [ablation reference] | 35.1 | 8.9 | 8.3 | 1.0 | 9.4 | 6.5 | 4.3 | 5.1 | 11.3 | 10.4 |

## Judge robustness

| Condition | Both-pass rubric | Judge 1 only | Judge 2 only | Criterion agreement |
|---|---:|---:|---:|---:|
| Vanilla | 54.7% | 59.1% | 60.6% | 89.8% |
| Full memory (v10) | 78.4% | 81.7% | 80.8% | 94.3% |
| Retrieved memory (K=50) | 79.5% | 84.6% | 80.8% | 93.5% |
| Budget-matched full memory | 71.4% | 73.6% | 73.7% | 95.5% |
| Oracle (partner guidance) | 68.1% | 70.3% | 71.4% | 94.4% |
| Placebo memory (A) | 53.6% | 58.6% | 61.9% | 86.7% |
| No commit gate (B) | 74.9% | 79.1% | 77.2% | 93.5% |
| Full memory (v3) [ablation reference] | 75.5% | 79.4% | 77.2% | 94.5% |
| No grading (C) | 62.7% | 67.5% | 69.6% | 88.5% |
| No merge (F) | 79.3% | 81.5% | 82.1% | 95.0% |
| Full memory (v2) [ablation reference] | 71.1% | 75.7% | 75.0% | 91.5% |
| Memory reset (G) | 70.8% | 76.8% | 73.0% | 91.8% |
| Full memory (v4) [ablation reference] | 76.7% | 81.5% | 78.9% | 93.0% |

All graded criterion pairs: n=25078, raw agreement 92.2%, Cohen's κ = 0.754
