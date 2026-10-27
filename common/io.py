"""Small JSON / JSONL helpers with atomic writes."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


def write_json(path: str | Path, obj: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())


def write_jsonl(path: str | Path, rows: Iterable[Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def read_jsonl(path: str | Path) -> list[Any]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
