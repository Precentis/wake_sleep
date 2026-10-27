"""Leakage scanner: flags lesson text that memorises matter-specific detail."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from common.io import read_json

DATA = Path(__file__).resolve().parents[1] / "data"
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"

HARD_PATTERNS = {
    "amount": re.compile(r"[$£€]\s?\d[\d,.]*\s*(?:m|bn|million|billion)?\b|\b\d{1,3}(?:,\d{3}){1,}\b"),
    "date": re.compile(rf"\b\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}\b|\b(?:{MONTHS})\s+\d{{1,2}},?\s+\d{{4}}\b|\b20\d\d-\d\d-\d\d\b"),
    "clause_number": re.compile(r"\b(?:Section|Clause|Article|Paragraph|Warranty|Item|Schedule)\s+\d+(?:\.\d+)*(?:\([a-z]\))?", re.I),
    "task_or_matter_id": re.compile(r"\b(?:MNA|CM|COM|RES)_[TVX]\d{3}\b|\bMATTER_\w+"),
    "document_file": re.compile(r"\b\w+\.md\b"),
}
SOFT_PATTERNS = {
    "specific_period": re.compile(r"\b\d+[- ](?:day|month|year)s?\b", re.I),
    "percentage": re.compile(r"\b\d+(?:\.\d+)?\s?%"),
}


@lru_cache(maxsize=1)
def _names() -> tuple[set[str], set[str]]:
    reg = read_json(DATA / "name_registry.json")
    full = set(reg["names"])
    from data.build_dataset import CO_PREFIX, LAST
    tokens = set(CO_PREFIX) | set(LAST)
    return full, tokens


def scan(text: str) -> dict[str, Any]:
    full, tokens = _names()
    hard: list[str] = []
    soft: list[str] = []
    for n in full:
        if n in text:
            hard.append(f"name:{n}")
    for tok in tokens:
        if re.search(rf"\b{re.escape(tok)}\b", text):
            hard.append(f"name_token:{tok}")
    for k, p in HARD_PATTERNS.items():
        for m in p.findall(text):
            hard.append(f"{k}:{m if isinstance(m, str) else m[0]}")
    for k, p in SOFT_PATTERNS.items():
        for m in p.findall(text):
            soft.append(f"{k}:{m}")
    return {"hard": sorted(set(hard)), "soft": sorted(set(soft)), "leak": bool(hard)}


def scan_memory(lessons: list[dict[str, Any]]) -> dict[str, Any]:
    flagged = []
    for l in lessons:
        s = scan(l["text"])
        if s["hard"] or s["soft"]:
            flagged.append({"lesson_id": l["lesson_id"], "text": l["text"], **s})
    return {"n_lessons": len(lessons), "n_hard": sum(1 for f in flagged if f["hard"]),
            "n_soft_only": sum(1 for f in flagged if not f["hard"]), "flagged": flagged}
