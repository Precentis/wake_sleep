"""YAML config loading with `extends:` inheritance and deep-merge overrides."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(path: str | Path, **overrides: Any) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    raw = yaml.safe_load(p.read_text()) or {}
    parent = raw.pop("extends", None)
    cfg = load_config(p.parent / parent) if parent else {}
    cfg = _deep_merge(cfg, raw)
    return _deep_merge(cfg, overrides) if overrides else cfg


def results_root(cfg: dict[str, Any]) -> Path:
    return ROOT / cfg.get("results_dir", "results") / cfg["experiment_id"]


def model_cfg(cfg: dict[str, Any], role: str) -> dict[str, str]:
    return cfg["models"][role]


def price(cfg: dict[str, Any], model: str, input_tokens: int, output_tokens: int) -> float:
    p = cfg.get("prices", {}).get(model, {"input": 0, "output": 0})
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1e6
