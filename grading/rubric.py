"""Task / rubric loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common.io import read_json

DATA = Path(__file__).resolve().parents[1] / "data"


def task_dir(task: dict[str, Any]) -> Path:
    return DATA / task["split"] / task["task_id"]


def load_tasks(split: str | None = None, cohort: str | None = None) -> list[dict[str, Any]]:
    out = []
    for p in sorted(DATA.glob("*/*/task.json")):
        t = read_json(p)
        if split and t["split"] != split:
            continue
        if cohort and t["cohort"] != cohort:
            continue
        out.append(t)
    return out


def load_rubric(task: dict[str, Any]) -> dict[str, Any]:
    return read_json(task_dir(task) / "rubric.json")


def load_documents_text(task: dict[str, Any]) -> str:
    parts = []
    for p in sorted((task_dir(task) / "documents").glob("*.md")):
        parts.append(f"===== DOCUMENT: {p.name} =====\n{p.read_text()}")
    return "\n\n".join(parts)
