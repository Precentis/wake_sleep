"""Build the synthetic legal benchmark (196 tasks) used by the wake-sleep experiment.

Usage:  python -m data.build_dataset [--config config/base.yaml] [--only TASK_ID] [--workers 16]

Matter facts, planted issues and rubric answers are generated procedurally (issue_library);
an author LLM only writes the prose of each document around the verbatim facts. Every
document is checked for the literal strings the rubric depends on; missing facts trigger a
rewrite and, as a last resort, an appended clause containing the fact verbatim.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import random
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.config import load_config, model_cfg  # noqa: E402
from common.io import read_json, write_json  # noqa: E402
from common.llm import chat  # noqa: E402
from data.issue_library import (  # noqa: E402
    DATE_ISSUES, DELIVERABLE_ASK, DOC_TITLES, HOUSE_STANDARDS, ISSUES, MATTER_FAMILY, PRINCIPAL_DOC,
    RESEARCH_TOPICS, TASK_TYPE_FAMILY, TASK_TYPE_STANDARDS, Planted, fmt_date, fmt_money,
)

DATA = Path(__file__).resolve().parent

CO_PREFIX = ["Arden", "Brightwater", "Calloway", "Dunmore", "Elstree", "Fenwick", "Galloway", "Hartwell", "Ivybridge",
             "Juniper", "Kestrel", "Larkspur", "Merrion", "Northgate", "Oakhurst", "Pemberton", "Quayside", "Redcliffe",
             "Saltash", "Thornbury", "Upton", "Vantage", "Whitlock", "Yarrow", "Ashcombe", "Bellhaven", "Corrib",
             "Delamere", "Eskdale", "Foxley", "Glenrock", "Holloway", "Ingleby", "Kingsmere", "Lowther", "Marlow",
             "Netherby", "Orwell", "Penrith", "Rothley"]
CO_SUFFIX = ["Holdings Ltd", "Technologies Ltd", "Logistics plc", "Foods Ltd", "Medical Ltd", "Analytics Ltd",
             "Energy plc", "Systems Ltd", "Capital LLP", "Industries Ltd", "Software Ltd", "Pharma plc",
             "Robotics Ltd", "Retail Group plc", "Engineering Ltd", "Media Ltd", "Bioscience plc", "Marine Ltd"]
FIRST = ["Amelia", "Rohan", "Priya", "Tobias", "Ines", "Marcus", "Leila", "Callum", "Freya", "Dmitri", "Sana", "Oliver",
         "Nadia", "Henrik", "Zara", "Felix", "Aoife", "Kenji", "Lucia", "Theo", "Mira", "Gareth", "Yusuf", "Elena",
         "Bram", "Chiara", "Idris", "Maeve", "Anton", "Rhea"]
LAST = ["Ashdown", "Bhattacharya", "Cavendale", "Dreyfus", "Ellery", "Fairbairn", "Grosvenor", "Hallam", "Iqbal",
        "Jessop", "Kowalczyk", "Lindqvist", "Montague", "Nakamura", "Okonkwo", "Pryce", "Quennell", "Rosenthal",
        "Sterling", "Thackeray", "Underwood", "Varga", "Wexford", "Yardley", "Zielinski", "Abernethy", "Blackwood",
        "Carrington", "Dalgleish", "Everard"]

MUTATORS = {"mna_escrow_release", "cm_lockup", "com_auto_renewal"}


def _company(rng: random.Random, used: set[str]) -> str:
    while True:
        n = f"{rng.choice(CO_PREFIX)} {rng.choice(CO_SUFFIX)}"
        if n not in used:
            used.add(n)
            return n


def _person(rng: random.Random, used: set[str]) -> str:
    while True:
        n = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if n not in used:
            used.add(n)
            return n


def _today(rng: random.Random) -> dt.date:
    d = dt.date(2026, 1, 5) + dt.timedelta(days=rng.randint(0, 540))
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def task_plan() -> list[dict[str, Any]]:
    """Fixed split: train 110 (M&A), validation 40, test 46 (incl. 6 negative controls)."""
    types = ["issues_list", "legal_memo", "contract_review", "redline", "due_diligence", "timeline_analysis"]
    diffs = ["easy", "medium", "hard"]
    plan: list[dict[str, Any]] = []

    def add(split: str, cohort: str, area: str, n: int, prefix: str) -> None:
        for i in range(n):
            plan.append({
                "split": split, "cohort": cohort, "practice_area": area,
                "task_type": "legal_research" if area == "research" else types[i % len(types)],
                "difficulty": diffs[(i // len(types)) % 3], "prefix": prefix,
            })

    add("train", "training", "corporate_mna", 110, "MNA")
    add("validation", "familiar", "corporate_mna", 20, "MNA")
    add("validation", "new", "capital_markets", 12, "CM")
    add("validation", "new", "commercial_contract", 8, "COM")
    add("test", "familiar", "corporate_mna", 20, "MNA")
    add("test", "new", "capital_markets", 12, "CM")
    add("test", "new", "commercial_contract", 8, "COM")
    add("test", "negative_control", "research", 6, "RES")
    counters: dict[tuple[str, str], int] = {}
    for p in plan:
        key = (p["split"], p["prefix"])
        counters[key] = counters.get(key, 0) + 1
        tag = {"train": "T", "validation": "V", "test": "X"}[p["split"]]
        p["task_id"] = f"{p['prefix']}_{tag}{counters[key]:03d}"
        p["matter_id"] = f"MATTER_{p['task_id']}"
    return plan


def make_matter(p: dict[str, Any], rng: random.Random, used: set[str]) -> dict[str, Any]:
    area = p["practice_area"]
    today = _today(rng)
    c: dict[str, Any] = {"today": today, "customer": _company(rng, used), "claimant": _company(rng, used),
                         "contractor": _company(rng, used), "director": _person(rng, used),
                         "contact": _person(rng, used)}
    if area == "corporate_mna":
        c.update(buyer=_company(rng, used), seller=_company(rng, used), target=_company(rng, used),
                 price=rng.choice(range(20, 260, 5)) * 1_000_000,
                 signing=today - dt.timedelta(days=rng.randint(5, 30)),
                 closing=today + dt.timedelta(days=rng.randint(20, 90)))
        c["client"], c["client_role"] = c["buyer"], "the Buyer"
        c["summary"] = f"{c['buyer']} (the Buyer) is acquiring the entire issued share capital of {c['target']} (the Company) from {c['seller']} (the Seller)."
    elif area == "capital_markets":
        c.update(issuer=_company(rng, used), underwriter=_company(rng, used).replace("Ltd", "Securities").replace("plc", "Securities"),
                 closing=today + dt.timedelta(days=rng.randint(10, 40)))
        c["client"], c["client_role"] = c["issuer"], "the Company (issuer)"
        c["summary"] = f"{c['issuer']} (the Company) is undertaking an initial public offering of ordinary shares underwritten by {c['underwriter']} (the Underwriter)."
    elif area == "commercial_contract":
        c.update(client_co=_company(rng, used), supplier=_company(rng, used),
                 closing=today + dt.timedelta(days=rng.randint(100, 200)))
        c["client"], c["client_role"] = c["client_co"], "the Customer"
        c["summary"] = f"{c['client_co']} (the Customer) receives managed IT services from {c['supplier']} (the Supplier) under a master services agreement."
    else:  # research
        c.update(client=_company(rng, used), client_role="the client")
        c["summary"] = f"{c['client']} has asked a general legal question."
    return c


def choose_issues(p: dict[str, Any], rng: random.Random) -> list:
    pool = list(ISSUES[p["practice_area"]])
    n = {"easy": 3, "medium": 4, "hard": 5}[p["difficulty"]]
    n = min(n, len(pool))
    for _ in range(200):
        pick = rng.sample(pool, n)
        if sum(f.__name__ in MUTATORS for f in pick) > 1:
            continue
        if p["task_type"] == "timeline_analysis":
            probe = [f.__name__ for f in pick]
            dateish = sum(any(k in name for k in ("escrow", "survival", "notice_conflict", "long_stop", "lockup",
                                                   "comfort", "auto_renewal")) for name in probe)
            if dateish < min(2, n):
                continue
        return sorted(pick, key=lambda f: f.__name__ not in MUTATORS)  # mutators first
    return pick


def base_facts(area: str, c: dict[str, Any]) -> dict[str, list[str]]:
    if area == "corporate_mna":
        return {"spa": [f"Parties: {c['buyer']} (Buyer), {c['seller']} (Seller); the Company is {c['target']}.",
                        f"Section 2.1: the Purchase Price is {fmt_money(c['price'])}.",
                        f"This Agreement is dated {fmt_date(c['signing'])}; Closing is scheduled for {fmt_date(c['closing'])} (the 'Closing Date')."]}
    if area == "capital_markets":
        return {"underwriting": [f"Parties: {c['issuer']} (Company) and {c['underwriter']} (Underwriter)."],
                "prospectus": [f"Issuer: {c['issuer']}. The date of this Prospectus is {fmt_date(c['closing'])}."]}
    if area == "commercial_contract":
        return {"msa": [f"Parties: {c['client_co']} (Customer) and {c['supplier']} (Supplier)."]}
    return {}


def build_spec(p: dict[str, Any], seed: int, used: set[str]) -> dict[str, Any]:
    rng = random.Random(f"{seed}:{p['task_id']}")
    local: set[str] = set()  # names unique within a matter; reused across matters (registry keeps all)
    c = make_matter(p, rng, local)
    used |= local
    area = p["practice_area"]
    criteria: list[dict[str, Any]] = []
    facts: dict[str, list[str]] = {}
    must: dict[str, list[str]] = {}
    issues_meta: list[dict[str, Any]] = []

    if area == "research":
        topic = RESEARCH_TOPICS[int(p["task_id"][-3:]) - 1]
        for pt in topic["points"]:
            criteria.append({"text": pt, "kind": "substantive", "source": "research_point"})
        facts["client_email"] = [f"Question from the client: {topic['q']}"]
        facts["research_note"] = [f"Background reading relevant to: {topic['q']} (covers at most two of the expected points, briefly)."]
        must["client_email"] = []
        task_q = topic["q"]
        std_pool = TASK_TYPE_STANDARDS["legal_research"]
        triggered: dict[str, str] = {}
        research_points = topic["points"]
    else:
        task_q = None
        research_points = []
        for doc, fl in base_facts(area, c).items():
            facts.setdefault(doc, []).extend(fl)
        triggered = {}
        for fn in choose_issues(p, rng):
            pl: Planted = fn(rng, c)
            for doc, fl in pl.facts.items():
                facts.setdefault(doc, []).extend(fl)
            for doc, ml in pl.must_contain.items():
                must.setdefault(doc, []).extend(ml)
            for cr in pl.criteria:
                criteria.append({"text": cr, "kind": "substantive", "source": pl.issue})
            for h, txt in pl.standard_criteria.items():
                triggered.setdefault(h, txt)
            issues_meta.append({"issue": pl.issue, "kind": pl.kind, "standards": pl.standards})
        if area == "corporate_mna":  # base facts may have shifted if a mutator moved the closing date
            facts["spa"][2] = f"This Agreement is dated {fmt_date(c['signing'])}; Closing is scheduled for {fmt_date(c['closing'])} (the 'Closing Date')."
        if area == "capital_markets":
            facts["prospectus"][0] = f"Issuer: {c['issuer']}. The date of this Prospectus is {fmt_date(c['closing'])}."
        std_pool = TASK_TYPE_STANDARDS[p["task_type"]]
        facts.setdefault(PRINCIPAL_DOC[area], [])
        facts.setdefault("client_email", [])

    # House-standard criteria: up to 3, preferring concrete issue-triggered ones in the task-type pool,
    # then any triggered H3/H4/H10 (experts always expect arithmetic and date work shown), then generic.
    chosen: list[tuple[str, str]] = []
    for h in std_pool:
        if h in triggered and len(chosen) < 2:
            chosen.append((h, triggered[h]))
    for h in ("H4", "H3", "H10"):
        if h in triggered and h not in dict(chosen) and len(chosen) < 2:
            chosen.append((h, triggered[h]))
    rest = [h for h in std_pool if h not in dict(chosen)]
    rng.shuffle(rest)
    for h in rest:
        if len(chosen) >= 3:
            break
        chosen.append((h, HOUSE_STANDARDS[h]))
    for h, txt in chosen:
        criteria.append({"text": txt, "kind": "house_standard", "source": h})
    for i, cr in enumerate(criteria, 1):
        cr["id"] = f"C{i}"
        cr["weight"] = 1

    instructions = (
        f"You act for {c['client_role']}, {c['client']}. {c['summary']}\n\n"
        + (f"The client asks: {task_q}\n\n" if task_q else "")
        + f"{DELIVERABLE_ASK[p['task_type']]} The matter documents are in the matter folder; "
        f"read them before you write. The date of your deliverable is {fmt_date(c['today'])}. "
        "Address the deliverable to the supervising partner."
    )
    docs = {DOC_TITLES[d]: {"key": d, "facts": f, "must_contain": must.get(d, [])} for d, f in facts.items()}
    names = sorted({v for k, v in c.items() if isinstance(v, str) and k in
                    ("buyer", "seller", "target", "customer", "claimant", "contractor", "director", "contact",
                     "issuer", "underwriter", "client_co", "supplier", "client")})
    return {
        "task": {
            "task_id": p["task_id"], "matter_id": p["matter_id"], "practice_area": area if area != "research" else "general",
            "task_type": p["task_type"], "difficulty": p["difficulty"], "instructions": instructions,
            "documents": sorted(docs), "rubric_id": f"RUBRIC_{p['task_id']}", "cohort": p["cohort"],
            "split": p["split"], "matter_family": MATTER_FAMILY.get(area, "research"),
            "task_family": TASK_TYPE_FAMILY[p["task_type"]], "deliverable_date": c["today"].isoformat(),
        },
        "rubric": {"rubric_id": f"RUBRIC_{p['task_id']}", "criteria": criteria},
        "answer_key": {"issues": issues_meta, "house_standards": [h for h, _ in chosen],
                       "research_points": research_points, "matter_names": names,
                       "context": {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in c.items()}},
        "docs": docs, "context": c,
    }


DOC_SYSTEM = (
    "You draft realistic legal documents for a synthetic law-firm training benchmark. All parties are fictional. "
    "Write in formal legal English with numbered sections. Output ONLY the document text in Markdown — no commentary."
)


STREETS = ["Fleet Street", "Bishopsgate", "Gresham Street", "King William Street", "Moorgate", "Cannon Street",
           "Queen Victoria Street", "Old Broad Street", "Cheapside", "Ludgate Hill"]


def registry_block(spec: dict[str, Any]) -> str:
    """Canonical identifying details shared by every document of a matter (prevents invented conflicts)."""
    c = spec["context"]
    rng = random.Random(spec["task"]["task_id"])
    roles = [("buyer", "Buyer"), ("seller", "Seller"), ("target", "Company"), ("issuer", "Company"),
             ("underwriter", "Underwriter"), ("client_co", "Customer"), ("supplier", "Supplier"),
             ("customer", "material customer"), ("client", "client")]
    lines, seen = [], set()
    for key, role in roles:
        name = c.get(key)
        if not name or name in seen:
            continue
        seen.add(name)
        lines.append(f"- {name} ({role}): incorporated in England and Wales, company number "
                     f"{rng.randint(10_000_000, 15_999_999):08d}, registered office {rng.randint(1, 180)} "
                     f"{rng.choice(STREETS)}, London.")
    return "\n".join(lines)


def write_document(cfg: dict[str, Any], spec: dict[str, Any], title: str, d: dict[str, Any]) -> tuple[str, dict]:
    c = spec["context"]
    kind = title.replace(".md", "").replace("_", " ")
    fact_lines = "\n".join(f"- {f}" for f in d["facts"]) or "- (no special facts; ordinary terms only)"
    if d["key"] == "client_email":
        shape = (f"An email from {c['contact']} at {c['client']} to the firm, 150-300 words, describing the matter "
                 "and asking for help. Include the facts below naturally.")
    elif d["key"] == "research_note":
        shape = "An internal research note by a trainee, 300-500 words, with general background. Do not cite any facts not given."
    elif d["key"] == "board_minutes":
        shape = "Minutes of a board meeting of the relevant company, 350-600 words, with numbered agenda items."
    else:
        shape = (f"An extract of a {kind}, 450-800 words, with numbered sections/clauses including ordinary boilerplate "
                 "(definitions, payment, notices, confidentiality, etc.) consistent with the matter.")
    prompt = (
        f"Matter: {c['summary']}\nDeliverable date context: documents pre-date {fmt_date(c['today'])}.\n\n"
        f"Canonical party details (use exactly these if you mention incorporation, numbers or addresses; "
        f"do not invent other ones):\n{registry_block(spec)}\n\n"
        f"Write: {shape}\n\n"
        "The document MUST contain each of the following facts, reproducing every name, number, percentage, period and "
        "date EXACTLY as written (even if a figure looks inconsistent — do not correct, comment on or flag anything), "
        "using the section/clause numbers given where stated:\n"
        f"{fact_lines}\n\n"
        "Do not add any other inconsistencies, errors, or legal problems beyond these facts. Do not invent other "
        "dates, amounts, periods, percentages, governing-law or jurisdiction terms about the matters covered by the facts; "
        "where this document type would normally state governing law, use English law and the courts of England unless "
        "a fact above says otherwise. "
        "Do not use the words 'issue', 'error', 'discrepancy' or 'inconsistent'."
    )
    m = model_cfg(cfg, "author")
    trace = {"title": title, "attempts": []}
    text = ""
    for attempt in range(3):
        msgs = [{"role": "system", "content": DOC_SYSTEM}, {"role": "user", "content": prompt}]
        if attempt and missing:
            msgs.append({"role": "assistant", "content": text})
            msgs.append({"role": "user", "content": "Rewrite the whole document. These exact strings are missing and must "
                                                     "appear verbatim: " + "; ".join(missing)})
        r = chat(msgs, model=m["model"], provider=m["provider"], role="author", temperature=0.7, max_tokens=3000)
        text = re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", r["content"].strip())
        missing = [s for s in d["must_contain"] if s not in text]
        trace["attempts"].append({"missing": missing, "usage": r["usage"]})
        if not missing:
            break
    if missing:  # last resort: append facts verbatim so the answer key stays valid
        text += "\n\n## Additional Provisions\n\n" + "\n\n".join(d["facts"])
        trace["appended_facts"] = True
    return text, trace


def build_task(cfg: dict[str, Any], spec: dict[str, Any]) -> str:
    t = spec["task"]
    out = DATA / t["split"] / t["task_id"]
    if (out / "task.json").exists():
        return f"{t['task_id']} exists"
    traces = []
    for title, d in spec["docs"].items():
        text, tr = write_document(cfg, spec, title, d)
        (out / "documents").mkdir(parents=True, exist_ok=True)
        (out / "documents" / title).write_text(text)
        traces.append(tr)
    write_json(out / "rubric.json", spec["rubric"])
    write_json(out / "expected_outputs" / "answer_key.json", spec["answer_key"])
    write_json(out / "expected_outputs" / "generation_trace.json", {"docs": traces, "doc_facts": spec["docs"]})
    (out / "instructions.md").write_text(t["instructions"] + "\n")
    write_json(out / "task.json", t)  # written last: marks the task complete
    return f"{t['task_id']} built"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/base.yaml")
    ap.add_argument("--only", default=None)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    cfg = load_config(args.config)
    used: set[str] = set()
    specs = [build_spec(p, cfg["seed"], used) for p in task_plan()]
    write_json(DATA / "manifest.json", {
        "dataset_version": cfg["dataset_version"], "seed": cfg["seed"],
        "tasks": [s["task"] | {"n_criteria": len(s["rubric"]["criteria"])} for s in specs],
    })
    write_json(DATA / "name_registry.json", {"names": sorted(used), "house_standards": HOUSE_STANDARDS})
    todo = [s for s in specs if not args.only or s["task"]["task_id"] == args.only]
    with cf.ThreadPoolExecutor(args.workers) as ex:
        for msg in ex.map(lambda s: build_task(cfg, s), todo):
            print(msg, flush=True)


if __name__ == "__main__":
    main()
