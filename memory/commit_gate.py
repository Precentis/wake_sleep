"""Commit gate: an independent verifier decides which proposed lesson changes enter memory.

Two layers: (1) a deterministic leakage scan (names, amounts, dates, clause numbers, ids)
that hard-rejects; (2) an LLM verifier from a different model family scoring
generalisability, specificity, evidence, matter dependence, redundancy and usefulness.
"""

from __future__ import annotations

import concurrent.futures as cf
from typing import Any

from common.config import model_cfg, price
from common.llm import chat_json
from evaluation.leakage import scan

GATE_SYSTEM = """You are the commit gate for a legal AI agent's long-term memory. You independently verify proposed lessons before they are stored.
For each proposed lesson decide:
- generalizable: would it help on OTHER clients' matters of a similar or different kind?
- matter_specific: does it contain or depend on facts of one matter (names, amounts, dates, specific clause numbers, deal-specific facts)?
- too_narrow: does it only apply to one unusual document or fact pattern?
- sufficient_evidence: is it supported by the cited evidence (number of independent source tasks shown)? One source can suffice only for an important, clearly general lesson.
- duplicate: is it redundant with another lesson in this batch or the listed existing lessons?
- useful: would following it plausibly improve the quality of legal deliverables?
- important: would ignoring it cause a serious error (wrong figure, missed deadline, missed material risk)?
decision: COMMIT (general, useful, evidenced, not specific), REJECT (specific, narrow, wrong, useless or duplicate), or REVIEW (plausible but uncertain; needs a human).
Return JSON only."""


def _gate_batch(cfg: dict[str, Any], batch: list[dict[str, Any]], existing_texts: list[str]) -> tuple[list[dict], dict]:
    items = "\n".join(
        f"- P{i}: [{p['action']}; {p['type']}; category={p['category']}; source_tasks={p['n_sources']}] {p['text']}"
        for i, p in enumerate(batch))
    ex = "\n".join(f"- {t}" for t in existing_texts[:80]) or "(none)"
    schema = ('{"verdicts": [{"id": "P0", "generalizable": true, "matter_specific": false, "too_narrow": false, '
              '"sufficient_evidence": true, "duplicate": false, "useful": true, "important": false, '
              '"decision": "COMMIT|REJECT|REVIEW", "reason": "short"}]}')
    user = f"# Existing committed lessons (for duplicate checks)\n{ex}\n\n# Proposed lessons\n{items}\n\nJSON schema: {schema}"
    m = model_cfg(cfg, "commit")
    parsed, raw = chat_json([{"role": "system", "content": GATE_SYSTEM}, {"role": "user", "content": user}],
                            model=m["model"], provider=m["provider"], role="commit_gate", max_tokens=6000)
    verdicts = {str(v.get("id")): v for v in ((parsed or {}).get("verdicts") or []) if isinstance(v, dict)}
    out = [verdicts.get(f"P{i}", {"decision": "REVIEW", "reason": "no verdict returned"}) for i in range(len(batch))]
    trace = {"prompt": user, "raw_response": raw["content"][:20000], "input_tokens": raw["usage"]["input_tokens"],
             "output_tokens": raw["usage"]["output_tokens"],
             "cost_usd": price(cfg, m["model"], raw["usage"]["input_tokens"], raw["usage"]["output_tokens"])}
    return out, trace


def gate_operations(cfg: dict[str, Any], ops: list[dict[str, Any]], memory_lessons: dict[str, dict],
                    existing_texts: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (decisions aligned with ops, gate traces). Each decision: {decision, reason, leakage, verdict}."""
    gc = cfg.get("commit_gate", {})
    if not gc.get("enabled", True):
        return [{"decision": "COMMIT", "reason": "gate disabled (ablation)", "leakage": None} for _ in ops], []
    min_src = int(gc.get("min_sources_for_auto_commit", 2))
    if not cfg["sleep"].get("merge", True):
        min_src = 1  # no-merge ablation: candidates are single-source by construction
    decisions: list[dict[str, Any] | None] = [None] * len(ops)
    pending: list[tuple[int, dict[str, Any]]] = []
    for i, op in enumerate(ops):
        if op["action"] == "DELETE":
            decisions[i] = {"decision": "COMMIT", "reason": "deletion", "leakage": None}
            continue
        leak = scan(op["text"])
        if leak["leak"]:
            decisions[i] = {"decision": "REJECT", "reason": "leakage scan: " + ", ".join(leak["hard"][:6]),
                            "leakage": leak}
            continue
        srcs = {t for c in op["candidates"] for t in c["source_tasks"]}
        for lid in op["lesson_ids"]:
            srcs |= set(memory_lessons[lid]["source_tasks"]) if lid in memory_lessons else set()
        pending.append((i, {**op, "n_sources": len(srcs), "leak": leak}))
    traces: list[dict[str, Any]] = []
    batches = [pending[s:s + 12] for s in range(0, len(pending), 12)]

    def job(b: list[tuple[int, dict[str, Any]]]) -> tuple[list[tuple[int, dict[str, Any]]], list[dict], dict]:
        v, tr = _gate_batch(cfg, [p for _, p in b], existing_texts)
        return b, v, tr

    with cf.ThreadPoolExecutor(8) as ex:
        for b, verdicts, tr in ex.map(job, batches):
            traces.append(tr)
            for (i, p), v in zip(b, verdicts):
                d = str(v.get("decision", "REVIEW")).upper()
                d = d if d in ("COMMIT", "REJECT", "REVIEW") else "REVIEW"
                reason = str(v.get("reason", ""))
                # Evidence rule: lessons resting on fewer than min_src training tasks never auto-commit; important
                # ones still reach the human review queue rather than being rejected.
                if d == "COMMIT" and p["n_sources"] < min_src:
                    d, reason = "REVIEW", f"insufficient independent sources (sources={p['n_sources']}); " + reason
                decisions[i] = {"decision": d, "reason": reason, "leakage": p["leak"], "verdict": v,
                                "n_sources": p["n_sources"]}
    return [d or {"decision": "REVIEW", "reason": "unprocessed"} for d in decisions], traces
