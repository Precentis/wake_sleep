"""Immutable memory versions: memory_v{n}.json plus a diff record for every sleep cycle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common.config import results_root
from common.io import read_json, write_json
from memory.store import Memory, new_lesson


def apply_operation(mem: Memory, op: dict[str, Any], cycle: int, new_id: str | None = None) -> str | None:
    """Apply one gated operation in place. Returns the id of the lesson created/modified (if any).

    `new_id` forces the id of an ADDed lesson (used for provisional ids during merging)."""
    srcs = sorted({t for c in op["candidates"] for t in c["source_tasks"]})
    evid = sorted({e for c in op["candidates"] for e in c["evidence"]})
    if op["action"] == "ADD":
        lid = new_id or mem.alloc_id()
        conf = max([c.get("confidence", 0.5) for c in op["candidates"]] or [0.5])
        mem.lessons[lid] = new_lesson(lid, text=op["text"], type_=op["type"], category=op["category"], cycle=cycle,
                                      source_tasks=srcs, evidence=evid, confidence=conf, scope=op["scope"])
        return lid
    if op["action"] in ("MERGE", "UPDATE"):
        lid = op["lesson_ids"][0]
        l = mem.lessons[lid]
        absorbed = op["lesson_ids"][1:] if op["action"] == "MERGE" else []
        for other in absorbed:
            o = mem.lessons[other]
            o["status"] = f"merged_into:{lid}"
            o["history"].append({"cycle": cycle, "action": "MERGED_INTO", "into": lid})
            srcs = sorted(set(srcs) | set(o["source_tasks"]))
            evid = sorted(set(evid) | set(o["evidence"]))
            for k in ("times_retrieved", "times_helpful", "times_unhelpful", "times_harmful"):
                l[k] += o[k]
        l["text"] = op["text"]
        l["type"] = op["type"] if op["type"] in ("checklist", "practice_note") else l["type"]
        l["source_tasks"] = sorted(set(l["source_tasks"]) | set(srcs))
        l["evidence"] = sorted(set(l["evidence"]) | set(evid))
        l["version"] += 1
        l["updated_cycle"] = cycle
        l["scope"] = op.get("scope") or l["scope"]
        l["history"].append({"cycle": cycle, "action": op["action"], "text": op["text"], "absorbed": absorbed})
        return lid
    if op["action"] == "DELETE":
        for lid in op["lesson_ids"]:
            l = mem.lessons[lid]
            l["status"] = "deleted"
            l["history"].append({"cycle": cycle, "action": "DELETE", "reason": op.get("reason", "")})
        return None
    raise ValueError(op["action"])


def memory_dir(cfg: dict[str, Any], lineage: str) -> Path:
    return results_root(cfg) / "memory" / lineage


def save_version(cfg: dict[str, Any], lineage: str, mem: Memory, diff: dict[str, Any] | None) -> None:
    d = memory_dir(cfg, lineage)
    write_json(d / f"memory_v{mem.version}.json", mem.to_json())
    if diff is not None:
        write_json(d / f"memory_v{mem.version}_diff.json", diff)


def load_version(cfg: dict[str, Any], lineage: str, version: int) -> Memory | None:
    p = memory_dir(cfg, lineage) / f"memory_v{version}.json"
    return Memory.from_json(read_json(p)) if p.exists() else None


def latest_version(cfg: dict[str, Any], lineage: str) -> int:
    d = memory_dir(cfg, lineage)
    vs = [int(p.stem.split("_v")[1]) for p in d.glob("memory_v*.json") if "_diff" not in p.stem]
    return max(vs) if vs else -1
