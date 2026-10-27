"""Retrieved memory (Condition C): select the top-K lessons relevant to a task.

score = w_sem * semantic_similarity + w_tt * task_type_match + w_pa * practice_area_match
      + w_help * historical_helpfulness + w_gen * general_relevance
then an LLM relevance scorer (the "Jev" role) rates the top 3K candidates and the final
ranking blends both. Weights are experiment parameters (config memory.retrieval_weights).
"""

from __future__ import annotations

import os
import threading
from typing import Any

import numpy as np

from common.config import model_cfg, price
from common.llm import chat_json
from memory.store import Memory

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

_model = None
_model_lock = threading.Lock()
_cache: dict[str, np.ndarray] = {}


def _embed(texts: list[str], model_name: str) -> np.ndarray:
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(model_name, device="cpu")
        missing = [t for t in texts if t not in _cache]
        if missing:
            vecs = _model.encode(missing, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
            for t, v in zip(missing, vecs):
                _cache[t] = v
        return np.stack([_cache[t] for t in texts])


def heuristic_scores(cfg: dict[str, Any], task: dict[str, Any], lessons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    w = cfg["memory"]["retrieval_weights"]
    query = f"{task['task_type'].replace('_', ' ')} | {task['practice_area'].replace('_', ' ')} | {task['instructions']}"
    vecs = _embed([query] + [l["text"] for l in lessons], cfg["embedding_model"])
    sims = (vecs[1:] @ vecs[0] + 1) / 2  # cosine -> [0, 1]
    rows = []
    for l, s in zip(lessons, sims):
        tt = l["scope"].get("task_type", "general")
        pa = l["scope"].get("practice_area", "general")
        tt_m = 1.0 if tt == task["task_type"] else (0.5 if tt == "general" else 0.0)
        pa_m = 1.0 if pa == task["practice_area"] else (0.5 if pa == "general" else 0.0)
        helpf = (l["times_helpful"] + 1) / (l["times_helpful"] + l["times_unhelpful"] + 2)
        gen = 1.0 if l["category"] == "general" else 0.0
        score = (w["semantic"] * float(s) + w["task_type"] * tt_m + w["practice_area"] * pa_m
                 + w["helpfulness"] * helpf + w["general"] * gen)
        rows.append({"lesson_id": l["lesson_id"], "semantic": round(float(s), 4), "task_type_match": tt_m,
                     "practice_area_match": pa_m, "helpfulness": round(helpf, 3), "general": gen,
                     "heuristic_score": round(score, 4)})
    return rows


RERANK_SYSTEM = """You select which lessons from a legal agent's memory will help with a specific task.
Rate each lesson's relevance to THIS task: 3 = directly needed for this task, 2 = likely helpful, 1 = marginal, 0 = irrelevant.
Consider the deliverable type and what the task involves (e.g. a lesson about computing deadlines is irrelevant to a pure conceptual research question with no dates). Return JSON only."""


def retrieve(cfg: dict[str, Any], task: dict[str, Any], memory: Memory, k: int) -> tuple[list[dict[str, Any]], dict]:
    lessons = memory.active()
    trace: dict[str, Any] = {"task_id": task["task_id"], "k": k, "memory_version": memory.version,
                             "n_memory": len(lessons), "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    if not lessons:
        trace["selected"] = []
        return [], trace
    rows = heuristic_scores(cfg, task, lessons)
    rows.sort(key=lambda r: -r["heuristic_score"])
    by_id = {l["lesson_id"]: l for l in lessons}
    pool = rows[: max(k * 3, 15)]
    if cfg["memory"].get("llm_rerank", True) and len(lessons) > k:
        items = "\n".join(f"- {r['lesson_id']}: {by_id[r['lesson_id']]['text']}" for r in pool)
        user = (f"# Task\nType: {task['task_type']} | Practice area: {task['practice_area']}\n{task['instructions']}\n\n"
                f"# Candidate lessons\n{items}\n\nJSON schema: {{\"ratings\": [{{\"lesson_id\": \"L0001\", \"relevance\": 0}}]}}")
        m = model_cfg(cfg, "retrieval")
        try:
            parsed, raw = chat_json([{"role": "system", "content": RERANK_SYSTEM}, {"role": "user", "content": user}],
                                    model=m["model"], provider=m["provider"], role="retrieval", max_tokens=4000)
            ratings = {str(r.get("lesson_id")): float(r.get("relevance") or 0)
                       for r in (parsed or {}).get("ratings", []) if isinstance(r, dict)}
            trace.update(input_tokens=raw["usage"]["input_tokens"], output_tokens=raw["usage"]["output_tokens"],
                         cost_usd=price(cfg, m["model"], raw["usage"]["input_tokens"], raw["usage"]["output_tokens"]))
        except Exception as e:  # noqa: BLE001 — fall back to heuristic ranking
            ratings = {}
            trace["rerank_error"] = str(e)[:300]
        for r in pool:
            r["llm_relevance"] = ratings.get(r["lesson_id"])
            r["final_score"] = round(0.6 * (r["llm_relevance"] or 0) / 3 + 0.4 * r["heuristic_score"], 4)
        pool.sort(key=lambda r: -r["final_score"])
    else:
        for r in pool:
            r["final_score"] = r["heuristic_score"]
    chosen = pool[:k]
    trace["candidates"] = pool
    trace["selected"] = [r["lesson_id"] for r in chosen]
    return [by_id[r["lesson_id"]] for r in chosen], trace
