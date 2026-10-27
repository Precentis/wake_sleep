"""Agent memory: lessons grouped by kind of work, with lifecycle metadata."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

CATEGORIES = ("general", "analysis", "drafting", "review")
LESSON_TYPES = ("checklist", "practice_note")


def new_lesson(lesson_id: str, *, text: str, type_: str, category: str, cycle: int,
               source_tasks: list[str], evidence: list[str], confidence: float = 0.5,
               scope: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "lesson_id": lesson_id,
        "type": type_ if type_ in LESSON_TYPES else "practice_note",
        "category": category if category in CATEGORIES else "general",
        "text": text.strip(),
        "scope": scope or {"practice_area": "general", "task_type": "general"},
        "source_tasks": sorted(set(source_tasks)),
        "evidence": sorted(set(evidence)),
        "confidence": confidence,
        "status": "active",
        "version": 1,
        "created_cycle": cycle,
        "updated_cycle": cycle,
        "times_retrieved": 0,
        "times_helpful": 0,
        "times_unhelpful": 0,
        "times_harmful": 0,
        "history": [{"cycle": cycle, "action": "ADD", "text": text.strip()}],
    }


@dataclass
class Memory:
    version: int = 0
    cycle: int = 0
    lessons: dict[str, dict[str, Any]] = field(default_factory=dict)
    next_id: int = 1

    # -------------------------------------------------------------- basics
    def active(self) -> list[dict[str, Any]]:
        return [l for l in self.lessons.values() if l["status"] == "active"]

    def by_category(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {c: [] for c in CATEGORIES}
        for l in self.active():
            out[l["category"]].append(l)
        return out

    def alloc_id(self) -> str:
        lid = f"L{self.next_id:04d}"
        self.next_id += 1
        return lid

    def copy(self) -> "Memory":
        return copy.deepcopy(self)

    # -------------------------------------------------------------- (de)serialise
    def to_json(self) -> dict[str, Any]:
        cats = self.by_category()
        return {
            "memory_version": self.version,
            "cycle": self.cycle,
            "next_id": self.next_id,
            "n_active": len(self.active()),
            **{c: sorted(cats[c], key=lambda l: l["lesson_id"]) for c in CATEGORIES},
            "retired": sorted([l for l in self.lessons.values() if l["status"] != "active"],
                              key=lambda l: l["lesson_id"]),
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Memory":
        m = cls(version=d["memory_version"], cycle=d.get("cycle", 0), next_id=d.get("next_id", 1))
        for c in (*CATEGORIES, "retired"):
            for l in d.get(c, []):
                m.lessons[l["lesson_id"]] = l
        return m


def render_memory(lessons: list[dict[str, Any]]) -> str:
    """Render lessons for injection into the agent's context."""
    if not lessons:
        return ""
    groups: dict[str, list[dict[str, Any]]] = {c: [] for c in CATEGORIES}
    for l in lessons:
        groups.setdefault(l["category"], []).append(l)
    parts = ["# Firm practice memory",
             "Lessons learned from the firm's previous matters. Checklist items state what a deliverable must contain; "
             "practice notes state how to do the work. Apply those relevant to this task."]
    for c in CATEGORIES:
        if not groups.get(c):
            continue
        parts.append(f"\n## {c.capitalize()}")
        for l in sorted(groups[c], key=lambda x: x["lesson_id"]):
            parts.append(f"- [{l['lesson_id']}] ({l['type'].replace('_', ' ')}) {l['text']}")
    return "\n".join(parts)


def memory_tokens(text: str) -> int:
    return int(len(text) / 4)
