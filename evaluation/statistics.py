"""Paired statistics for condition comparisons (task-level pairing preserved)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats


def describe(xs: list[float]) -> dict[str, float]:
    a = np.asarray(xs, dtype=float)
    if not len(a):
        return {"n": 0}
    lo, hi = bootstrap_ci(a)
    return {"n": int(len(a)), "mean": float(a.mean()), "median": float(np.median(a)),
            "sd": float(a.std(ddof=1)) if len(a) > 1 else 0.0, "ci95_low": lo, "ci95_high": hi}


def bootstrap_ci(a: np.ndarray, n_boot: int = 10000, seed: int = 42) -> tuple[float, float]:
    if len(a) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(n_boot, len(a)))
    means = a[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired(a: dict[str, float], b: dict[str, float]) -> dict[str, Any]:
    """Compare condition B against A over shared task ids (diff = B - A)."""
    ids = sorted(set(a) & set(b))
    if not ids:
        return {"n": 0}
    x = np.array([a[i] for i in ids], dtype=float)
    y = np.array([b[i] for i in ids], dtype=float)
    d = y - x
    out = {"n": len(ids), "mean_a": float(x.mean()), "mean_b": float(y.mean()), "diff": describe(list(d))}
    sd = d.std(ddof=1) if len(d) > 1 else 0.0
    out["cohens_dz"] = float(d.mean() / sd) if sd > 0 else (0.0 if d.mean() == 0 else math.copysign(math.inf, d.mean()))
    nz = d[d != 0]
    if len(nz) >= 1:
        try:
            w = stats.wilcoxon(y, x, zero_method="wilcox", alternative="two-sided")
            out["wilcoxon_p"] = float(w.pvalue)
        except ValueError:
            out["wilcoxon_p"] = None
    else:
        out["wilcoxon_p"] = 1.0
    out["n_improved"] = int((d > 0).sum())
    out["n_worse"] = int((d < 0).sum())
    out["n_tied"] = int((d == 0).sum())
    return out


def mcnemar(a: dict[str, bool], b: dict[str, bool]) -> dict[str, Any]:
    """Exact McNemar test for paired binary outcomes (e.g. all-pass)."""
    ids = sorted(set(a) & set(b))
    b01 = sum(1 for i in ids if not a[i] and b[i])  # B passes, A fails
    b10 = sum(1 for i in ids if a[i] and not b[i])
    n = b01 + b10
    p = float(stats.binomtest(b01, n, 0.5).pvalue) if n else 1.0
    return {"n": len(ids), "rate_a": sum(a[i] for i in ids) / max(1, len(ids)),
            "rate_b": sum(b[i] for i in ids) / max(1, len(ids)), "b_only": b01, "a_only": b10, "p_exact": p}


def cohen_kappa(x: list[bool], y: list[bool]) -> float:
    n = len(x)
    if not n:
        return float("nan")
    po = sum(1 for a, b in zip(x, y) if a == b) / n
    px, py = sum(x) / n, sum(y) / n
    pe = px * py + (1 - px) * (1 - py)
    return float((po - pe) / (1 - pe)) if pe < 1 else 1.0
