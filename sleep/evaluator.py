"""Lesson helpfulness bookkeeping from sleep-phase reviews (cycle >= 2)."""

from __future__ import annotations

from typing import Any

from memory.store import Memory


def apply_feedback(memory: Memory, results: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> dict[str, int]:
    """Update times_retrieved / helpful / unhelpful / harmful counters in place; return label counts."""
    counts = {"HELPFUL": 0, "HARMFUL": 0, "IRRELEVANT": 0}
    for r in results:
        for lid in r.get("injected_lesson_ids", []):
            if lid in memory.lessons:
                memory.lessons[lid]["times_retrieved"] += 1
    for rv in reviews:
        for fb in rv.get("lesson_feedback", []):
            lid, label = str(fb.get("lesson_id", "")), str(fb.get("label", "")).upper()
            l = memory.lessons.get(lid)
            if not l or label not in counts:
                continue
            counts[label] += 1
            if label == "HELPFUL":
                l["times_helpful"] += 1
            else:
                l["times_unhelpful"] += 1
                if label == "HARMFUL":
                    l["times_harmful"] += 1
    return counts
