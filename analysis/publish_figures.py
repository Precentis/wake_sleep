"""Publication figures for the README.

Numbers match results/ws_2026_001/REPORT_TABLES.md. The script writes SVG.
When Google Chrome is installed it also writes PNG at 2x, which is what the
README embeds. No third-party plotting library.

    python -m analysis.publish_figures
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures"

INK = "#1c1917"
MUTED = "#57534e"
GRID = "#e7e5e4"
NAVY = "#1e3a5f"
STEEL = "#3d6b99"
SAGE = "#4d6b4a"
BRASS = "#8a6a3b"
STONE = "#a8a29e"
CLAY = "#9a3412"
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class Svg:
    def __init__(self, w: int, h: int) -> None:
        self.w = w
        self.h = h
        self.parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        ]

    def text(self, x, y, s, size=16, fill=INK, anchor="start", weight="400") -> None:
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-family="{FONT}" '
            f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{_esc(s)}</text>'
        )

    def rect(self, x, y, w, h, fill) -> None:
        self.parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" rx="2"/>')

    def line(self, x1, y1, x2, y2, stroke=GRID, sw=1) -> None:
        self.parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def circle(self, x, y, r, fill) -> None:
        self.parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}"/>')

    def poly(self, pts: list[tuple[float, float]], stroke, sw=2.4) -> None:
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.parts.append(f'<polyline points="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"/>')

    def round_box(self, x, y, w, h, stroke) -> None:
        self.parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="14" '
            f'fill="#fafaf9" stroke="{stroke}" stroke-width="1.6"/>'
        )

    def save(self, name: str) -> Path:
        self.parts.append("</svg>")
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / name
        path.write_text("\n".join(self.parts))
        return path


def _hbar_panel(svg: Svg, origin_x: int, origin_y: int, width: int, height: int,
                title: str, xlabel: str, labels: list[str], values: list[float],
                colors: list[str], xmax: float) -> None:
    svg.text(origin_x, origin_y + 8, title, size=20, weight="600")
    label_w = 168
    plot_x = origin_x + label_w
    plot_w = width - label_w - 70
    top = origin_y + 36
    row_h = (height - 78) / len(labels)
    for i, tick in enumerate([0, xmax / 2, xmax]):
        x = plot_x + plot_w * (tick / xmax)
        svg.line(x, top, x, top + row_h * len(labels), GRID, 1)
        svg.text(x, top + row_h * len(labels) + 22, f"{tick:.0f}", size=13, fill=MUTED, anchor="middle")
    svg.text(origin_x + width / 2, origin_y + height - 6, xlabel, size=14, fill=MUTED, anchor="middle")
    for i, (label, value, color) in enumerate(zip(labels, values, colors)):
        y = top + i * row_h
        bar_h = row_h * 0.46
        bar_y = y + (row_h - bar_h) / 2
        bw = plot_w * (value / xmax)
        svg.text(plot_x - 12, bar_y + bar_h * 0.72, label, size=15, anchor="end")
        svg.rect(plot_x, bar_y, max(bw, 1), bar_h, color)
        svg.text(plot_x + bw + 8, bar_y + bar_h * 0.72, f"{value:.1f}%", size=14)


def loop() -> Svg:
    s = Svg(1400, 420)
    stages = [
        (40, "1   Wake", "Tool-using associate", "reads, calculates, drafts, ships", NAVY),
        (490, "2   Grade", "Two blind judges", "A criterion counts only if both pass", STEEL),
        (940, "3   Sleep", "Review, merge, gate", "Commit habits. Reject client facts.", SAGE),
    ]
    for x, title, a, b, color in stages:
        s.round_box(x, 70, 410, 230, color)
        s.text(x + 205, 130, title, size=26, fill=color, anchor="middle", weight="600")
        s.text(x + 205, 185, a, size=20, anchor="middle")
        s.text(x + 205, 220, b, size=18, fill=MUTED, anchor="middle")
    s.text(455, 188, "→", size=28, fill=INK, anchor="middle")
    s.text(905, 188, "→", size=28, fill=INK, anchor="middle")
    s.line(230, 330, 1170, 330, NAVY, 1.6)
    s.text(1162, 336, "▸", size=16, fill=NAVY, anchor="middle")
    s.text(700, 372, "Next wake sees the versioned memory bank  ·  full text, or retrieved top-K",
           size=18, fill=NAVY, anchor="middle")
    return s


def headline() -> Svg:
    labels = ["Vanilla", "Placebo memory", "Oracle guidance", "Budget-matched", "Full memory v10", "Retrieved K=50"]
    colors = [STONE, "#d6d3d1", BRASS, SAGE, NAVY, STEEL]
    rubric = [54.7, 53.6, 68.1, 71.4, 78.4, 79.5]
    all_pass = [2.2, 6.5, 13.0, 26.1, 34.8, 30.4]
    s = Svg(1400, 620)
    s.text(36, 40, "Held-out test  ·  46 tasks  ·  one seed", size=22, weight="600")
    _hbar_panel(s, 36, 70, 650, 520, "Rubric pass", "Percent of criteria passed", labels, rubric, colors, 100)
    _hbar_panel(s, 730, 70, 640, 520, "All-pass", "Percent of tasks fully passed", labels, all_pass, colors, 50)
    return s


def generalization() -> Svg:
    s = Svg(980, 560)
    s.text(40, 46, "The gain transfers, and it shrinks", size=24, weight="600")
    s.text(40, 78, "Rubric pass on the held-out test", size=16, fill=MUTED)
    labels = ["Familiar M&A", "New matters"]
    vanilla = [57.1, 55.5]
    memory = [88.5, 66.1]
    notes = ["+31.3 pp", "+10.6 pp"]
    plot_x, plot_y, plot_w, plot_h = 90, 120, 760, 340
    for tick in (0, 25, 50, 75, 100):
        y = plot_y + plot_h - plot_h * tick / 100
        s.line(plot_x, y, plot_x + plot_w, y, GRID)
        s.text(plot_x - 12, y + 5, str(tick), size=14, fill=MUTED, anchor="end")
    s.line(plot_x, plot_y + plot_h, plot_x + plot_w, plot_y + plot_h, INK, 1.2)
    group_w = plot_w / 2
    for i, (lab, v, m, note) in enumerate(zip(labels, vanilla, memory, notes)):
        cx = plot_x + group_w * i + group_w / 2
        bw = 70
        for dx, val, color in ((-48, v, STONE), (48, m, NAVY)):
            h = plot_h * val / 100
            s.rect(cx + dx - bw / 2, plot_y + plot_h - h, bw, h, color)
            s.text(cx + dx, plot_y + plot_h - h - 12, f"{val:.1f}%", size=15, anchor="middle")
        s.text(cx, plot_y + plot_h + 36, lab, size=18, anchor="middle")
        s.text(cx, plot_y + plot_h + 62, note, size=16, fill=NAVY if i == 0 else CLAY, anchor="middle")
    s.rect(640, 130, 16, 16, STONE)
    s.text(666, 144, "Vanilla", size=15)
    s.rect(760, 130, 16, 16, NAVY)
    s.text(786, 144, "Full memory", size=15)
    return s


def _y(v: float, top: float, height: float, ymin: float, ymax: float) -> float:
    return top + height - height * (v - ymin) / (ymax - ymin)


def learning() -> Svg:
    cycles = list(range(11))
    overall = [55.7, 79.3, 76.8, 76.4, 79.1, 75.4, 73.9, 76.0, 77.8, 72.0, 75.3]
    familiar = [62.4, 88.9, 91.4, 88.0, 92.2, 87.3, 90.6, 86.8, 85.5, 87.0, 85.0]
    new = [48.9, 69.8, 62.3, 64.8, 66.1, 63.5, 57.1, 65.1, 70.1, 57.0, 65.5]
    lessons = [0, 52, 44, 35, 38, 34, 29, 31, 30, 24, 31]
    s = Svg(1400, 560)
    # left panel
    s.text(48, 42, "Almost all of the lift is cycle 1", size=22, weight="600")
    s.text(48, 70, "Validation rubric pass, 40 tasks", size=15, fill=MUTED)
    L = (70, 110, 560, 360)
    for tick in (40, 55, 70, 85, 100):
        y = _y(tick, L[1], L[3], 40, 100)
        s.line(L[0], y, L[0] + L[2], y, GRID)
        s.text(L[0] - 10, y + 4, str(tick), size=13, fill=MUTED, anchor="end")
    s.line(L[0], L[1] + L[3], L[0] + L[2], L[1] + L[3], INK, 1.2)

    def series(vals, color):
        pts = []
        for i, v in enumerate(vals):
            x = L[0] + L[2] * i / 10
            y = _y(v, L[1], L[3], 40, 100)
            pts.append((x, y))
        s.poly(pts, color)
        for x, y in pts:
            s.circle(x, y, 4, color)

    series(familiar, NAVY)
    series(overall, SAGE)
    series(new, CLAY)
    for i in cycles:
        s.text(L[0] + L[2] * i / 10, L[1] + L[3] + 24, str(i), size=13, fill=MUTED, anchor="middle")
    s.text(L[0] + L[2] / 2, 530, "Memory version after each sleep", size=15, fill=MUTED, anchor="middle")
    s.rect(430, 96, 14, 14, NAVY)
    s.text(450, 108, "Familiar", size=14)
    s.rect(540, 96, 14, 14, SAGE)
    s.text(560, 108, "All", size=14)
    s.rect(620, 96, 14, 14, CLAY)
    s.text(640, 108, "New", size=14)

    # right panel
    s.text(760, 42, "The bank got smaller, not larger", size=22, weight="600")
    s.text(760, 70, "Active lessons", size=15, fill=MUTED)
    R = (790, 110, 520, 360)
    for tick in (0, 20, 40, 60):
        y = _y(tick, R[1], R[3], 0, 60)
        s.line(R[0], y, R[0] + R[2], y, GRID)
        s.text(R[0] - 10, y + 4, str(tick), size=13, fill=MUTED, anchor="end")
    s.line(R[0], R[1] + R[3], R[0] + R[2], R[1] + R[3], INK, 1.2)
    pts = []
    for i, v in enumerate(lessons):
        x = R[0] + R[2] * i / 10
        y = _y(v, R[1], R[3], 0, 60)
        pts.append((x, y))
        s.text(x, R[1] + R[3] + 24, str(i), size=13, fill=MUTED, anchor="middle")
    s.poly(pts, NAVY)
    for x, y in pts:
        s.circle(x, y, 4, NAVY)
    s.text(pts[1][0] + 14, pts[1][1] - 12, "52", size=16, fill=NAVY)
    s.text(pts[9][0] - 8, pts[9][1] + 28, "24", size=16, fill=MUTED, anchor="end")
    s.text(R[0] + R[2] / 2, 530, "Memory version", size=15, fill=MUTED, anchor="middle")
    return s


def behaviour() -> Svg:
    labels = ["Document reads", "Searches", "Calculations", "Draft revisions"]
    vanilla = [4.3, 4.8, 5.2, 4.9]
    memory = [4.2, 4.7, 10.6, 9.1]
    s = Svg(1000, 520)
    s.text(40, 46, "Memory changes the craft, not the search", size=24, weight="600")
    s.text(40, 78, "Mean calls per held-out task", size=16, fill=MUTED)
    plot_x, top, plot_w = 230, 120, 620
    row_h = 80
    xmax = 14
    for tick in (0, 4, 8, 12):
        x = plot_x + plot_w * tick / xmax
        s.line(x, top, x, top + row_h * 4, GRID)
        s.text(x, top + row_h * 4 + 28, str(tick), size=14, fill=MUTED, anchor="middle")
    for i, (lab, v, m) in enumerate(zip(labels, vanilla, memory)):
        y = top + i * row_h
        s.text(plot_x - 16, y + 36, lab, size=17, anchor="end")
        s.rect(plot_x, y + 10, plot_w * v / xmax, 22, STONE)
        s.rect(plot_x, y + 38, plot_w * m / xmax, 22, NAVY)
        s.text(plot_x + plot_w * v / xmax + 8, y + 26, f"{v:.1f}", size=14)
        s.text(plot_x + plot_w * m / xmax + 8, y + 54, f"{m:.1f}", size=14, fill=NAVY)
    s.rect(620, 62, 16, 16, STONE)
    s.text(644, 76, "Vanilla", size=15)
    s.rect(740, 62, 16, 16, NAVY)
    s.text(764, 76, "Full memory v10", size=15)
    return s


def ablations() -> Svg:
    labels = ["No grading  vs full v3", "Reset every 2 cycles  vs full v4", "No commit gate  vs full v3", "No merge  vs full v2"]
    deltas = [-12.8, -5.9, -0.6, 8.3]
    colors = [CLAY, CLAY, STONE, SAGE]
    s = Svg(1100, 520)
    s.text(40, 46, "What the lift depends on", size=24, weight="600")
    s.text(40, 78, "Test rubric, percentage points versus the matched memory version", size=16, fill=MUTED)
    plot_x, top, plot_w = 340, 120, 620
    row_h = 78
    xmin, xmax = -18, 14
    span = xmax - xmin

    def x_of(v: float) -> float:
        return plot_x + plot_w * (v - xmin) / span

    for tick in (-15, -10, -5, 0, 5, 10):
        x = x_of(tick)
        s.line(x, top, x, top + row_h * 4, GRID)
        s.text(x, top + row_h * 4 + 28, str(tick), size=14, fill=MUTED, anchor="middle")
    s.line(x_of(0), top - 8, x_of(0), top + row_h * 4 + 6, INK, 1.2)
    for i, (lab, d, color) in enumerate(zip(labels, deltas, colors)):
        y = top + i * row_h + 22
        x0, x1 = sorted((x_of(0), x_of(d)))
        s.rect(x0, y, max(x1 - x0, 2), 28, color)
        s.text(plot_x - 16, y + 20, lab, size=16, anchor="end")
        label_x = x_of(d) + (8 if d >= 0 else -8)
        anchor = "start" if d >= 0 else "end"
        s.text(label_x, y + 20, f"{d:+.1f} pp", size=15, anchor=anchor)
    return s


def k_sweep() -> Svg:
    k = [3, 5, 10, 20, 50]
    rubric = [61.0, 62.8, 70.6, 70.7, 76.1]
    tokens = [245, 307, 547, 563, 688]
    s = Svg(1400, 540)
    s.text(40, 42, "K was chosen on validation. K = 50 is nearly the whole bank.", size=22, weight="600")

    def panel(origin, title, ylabel, values, ymin, ymax, color, fmt):
        s.text(origin, 88, title, size=20, weight="600")
        x0, y0, w, h = origin + 50, 130, 500, 320
        for tick_i in range(5):
            tick = ymin + (ymax - ymin) * tick_i / 4
            y = _y(tick, y0, h, ymin, ymax)
            s.line(x0, y, x0 + w, y, GRID)
            s.text(x0 - 10, y + 4, f"{tick:.0f}", size=13, fill=MUTED, anchor="end")
        s.line(x0, y0 + h, x0 + w, y0 + h, INK, 1.2)
        pts = []
        for i, (kk, val) in enumerate(zip(k, values)):
            x = x0 + w * i / (len(k) - 1)
            y = _y(val, y0, h, ymin, ymax)
            pts.append((x, y))
            s.text(x, y0 + h + 26, str(kk), size=14, fill=MUTED, anchor="middle")
            s.text(x, y - 14, fmt(val), size=14, fill=color, anchor="middle")
        s.poly(pts, color)
        for x, y in pts:
            s.circle(x, y, 5, color)
        s.text(x0 + w / 2, 510, "Lessons retrieved (K)", size=15, fill=MUTED, anchor="middle")
        s.text(origin, 112, ylabel, size=14, fill=MUTED)

    panel(40, "Quality", "Validation rubric pass", rubric, 50, 90, NAVY, lambda v: f"{v:.0f}%")
    panel(740, "Prompt size", "Input tokens per task, thousands", tokens, 0, 800, BRASS, lambda v: f"{v:.0f}k")
    return s


CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def _rasterize(svg_path: Path, width: int, height: int) -> None:
    if not CHROME.is_file():
        return
    html_path = svg_path.with_suffix(".html")
    html_path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>html,body{margin:0;background:#fff}svg{display:block}</style></head><body>"
        + svg_path.read_text()
        + "</body></html>"
    )
    png_path = OUT / f"{svg_path.stem}.png"
    subprocess.run(
        [
            str(CHROME),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=2",
            f"--window-size={width},{height}",
            f"--screenshot={png_path}",
            html_path.as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    html_path.unlink(missing_ok=True)


def main() -> None:
    figures = {
        "01_loop.svg": loop(),
        "02_headline.svg": headline(),
        "03_generalization.svg": generalization(),
        "04_learning.svg": learning(),
        "05_behaviour.svg": behaviour(),
        "06_ablations.svg": ablations(),
        "07_k_sweep.svg": k_sweep(),
    }
    for name, drawing in figures.items():
        path = drawing.save(name)
        _rasterize(path, drawing.w, drawing.h)
        print(path.name)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
