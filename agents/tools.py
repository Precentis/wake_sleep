"""Matter workspace tools available to the legal agent.

The workspace is a read-only document folder plus one mutable draft (the deliverable).
`calculate` is a restricted expression evaluator (arithmetic + date helpers) — it never
executes arbitrary code.
"""

from __future__ import annotations

import ast
import calendar
import datetime as dt
import math
import operator
import re
from pathlib import Path
from typing import Any

TOOL_SPECS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "list_documents", "description": "List the documents in the matter folder with their line counts.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "read_document", "description": "Read a document (numbered lines). Use start_line/num_lines to page.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "start_line": {"type": "integer", "default": 1},
            "num_lines": {"type": "integer", "default": 200}}, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "search_documents", "description": "Keyword search across all matter documents; returns matching lines with document name and line number.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "calculate",
        "description": ("Evaluate arithmetic and date expressions, one per line; 'x = expr' assigns. Functions: "
                        "date('YYYY-MM-DD'), add_days(d,n), add_months(d,n), add_years(d,n), days_between(a,b), "
                        "weekday(d), next_business_day(d), prev_business_day(d), round, abs, min, max, sum, pct(part,whole)."),
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}},
    {"type": "function", "function": {
        "name": "write_draft", "description": "Create or fully replace the deliverable draft (Markdown).",
        "parameters": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}}},
    {"type": "function", "function": {
        "name": "edit_draft", "description": "Replace an exact passage of the draft with new text.",
        "parameters": {"type": "object", "properties": {"find": {"type": "string"}, "replace": {"type": "string"}},
                       "required": ["find", "replace"]}}},
    {"type": "function", "function": {
        "name": "read_draft", "description": "Read the current deliverable draft.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "finish", "description": "Submit the current draft as the final deliverable.",
        "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}}}},
]

RESEARCH_TOOLS = {"list_documents", "read_document", "search_documents"}
ANALYSIS_TOOLS = {"calculate"}
DRAFTING_TOOLS = {"write_draft", "edit_draft"}


# ------------------------------------------------------------------ calculator
def _d(x: Any) -> dt.date:
    if isinstance(x, dt.date):
        return x
    return dt.date.fromisoformat(str(x))


def _add_months(d: Any, n: int) -> dt.date:
    d = _d(d)
    m = d.month - 1 + int(n)
    y = d.year + m // 12
    m = m % 12 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _nbd(d: Any) -> dt.date:
    d = _d(d)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def _pbd(d: Any) -> dt.date:
    d = _d(d)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


FUNCS = {
    "date": lambda s, *rest: dt.date(int(s), *map(int, rest)) if rest else _d(s),
    "add_days": lambda d, n: _d(d) + dt.timedelta(days=int(n)),
    "add_months": _add_months,
    "add_years": lambda d, n: _add_months(d, 12 * int(n)),
    "days_between": lambda a, b: (_d(b) - _d(a)).days,
    "weekday": lambda d: _d(d).strftime("%A"),
    "next_business_day": _nbd, "prev_business_day": _pbd,
    "round": round, "abs": abs, "min": min, "max": max, "sum": sum, "int": int, "float": float,
    "pct": lambda part, whole: 100.0 * part / whole, "sqrt": math.sqrt,
}
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
       ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
       ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval(node: ast.AST, env: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, env)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        left, right = _eval(node.left, env), _eval(node.right, env)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("exponent too large")
        if isinstance(left, dt.date) and isinstance(right, dt.date) and isinstance(node.op, ast.Sub):
            return (left - right).days
        if isinstance(left, dt.date) and isinstance(right, (int, float)):
            return left + dt.timedelta(days=int(right if isinstance(node.op, ast.Add) else -right))
        return OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand, env))
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        raise ValueError(f"unknown name {node.id}")
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(e, env) for e in node.elts]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS:
        return FUNCS[node.func.id](*[_eval(a, env) for a in node.args])
    raise ValueError(f"unsupported expression: {ast.dump(node)[:80]}")


def calculate(expression: str) -> str:
    env: dict[str, Any] = {}
    out = []
    for raw in re.split(r"[\n;]+", expression):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            m = re.match(r"^([A-Za-z_]\w*)\s*=(?!=)\s*(.+)$", line)
            target, expr = (m.group(1), m.group(2)) if m else (None, line)
            expr = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", expr.replace("$", ""))  # 1,250,000 -> 1250000
            val = _eval(ast.parse(expr, mode="eval"), env)
            if target:
                env[target] = val
            shown = val.isoformat() + f" ({val.strftime('%A')})" if isinstance(val, dt.date) else (
                f"{val:,.4f}".rstrip("0").rstrip(".") if isinstance(val, float) else str(val))
            out.append(f"{line} => {shown}")
        except Exception as e:  # noqa: BLE001 — report any evaluation error to the agent
            out.append(f"{line} => ERROR: {e}")
    return "\n".join(out) or "ERROR: empty expression"


# ------------------------------------------------------------------ workspace
class Workspace:
    def __init__(self, doc_dir: Path):
        self.docs = {p.name: p.read_text() for p in sorted(Path(doc_dir).glob("*.md"))}
        self.draft: str = ""
        self.draft_versions: list[str] = []

    def list_documents(self) -> str:
        return "\n".join(f"{n} ({len(t.splitlines())} lines)" for n, t in self.docs.items())

    def read_document(self, name: str, start_line: int = 1, num_lines: int = 200) -> str:
        if name not in self.docs:
            cand = [n for n in self.docs if name.lower().replace(".md", "") in n.lower()]
            if len(cand) != 1:
                return f"ERROR: no document named {name!r}. Available: {', '.join(self.docs)}"
            name = cand[0]
        lines = self.docs[name].splitlines()
        s = max(1, int(start_line or 1))
        e = min(len(lines), s - 1 + max(1, min(int(num_lines or 200), 400)))
        body = "\n".join(f"{i:>4}| {lines[i - 1]}" for i in range(s, e + 1))
        more = f"\n[... {len(lines) - e} more lines]" if e < len(lines) else ""
        return f"== {name} (lines {s}-{e} of {len(lines)}) ==\n{body}{more}"

    def search_documents(self, query: str) -> str:
        terms = [t for t in re.findall(r"[a-z0-9%$.,]+", query.lower()) if len(t) > 1]
        hits = []
        for n, t in self.docs.items():
            for i, line in enumerate(t.splitlines(), 1):
                low = line.lower()
                score = sum(1 for term in terms if term in low)
                if score:
                    hits.append((score, n, i, line.strip()))
        hits.sort(key=lambda h: (-h[0], h[1], h[2]))
        if not hits:
            return "No matches."
        return "\n".join(f"{n}:{i}: {line[:300]}" for _, n, i, line in hits[:12])

    def write_draft(self, content: str) -> str:
        self.draft = content or ""
        self.draft_versions.append(self.draft)
        return f"Draft saved ({len(self.draft.split())} words)."

    def edit_draft(self, find: str, replace: str) -> str:
        if not find or find not in self.draft:
            return "ERROR: passage not found in draft (it must match exactly)."
        self.draft = self.draft.replace(find, replace, 1)
        self.draft_versions.append(self.draft)
        return f"Draft edited ({len(self.draft.split())} words)."

    def read_draft(self) -> str:
        return self.draft or "(draft is empty)"
