"""Build summary.json, metrics.csv, task_results.jsonl, plots and REPORT.md from cached results.

Usage: python -m analysis.reports [--config config/base.yaml]
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.plots import bar_chart, line_chart, memory_evolution  # noqa: E402
from common.config import load_config, results_root  # noqa: E402
from common.io import read_json, read_jsonl, write_json, write_jsonl  # noqa: E402
from evaluation.leakage import scan_memory  # noqa: E402
from evaluation.metrics import by_group, condition_metrics  # noqa: E402
from evaluation.statistics import cohen_kappa, mcnemar, paired  # noqa: E402
from memory.store import Memory, memory_tokens, render_memory  # noqa: E402

DATE_WORDS = re.compile(r"deadline|date|day|period|calendar|business day|weekend|duration|expir", re.I)


def pct(x: float | None, d: int = 1) -> str:
    return "—" if x is None else f"{100 * x:.{d}f}%"


def num(x: float | None, d: int = 0) -> str:
    return "—" if x is None else f"{x:,.{d}f}"


def load_eval(root: Path) -> dict[str, list[dict[str, Any]]]:
    out = {}
    for p in sorted((root / "eval_rows").glob("*.jsonl")):
        out[p.stem.replace("__", "/")] = read_jsonl(p)
    return out


def scores(rows: list[dict[str, Any]], key: str = "rubric_score") -> dict[str, Any]:
    return {r["task_id"]: r[key] for r in rows if key in r}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/base.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    root = results_root(cfg)
    plots = root / "plots"
    ev = load_eval(root)
    summary: dict[str, Any] = {"experiment_id": cfg["experiment_id"]}

    # ------------------------------------------------------------ conditions on test
    mem_versions = sorted(int(p.stem.split("_v")[1]) for p in (root / "memory" / "main").glob("memory_v*.json")
                          if "_diff" not in p.stem)
    vfinal = max(mem_versions) if mem_versions else 0
    kinfo = read_json(root / "retrieval" / "k_sweep_validation.json") if (root / "retrieval" / "k_sweep_validation.json").exists() else {}
    kstar = kinfo.get("k_star")
    named = {
        "Vanilla": "eval/test/vanilla",
        f"Full memory (v{vfinal})": f"eval/test/full_v{vfinal}",
        f"Retrieved memory (K={kstar})": f"eval/test/retrieved_v{vfinal}_k{kstar}",
        "Budget-matched full memory": f"eval/test/budget_matched_v{vfinal}",
        "Oracle (partner guidance)": "eval/test/oracle",
        "Placebo memory (A)": "eval/test/placebo",
    }
    for ab, lab in [("no_commit_gate", "No commit gate (B)"), ("no_grading", "No grading (C)"),
                    ("no_merge", "No merge (F)"), ("memory_reset", "Memory reset (G)")]:
        hits = [k for k in ev if k.startswith(f"eval/test/ablation_{ab}_v")]
        if hits:
            v = int(hits[0].rsplit("_v", 1)[1])
            named[lab] = hits[0]
            named.setdefault(f"Full memory (v{v}) [ablation reference]", f"eval/test/full_v{v}")
    conds = {lab: ev[k] for lab, k in named.items() if k in ev}
    summary["test_conditions"] = {lab: condition_metrics(r) for lab, r in conds.items()}
    summary["test_by_cohort"] = {lab: by_group(r, "cohort") for lab, r in conds.items()}
    summary["test_by_task_type"] = {lab: by_group(r, "task_type") for lab, r in conds.items()}

    # ------------------------------------------------------------ paired statistics vs vanilla
    stats_out: dict[str, Any] = {}
    van = conds.get("Vanilla", [])
    for lab, rows in conds.items():
        if lab == "Vanilla" or not van:
            continue
        entry = {"overall": {"rubric": paired(scores(van), scores(rows)),
                             "all_pass": mcnemar(scores(van, "all_pass"), scores(rows, "all_pass"))}}
        for coh in ("familiar", "new", "negative_control"):
            a = [r for r in van if r["cohort"] == coh]
            b = [r for r in rows if r["cohort"] == coh]
            entry[coh] = {"rubric": paired(scores(a), scores(b)), "all_pass": mcnemar(scores(a, "all_pass"), scores(b, "all_pass"))}
        stats_out[lab] = entry
    # Ablations vs their matched-cycle full-memory reference
    for lab in list(conds):
        m = re.match(r".*\((B|C|F|G)\)$", lab)
        if m:
            v = int(named[lab].rsplit("_v", 1)[1])
            ref = conds.get(f"Full memory (v{v}) [ablation reference]")
            if ref:
                stats_out[f"{lab} vs full v{v}"] = {"overall": {"rubric": paired(scores(ref), scores(conds[lab])),
                                                                "all_pass": mcnemar(scores(ref, "all_pass"), scores(conds[lab], "all_pass"))}}
    full_lab = f"Full memory (v{vfinal})"
    ret_lab = f"Retrieved memory (K={kstar})"
    if full_lab in conds and ret_lab in conds:
        stats_out["Retrieved vs Full"] = {"overall": {
            "rubric": paired(scores(conds[full_lab]), scores(conds[ret_lab])),
            "cost": paired(scores(conds[full_lab], "cost_usd"), scores(conds[ret_lab], "cost_usd")),
            "input_tokens": paired(scores(conds[full_lab], "input_tokens"), scores(conds[ret_lab], "input_tokens"))}}
    summary["statistics"] = stats_out

    # ------------------------------------------------------------ learning curve (validation)
    curve = []
    cyc_dir = root / "cycles" / "main"
    for p in sorted(cyc_dir.glob("cycle_*_validation_rows.jsonl")):
        c = int(p.stem.split("_")[1])
        rows = read_jsonl(p)
        curve.append({"memory_version": c - 1, "rows": rows})
    fin = root / "trajectories" / "main" / f"final_v{vfinal}" / "validation"
    fin_rows = read_jsonl(cyc_dir / "final_validation_rows.jsonl")
    if not fin_rows and fin.exists():
        from experiments.common import make_row
        from grading.aggregation import aggregate
        from grading.rubric import load_rubric, load_tasks
        tasks = {t["task_id"]: t for t in load_tasks("validation")}
        for tp in sorted(fin.glob("*.json")):
            r = read_json(tp)
            gp = root / "grades" / "main" / f"final_v{vfinal}" / "validation" / tp.name
            g = None
            if gp.exists():
                t = tasks[r["task_id"]]
                g = aggregate(t, load_rubric(t), read_json(gp)["judgements"], rule=cfg["grading"]["aggregation"])
            fin_rows.append(make_row(r, g, f"main_v{vfinal}"))
        write_jsonl(cyc_dir / "final_validation_rows.jsonl", fin_rows)
    if fin_rows:
        curve.append({"memory_version": vfinal, "rows": fin_rows})
    lc = []
    for pt in curve:
        m_all = condition_metrics(pt["rows"])
        coh = by_group(pt["rows"], "cohort")
        mem = Memory.from_json(read_json(root / "memory" / "main" / f"memory_v{pt['memory_version']}.json"))
        lc.append({"memory_version": pt["memory_version"], "overall": m_all,
                   "familiar": coh.get("familiar", {}), "new": coh.get("new", {}),
                   "n_lessons": len(mem.active()), "memory_tokens": memory_tokens(render_memory(mem.active()))})
    summary["learning_curve_validation"] = [{k: v for k, v in x.items()} for x in lc]
    if lc:
        base = lc[0]
        xs = [x["memory_version"] for x in lc]
        line_chart(plots / "learning_curve_rubric.svg", "Validation rubric pass rate by wake-sleep cycle",
                   {"Familiar matters": [(x["memory_version"], x["familiar"].get("rubric_pass_rate")) for x in lc],
                    "New matters": [(x["memory_version"], x["new"].get("rubric_pass_rate")) for x in lc],
                    "All": [(x["memory_version"], x["overall"].get("rubric_pass_rate")) for x in lc]},
                   "memory version (cycles of sleep)", "rubric pass rate")
        line_chart(plots / "learning_curve_gain.svg", "Gain in rubric pass rate over vanilla (validation)",
                   {"Familiar matters": [(x["memory_version"], (x["familiar"].get("rubric_pass_rate") or 0) - (base["familiar"].get("rubric_pass_rate") or 0)) for x in lc],
                    "New matters": [(x["memory_version"], (x["new"].get("rubric_pass_rate") or 0) - (base["new"].get("rubric_pass_rate") or 0)) for x in lc]},
                   "memory version", "Δ rubric pass rate")
        line_chart(plots / "learning_curve_all_pass.svg", "Validation all-pass rate by cycle",
                   {"Familiar": [(x["memory_version"], x["familiar"].get("all_pass_rate")) for x in lc],
                    "New": [(x["memory_version"], x["new"].get("all_pass_rate")) for x in lc],
                    "All": [(x["memory_version"], x["overall"].get("all_pass_rate")) for x in lc]},
                   "memory version", "all-pass rate")
        line_chart(plots / "memory_size.svg", "Memory size by version",
                   {"active lessons": [(x["memory_version"], x["n_lessons"]) for x in lc]}, "memory version", "lessons")
        line_chart(plots / "cost_tokens_by_cycle.svg", "Agent tokens per validation task by memory version",
                   {"input tokens": [(x["memory_version"], x["overall"].get("input_tokens_per_task")) for x in lc],
                    "total tokens": [(x["memory_version"], x["overall"].get("total_tokens_per_task")) for x in lc]},
                   "memory version", "tokens / task")
        line_chart(plots / "cost_by_cycle.svg", "Agent cost per validation task by memory version",
                   {"cost (USD)": [(x["memory_version"], x["overall"].get("cost_usd_per_task")) for x in lc]},
                   "memory version", "USD / task")
        del xs

    # ------------------------------------------------------------ training curve + forgetting
    train_curve = []
    for p in sorted(cyc_dir.glob("cycle_*_train_rows.jsonl")):
        c = int(p.stem.split("_")[1])
        rows = read_jsonl(p)
        train_curve.append({"cycle": c, "memory_version": c - 1, "overall": condition_metrics(rows),
                            "by_task_type": {k: v.get("rubric_pass_rate") for k, v in by_group(rows, "task_type").items()}})
    summary["training_curve"] = train_curve
    if train_curve:
        tts = sorted({t for x in train_curve for t in x["by_task_type"]})
        line_chart(plots / "forgetting_by_task_type_train.svg", "Training rubric pass rate by task type (forgetting test)",
                   {t: [(x["memory_version"], x["by_task_type"].get(t)) for x in train_curve] for t in tts},
                   "memory version used in wake", "rubric pass rate")
        val_tt = []
        for x in curve:
            val_tt.append({"v": x["memory_version"], "tt": {k: v.get("rubric_pass_rate") for k, v in by_group(x["rows"], "task_type").items()}})
        summary["validation_by_task_type_curve"] = val_tt
        dec = {}
        for t in tts:
            seq = [x["by_task_type"].get(t) for x in train_curve if x["by_task_type"].get(t) is not None]
            if len(seq) >= 2:
                peak = max(seq)
                dec[t] = {"first": seq[0], "peak": peak, "last": seq[-1], "drop_from_peak": peak - seq[-1]}
        summary["forgetting"] = dec

    # ------------------------------------------------------------ memory growth + leakage + lifecycle
    growth = []
    for v in mem_versions:
        mj = read_json(root / "memory" / "main" / f"memory_v{v}.json")
        mem = Memory.from_json(mj)
        act = mem.active()
        dp = root / "memory" / "main" / f"memory_v{v}_diff.json"
        d = read_json(dp) if dp.exists() else {}
        leak = scan_memory(act)
        growth.append({"version": v, "n_active": len(act), **(d.get("counts") or {}),
                       "avg_lesson_words": (sum(len(l["text"].split()) for l in act) / len(act)) if act else 0,
                       "memory_tokens": memory_tokens(render_memory(act)),
                       "n_checklist": sum(l["type"] == "checklist" for l in act),
                       "n_practice_note": sum(l["type"] == "practice_note" for l in act),
                       "by_category": {c: sum(l["category"] == c for l in act) for c in ("general", "analysis", "drafting", "review")},
                       "leakage_hard": leak["n_hard"], "leakage_soft_only": leak["n_soft_only"],
                       "helpfulness": d.get("helpfulness_feedback")})
    summary["memory_growth"] = growth
    if mem_versions:
        final_mem = Memory.from_json(read_json(root / "memory" / "main" / f"memory_v{vfinal}.json"))
        summary["final_memory_leakage"] = scan_memory(final_mem.active())
        lessons = sorted(final_mem.lessons.values(), key=lambda l: (-len(l["history"]), l["lesson_id"]))
        summary["most_revised_lessons"] = [{"lesson_id": l["lesson_id"], "status": l["status"], "history": l["history"]}
                                           for l in lessons[:5]]
        dl = [l for l in final_mem.active() if DATE_WORDS.search(l["text"])]
        summary["deadline_lesson_example"] = sorted(dl, key=lambda l: -len(l["history"]))[:1]
        summary["top_helpful_lessons"] = sorted(
            [{"lesson_id": l["lesson_id"], "text": l["text"], "helpful": l["times_helpful"], "harmful": l["times_harmful"],
              "retrieved": l["times_retrieved"]} for l in final_mem.active()], key=lambda x: -x["helpful"])[:10]
        memory_evolution(plots / "memory_evolution.svg",
                         [read_json(root / "memory" / "main" / f"memory_v{v}.json") for v in mem_versions if v > 0])

    # ------------------------------------------------------------ ablation-lineage memory stats
    ab_mem = {}
    for d in sorted((root / "memory").glob("ablation_*")):
        vs = sorted(int(p.stem.split("_v")[1]) for p in d.glob("memory_v*.json") if "_diff" not in p.stem)
        if vs:
            m = Memory.from_json(read_json(d / f"memory_v{vs[-1]}.json"))
            ab_mem[d.name] = {"version": vs[-1], "n_active": len(m.active()),
                              "memory_tokens": memory_tokens(render_memory(m.active())),
                              "leakage": {k: v for k, v in scan_memory(m.active()).items() if k != "flagged"}}
    summary["ablation_memories"] = ab_mem

    # ------------------------------------------------------------ K sweep
    if kinfo:
        summary["k_sweep_validation"] = kinfo
        ks = sorted(int(k) for k in kinfo["results"])
        r = kinfo["results"]
        line_chart(plots / "k_sweep_quality.svg", "Retrieved memory: validation rubric pass rate vs K",
                   {"rubric pass rate": [(k, r[str(k)]["rubric_pass_rate"] if str(k) in r else r[k]["rubric_pass_rate"]) for k in ks]},
                   "K (lessons retrieved)", "rubric pass rate")
        line_chart(plots / "k_sweep_tokens.svg", "Retrieved memory: input tokens per task vs K",
                   {"input tokens / task": [(k, (r.get(str(k)) or r.get(k))["input_tokens_per_task"]) for k in ks]},
                   "K", "input tokens / task")

    # ------------------------------------------------------------ negative control: what is retrieved for research tasks
    if kstar:
        neg = []
        rdir = root / "retrieval" / f"retrieved_v{vfinal}_k{kstar}"
        if rdir.exists() and mem_versions:
            fm = Memory.from_json(read_json(root / "memory" / "main" / f"memory_v{vfinal}.json"))
            date_ids = {l["lesson_id"] for l in fm.active() if DATE_WORDS.search(l["text"])}
            share_date = {"negative_control": [], "other": []}
            for p in rdir.glob("*.json"):
                tr = read_json(p)
                sel = tr.get("selected", [])
                frac = sum(1 for s in sel if s in date_ids) / max(1, len(sel))
                share_date["negative_control" if p.stem.startswith("RES_") else "other"].append(frac)
            neg = {k: (sum(v) / len(v) if v else None) for k, v in share_date.items()}
            neg["date_lessons_in_memory_share"] = len(date_ids) / max(1, len(fm.active()))
        summary["negative_control_retrieval"] = neg

    # ------------------------------------------------------------ judge robustness (one vs two judges)
    jr = {}
    for lab, rows in conds.items():
        g = [r for r in rows if "judge_1_rubric_score" in r]
        if g:
            jr[lab] = {"both_pass": sum(r["rubric_score"] for r in g) / len(g),
                       "judge_1_only": sum(r["judge_1_rubric_score"] for r in g) / len(g),
                       "judge_2_only": sum(r["judge_2_rubric_score"] for r in g) / len(g),
                       "criterion_agreement": sum(r["judge_agreement"] for r in g) / len(g)}
    x1, x2 = [], []
    for p in (root / "grades").rglob("*.json"):
        js = read_json(p).get("judgements", [])
        if len(js) == 2:
            a = {r["criterion_id"]: r["result"] == "PASS" for r in js[0]["results"]}
            b = {r["criterion_id"]: r["result"] == "PASS" for r in js[1]["results"]}
            for cid in a:
                if cid in b:
                    x1.append(a[cid])
                    x2.append(b[cid])
    jr["_all_grades"] = {"n_criterion_verdict_pairs": len(x1), "raw_agreement": sum(a == b for a, b in zip(x1, x2)) / max(1, len(x1)),
                         "cohen_kappa": cohen_kappa(x1, x2),
                         "judge_1_pass_rate": sum(x1) / max(1, len(x1)), "judge_2_pass_rate": sum(x2) / max(1, len(x2))}
    if "Vanilla" in conds and full_lab in conds:
        for j in ("judge_1", "judge_2"):
            jr[f"delta_full_vs_vanilla_{j}_only"] = paired(scores(conds["Vanilla"], f"{j}_rubric_score"),
                                                          scores(conds[full_lab], f"{j}_rubric_score"))
    summary["judge_robustness"] = jr

    # ------------------------------------------------------------ total experiment cost
    tot = defaultdict(float)
    for p in (root / "trajectories").rglob("*.json"):
        r = read_json(p)
        tot["agent_runs"] += 1
        tot["agent_input_tokens"] += r.get("input_tokens", 0)
        tot["agent_output_tokens"] += r.get("output_tokens", 0)
        tot["agent_cost_usd"] += r.get("cost_usd", 0)
    for p in (root / "grades").rglob("*.json"):
        for j in read_json(p).get("judgements", []):
            tot["judge_calls"] += 1
            tot["judge_input_tokens"] += j["input_tokens"]
            tot["judge_cost_usd"] += j["cost_usd"]
    for p in (root / "lessons").rglob("reviews/*.json"):
        r = read_json(p)
        tot["sleep_reviews"] += 1
        tot["sleep_cost_usd"] += r.get("cost_usd", 0)
    summary["experiment_totals"] = dict(tot)

    # ------------------------------------------------------------ behaviour plot + criterion-source plot
    if conds:
        labs = list(conds)
        keys = ["research_actions", "analysis_actions", "drafting_actions", "editing_actions", "verification_actions"]
        bar_chart(plots / "behaviour_tool_calls.svg", "Tool calls per held-out task by action class",
                  [k.replace("_actions", "") for k in keys],
                  {lab: [summary["test_conditions"][lab].get(f"{k}_per_task") for k in keys]
                   for lab in labs if lab in ("Vanilla", full_lab, ret_lab)}, "calls / task", fmt="{:.1f}")
        bar_chart(plots / "main_results_rubric.svg", "Held-out test rubric pass rate by condition", labs,
                  {"rubric pass rate": [summary["test_conditions"][l].get("rubric_pass_rate") for l in labs]}, "rubric pass rate")
        bar_chart(plots / "main_results_all_pass.svg", "Held-out test all-pass rate by condition", labs,
                  {"all-pass rate": [summary["test_conditions"][l].get("all_pass_rate") for l in labs]}, "all-pass rate")
        if "Vanilla" in conds and full_lab in conds:
            srcs = sorted(set(summary["test_conditions"]["Vanilla"]["pass_rate_by_criterion_source"])
                          | set(summary["test_conditions"][full_lab]["pass_rate_by_criterion_source"]))
            bar_chart(plots / "criterion_source_gain.svg", "Test pass rate by rubric criterion source", srcs,
                      {lab: [summary["test_conditions"][lab]["pass_rate_by_criterion_source"].get(s) for s in srcs]
                       for lab in ("Vanilla", full_lab)}, "pass rate", w=1100)

    # ------------------------------------------------------------ files
    all_rows = [dict(r, eval_name=name) for name, rows in ev.items() for r in rows]
    for p in sorted(cyc_dir.glob("cycle_*_rows.jsonl")):
        all_rows += [dict(r, eval_name=f"main/{p.stem}") for r in read_jsonl(p)]
    write_jsonl(root / "task_results.jsonl", all_rows)
    flat_keys = ["eval_name", "condition", "task_id", "split", "cohort", "practice_area", "task_type", "memory_mode",
                 "memory_version", "retrieval_k", "rubric_score", "all_pass", "n_passed", "n_criteria",
                 "house_standard_score", "substantive_score", "judge_agreement", "judge_1_rubric_score",
                 "judge_2_rubric_score", "input_tokens", "output_tokens", "total_tokens", "cost_usd", "latency_ms",
                 "steps", "tool_calls", "research_actions", "analysis_actions", "drafting_actions", "editing_actions",
                 "verification_actions", "n_memory_lessons", "memory_tokens", "budget_hit", "deliverable_words"]
    with open(root / "metrics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=flat_keys, extrasaction="ignore")
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    write_json(root / "summary.json", summary)
    (root / "REPORT_TABLES.md").write_text(render_tables(summary, conds, full_lab, ret_lab))
    print(f"wrote {root / 'summary.json'}, metrics.csv ({len(all_rows)} rows), plots/, REPORT_TABLES.md")


def render_tables(s: dict[str, Any], conds: dict[str, Any], full_lab: str, ret_lab: str) -> str:
    out = ["# Wake-sleep experiment — generated tables", ""]
    tc = s["test_conditions"]
    out += ["## Main results (held-out test, 46 tasks)", "",
            "| Condition | All-pass | Rubric pass | House-std pass | Substantive pass | Tokens/task | Cost/task (USD, assumed prices) | Latency (s) | Tool calls |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for lab, m in tc.items():
        out.append(f"| {lab} | {pct(m.get('all_pass_rate'))} | {pct(m.get('rubric_pass_rate'))} | "
                   f"{pct(m.get('house_standard_pass_rate'))} | {pct(m.get('substantive_pass_rate'))} | "
                   f"{num(m.get('total_tokens_per_task'))} | {num(m.get('cost_usd_per_task'), 4)} | "
                   f"{num(m.get('latency_s_per_task'), 0)} | {num(m.get('tool_calls_per_task'), 1)} |")
    out += ["", "## Generalization (test, rubric pass rate)", "",
            "| Condition | Familiar | New matters | Negative control | Δ Familiar | Δ New |", "|---|---:|---:|---:|---:|---:|"]
    vb = s["test_by_cohort"].get("Vanilla", {})
    for lab, g in s["test_by_cohort"].items():
        f, n, nc = (g.get(k, {}).get("rubric_pass_rate") for k in ("familiar", "new", "negative_control"))
        df = None if lab == "Vanilla" or f is None else f - vb.get("familiar", {}).get("rubric_pass_rate", 0)
        dn = None if lab == "Vanilla" or n is None else n - vb.get("new", {}).get("rubric_pass_rate", 0)
        out.append(f"| {lab} | {pct(f)} | {pct(n)} | {pct(nc)} | {'—' if df is None else f'{100 * df:+.1f} pp'} | "
                   f"{'—' if dn is None else f'{100 * dn:+.1f} pp'} |")
    out += ["", "## Paired statistics vs vanilla (per-task rubric score difference; McNemar on all-pass)", "",
            "| Comparison | Subset | n | Mean Δ | Median Δ | SD | 95% CI | Cohen dz | Wilcoxon p | improved/worse/tied | all-pass A→B | McNemar p |",
            "|---|---|---:|---:|---:|---:|---|---:|---:|---|---|---:|"]
    for lab, e in s["statistics"].items():
        for sub, v in e.items():
            r = v.get("rubric")
            if not r or not r.get("n"):
                continue
            d = r["diff"]
            ap = v.get("all_pass") or {}
            out.append(f"| {lab} | {sub} | {r['n']} | {100 * d['mean']:+.1f} pp | {100 * d['median']:+.1f} pp | "
                       f"{100 * d['sd']:.1f} | [{100 * d['ci95_low']:+.1f}, {100 * d['ci95_high']:+.1f}] | "
                       f"{r['cohens_dz']:.2f} | {r['wilcoxon_p'] if r['wilcoxon_p'] is None else f'{r['wilcoxon_p']:.4f}'} | "
                       f"{r['n_improved']}/{r['n_worse']}/{r['n_tied']} | "
                       f"{pct(ap.get('rate_a'))}→{pct(ap.get('rate_b'))} | {num(ap.get('p_exact'), 4) if ap else '—'} |")
    out += ["", "## Learning curve (validation, 40 tasks)", "",
            "| Memory version | Lessons | Memory tokens | Rubric (all) | Familiar | New | All-pass | Input tokens/task | Cost/task |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for x in s.get("learning_curve_validation", []):
        o = x["overall"]
        out.append(f"| v{x['memory_version']} | {x['n_lessons']} | {num(x['memory_tokens'])} | {pct(o.get('rubric_pass_rate'))} | "
                   f"{pct(x['familiar'].get('rubric_pass_rate'))} | {pct(x['new'].get('rubric_pass_rate'))} | "
                   f"{pct(o.get('all_pass_rate'))} | {num(o.get('input_tokens_per_task'))} | {num(o.get('cost_usd_per_task'), 4)} |")
    out += ["", "## Memory growth (main lineage)", "",
            "| Version | Active | Added | Modified | Removed | Rejected | Review queue | Avg words | Memory tokens | Checklist / Practice | Leakage hard / soft |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for g in s.get("memory_growth", []):
        out.append(f"| v{g['version']} | {g['n_active']} | {g.get('added', '—')} | {g.get('modified', '—')} | {g.get('removed', '—')} | "
                   f"{g.get('rejected', '—')} | {g.get('review_queue', '—')} | {g['avg_lesson_words']:.1f} | {num(g['memory_tokens'])} | "
                   f"{g['n_checklist']} / {g['n_practice_note']} | {g['leakage_hard']} / {g['leakage_soft_only']} |")
    if s.get("k_sweep_validation"):
        out += ["", "## Retrieval K sweep (validation)", "", "| K | Rubric pass | All-pass | Input tokens/task | Cost/task |", "|---:|---:|---:|---:|---:|"]
        for k, m in sorted(s["k_sweep_validation"]["results"].items(), key=lambda kv: int(kv[0])):
            out.append(f"| {k} | {pct(m['rubric_pass_rate'])} | {pct(m['all_pass_rate'])} | {num(m['input_tokens_per_task'])} | {num(m['cost_per_task'], 4)} |")
        out.append(f"\nK* = {s['k_sweep_validation']['k_star']} ({s['k_sweep_validation']['rule']})")
    out += ["", "## Behaviour (test, per task)", "",
            "| Condition | Tool calls | Research | Analysis | Drafting | Editing | Verification | Doc reads | Searches | Calculations | Draft revisions |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for lab, m in tc.items():
        out.append(f"| {lab} | " + " | ".join(num(m.get(f"{k}_per_task"), 1) for k in (
            "tool_calls", "research_actions", "analysis_actions", "drafting_actions", "editing_actions",
            "verification_actions", "n_read_document", "n_search_documents", "n_calculate", "draft_revisions")) + " |")
    jr = s.get("judge_robustness", {})
    if jr:
        out += ["", "## Judge robustness", "", "| Condition | Both-pass rubric | Judge 1 only | Judge 2 only | Criterion agreement |", "|---|---:|---:|---:|---:|"]
        for lab, v in jr.items():
            if lab.startswith("_") or lab.startswith("delta"):
                continue
            out.append(f"| {lab} | {pct(v['both_pass'])} | {pct(v['judge_1_only'])} | {pct(v['judge_2_only'])} | {pct(v['criterion_agreement'])} |")
        a = jr.get("_all_grades", {})
        out.append(f"\nAll graded criterion pairs: n={a.get('n_criterion_verdict_pairs')}, raw agreement {pct(a.get('raw_agreement'))}, Cohen's κ = {a.get('cohen_kappa', float('nan')):.3f}")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
