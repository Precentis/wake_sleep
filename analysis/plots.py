"""Dependency-free SVG charts (line and bar) for the experiment report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

PALETTE = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#4b5563"]


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def line_chart(path: Path, title: str, series: dict[str, list[tuple[float, float | None]]], xlabel: str,
               ylabel: str, y_range: tuple[float, float] | None = None, w: int = 720, h: int = 420) -> None:
    pts = [(x, y) for s in series.values() for x, y in s if y is not None]
    if not pts:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs) if max(xs) > min(xs) else min(xs) + 1
    y0, y1 = y_range or (min(ys), max(ys))
    if y1 == y0:
        y1 = y0 + 1
    pad = (y1 - y0) * 0.08 if not y_range else 0
    y0, y1 = y0 - pad, y1 + pad
    L, R, T, B = 70, 170, 40, 55
    px = lambda x: L + (x - x0) / (x1 - x0) * (w - L - R)  # noqa: E731
    py = lambda y: h - B - (y - y0) / (y1 - y0) * (h - T - B)  # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="Helvetica,Arial" font-size="12">',
           f'<rect width="{w}" height="{h}" fill="white"/>',
           f'<text x="{w / 2}" y="22" text-anchor="middle" font-size="15" font-weight="bold">{_esc(title)}</text>']
    for i in range(6):
        yv = y0 + (y1 - y0) * i / 5
        out.append(f'<line x1="{L}" x2="{w - R}" y1="{py(yv):.1f}" y2="{py(yv):.1f}" stroke="#e5e7eb"/>')
        out.append(f'<text x="{L - 6}" y="{py(yv) + 4:.1f}" text-anchor="end">{yv:.3g}</text>')
    for xv in sorted(set(xs)):
        out.append(f'<text x="{px(xv):.1f}" y="{h - B + 18}" text-anchor="middle">{xv:g}</text>')
    out.append(f'<line x1="{L}" x2="{w - R}" y1="{h - B}" y2="{h - B}" stroke="#111"/>')
    out.append(f'<line x1="{L}" x2="{L}" y1="{T}" y2="{h - B}" stroke="#111"/>')
    out.append(f'<text x="{(L + w - R) / 2}" y="{h - 12}" text-anchor="middle">{_esc(xlabel)}</text>')
    out.append(f'<text transform="translate(18,{(T + h - B) / 2}) rotate(-90)" text-anchor="middle">{_esc(ylabel)}</text>')
    for i, (name, s) in enumerate(series.items()):
        c = PALETTE[i % len(PALETTE)]
        s = [(x, y) for x, y in s if y is not None]
        if not s:
            continue
        d = " ".join(f"{'M' if j == 0 else 'L'}{px(x):.1f},{py(y):.1f}" for j, (x, y) in enumerate(s))
        out.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="2.2"/>')
        for x, y in s:
            out.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="3.2" fill="{c}"/>')
        ly = T + 10 + i * 18
        out.append(f'<rect x="{w - R + 12}" y="{ly - 8}" width="12" height="3" fill="{c}"/>')
        out.append(f'<text x="{w - R + 30}" y="{ly}">{_esc(name)}</text>')
    out.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out))


def bar_chart(path: Path, title: str, labels: list[str], groups: dict[str, list[float | None]], ylabel: str,
              w: int = 760, h: int = 420, fmt: str = "{:.2f}") -> None:
    vals = [v for g in groups.values() for v in g if v is not None]
    if not vals:
        return
    y1 = max(vals) * 1.15 or 1
    L, R, T, B = 70, 30, 40, 90
    n, k = len(labels), len(groups)
    slot = (w - L - R) / max(1, n)
    bw = slot * 0.8 / max(1, k)
    py = lambda y: h - B - y / y1 * (h - T - B)  # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="Helvetica,Arial" font-size="12">',
           f'<rect width="{w}" height="{h}" fill="white"/>',
           f'<text x="{w / 2}" y="22" text-anchor="middle" font-size="15" font-weight="bold">{_esc(title)}</text>',
           f'<line x1="{L}" x2="{w - R}" y1="{h - B}" y2="{h - B}" stroke="#111"/>']
    for i in range(6):
        yv = y1 * i / 5
        out.append(f'<line x1="{L}" x2="{w - R}" y1="{py(yv):.1f}" y2="{py(yv):.1f}" stroke="#e5e7eb"/>')
        out.append(f'<text x="{L - 6}" y="{py(yv) + 4:.1f}" text-anchor="end">{yv:.3g}</text>')
    for gi, (gname, gvals) in enumerate(groups.items()):
        c = PALETTE[gi % len(PALETTE)]
        for i, v in enumerate(gvals):
            if v is None:
                continue
            x = L + i * slot + slot * 0.1 + gi * bw
            out.append(f'<rect x="{x:.1f}" y="{py(v):.1f}" width="{bw - 2:.1f}" height="{h - B - py(v):.1f}" fill="{c}"/>')
            out.append(f'<text x="{x + bw / 2:.1f}" y="{py(v) - 4:.1f}" text-anchor="middle" font-size="10">{fmt.format(v)}</text>')
        if k > 1:
            out.append(f'<rect x="{L + gi * 140}" y="{h - 22}" width="12" height="10" fill="{c}"/>')
            out.append(f'<text x="{L + gi * 140 + 16}" y="{h - 13}">{_esc(gname)}</text>')
    for i, lab in enumerate(labels):
        x = L + i * slot + slot / 2
        out.append(f'<text transform="translate({x:.1f},{h - B + 14}) rotate(25)" font-size="11">{_esc(lab)}</text>')
    out.append(f'<text transform="translate(18,{(T + h - B) / 2}) rotate(-90)" text-anchor="middle">{_esc(ylabel)}</text>')
    out.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out))


def memory_evolution(path: Path, versions: list[dict[str, Any]], w: int = 900, h: int = 520) -> None:
    """Figure-4 style: one column per memory version, one dot per lesson, coloured by change type."""
    if len(versions) < 2:
        return
    L, T, B = 60, 40, 40
    colw = (w - L - 40) / max(1, len(versions) - 1)
    ids_all = sorted({l["lesson_id"] for v in versions for c in ("general", "analysis", "drafting", "review") for l in v[c]})
    rows = {lid: i for i, lid in enumerate(ids_all)}
    dy = (h - T - B) / max(1, len(ids_all))
    colors = {"new": "#2563eb", "revised": "#111827", "same": "#9ca3af"}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="Helvetica,Arial" font-size="12">',
           f'<rect width="{w}" height="{h}" fill="white"/>',
           f'<text x="{w / 2}" y="22" text-anchor="middle" font-size="15" font-weight="bold">Evolution of memory (blue=new, black=revised, grey=unchanged, red x=removed)</text>']
    prev: dict[str, dict] = {}
    for vi, v in enumerate(versions):
        x = L + vi * colw
        out.append(f'<text x="{x:.1f}" y="{h - 15}" text-anchor="middle">v{v["memory_version"]}</text>')
        cur = {l["lesson_id"]: l for c in ("general", "analysis", "drafting", "review") for l in v[c]}
        for lid, l in cur.items():
            y = T + rows[lid] * dy
            kind = "new" if lid not in prev else ("revised" if prev[lid]["text"] != l["text"] else "same")
            if lid in prev:
                out.append(f'<line x1="{x - colw:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#d1d5db" stroke-width="0.6"/>')
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{max(1.2, min(3, dy / 2)):.1f}" fill="{colors[kind]}"/>')
        for lid in set(prev) - set(cur):
            y = T + rows[lid] * dy
            out.append(f'<text x="{x:.1f}" y="{y + 3:.1f}" text-anchor="middle" fill="#dc2626" font-size="9">x</text>')
        prev = cur
    out.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out))
