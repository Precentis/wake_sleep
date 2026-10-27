"""Standard agent interface for the wake phase."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    @abstractmethod
    def run(self, task: dict[str, Any], documents: str, memory: list[dict[str, Any]],
            tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Run one task. Returns a result dict with at least: task_id, deliverable, trajectory,
        tool_calls, documents_read, search_queries, input_tokens, output_tokens, latency_ms, cost_usd."""
