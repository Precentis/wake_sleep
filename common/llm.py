"""Thin, self-contained LLM client for the wake-sleep experiment.

Reads endpoints and keys from a local `.env` when this folder is used on its own,
and otherwise from the monorepo path `legal-memory-retrieval/.env`. Two
OpenAI-compatible backends:
  - azure:   Azure AI Foundry /openai/v1 (agent model)
  - bedrock: Bedrock Mantle /openai/v1 (judges, sleep, gate, dataset author)

Every call returns {content, tool_calls, usage, latency_ms, model, finish_reason}
and retries on 429 / 5xx / timeouts with exponential backoff.
"""

from __future__ import annotations

import json
import random
import re
import threading
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]


def _resolve_env_path() -> Path:
    """Local `.env` first, then the monorepo app env this experiment grew up beside."""
    candidates = (
        ROOT / ".env",
        ROOT.parents[1] / "legal-memory-retrieval" / ".env",
    )
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


ENV_PATH = _resolve_env_path()

_env_cache: dict[str, str] | None = None
_lock = threading.Lock()


def _env() -> dict[str, str]:
    global _env_cache
    if _env_cache is None:
        vals: dict[str, str] = {}
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
        _env_cache = vals
    return _env_cache


def _endpoint(provider: str, model: str = "") -> tuple[str, dict[str, str]]:
    env = _env()
    if provider == "azure":
        base = env["AZURE_OPENAI_ENDPOINT"].rstrip("/")
        key = env["AZURE_OPENAI_API_KEY"]
        headers = {"api-key": key, "Authorization": f"Bearer {key}"}
    elif provider == "bedrock":
        region = env.get("BEDROCK_REGION", "us-east-1")
        # Mantle serves openai.* models under /openai/v1 and all others under /v1.
        prefix = "/openai/v1" if model.startswith("openai.") else "/v1"
        base = f"https://bedrock-mantle.{region}.api.aws{prefix}"
        headers = {"Authorization": f"Bearer {env['AWS_BEARER_TOKEN_BEDROCK']}"}
    else:
        raise ValueError(provider)
    headers["Content-Type"] = "application/json"
    return f"{base}/chat/completions", headers


# Global usage ledger (per process) — every call is attributed to a role.
USAGE: dict[str, dict[str, float]] = {}


def _record(role: str, usage: dict[str, Any], latency_ms: float) -> None:
    with _lock:
        u = USAGE.setdefault(role, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0})
        u["calls"] += 1
        u["input_tokens"] += int(usage.get("prompt_tokens") or 0)
        u["output_tokens"] += int(usage.get("completion_tokens") or 0)
        u["latency_ms"] += latency_ms


def chat(
    messages: list[dict[str, Any]],
    *,
    model: str,
    provider: str,
    role: str = "misc",
    temperature: float = 0.0,
    max_tokens: int = 4096,
    tools: list[dict[str, Any]] | None = None,
    json_mode: bool = False,
    timeout: float = 240.0,
    max_retries: int = 10,
) -> dict[str, Any]:
    url, headers = _endpoint(provider, model)
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        body["tools"] = tools
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    last_err: Exception | None = None
    for attempt in range(max_retries):
        t0 = time.time()
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, headers=headers, json=body)
            if resp.status_code == 400 and json_mode and "response_format" in resp.text:
                body.pop("response_format", None)
                json_mode = False
                continue
            if resp.status_code in (408, 409, 429) or resp.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"retryable {resp.status_code}: {resp.text[:300]}", request=resp.request, response=resp
                )
            resp.raise_for_status()
            data = resp.json()
            latency_ms = (time.time() - t0) * 1000
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            usage = data.get("usage") or {}
            _record(role, usage, latency_ms)
            return {
                "content": msg.get("content") or "",
                "tool_calls": msg.get("tool_calls") or [],
                "usage": {
                    "input_tokens": int(usage.get("prompt_tokens") or 0),
                    "output_tokens": int(usage.get("completion_tokens") or 0),
                },
                "latency_ms": latency_ms,
                "model": model,
                "finish_reason": choice.get("finish_reason"),
            }
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            last_err = e
            if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
                code = e.response.status_code
                if 400 <= code < 500 and code not in (408, 409, 429):
                    raise
            time.sleep(min(60, (2**attempt) + random.random() * 2))
    raise RuntimeError(f"LLM call failed after {max_retries} retries: {last_err}")


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_json(text: str) -> Any:
    """Parse the first JSON object/array in an LLM response (tolerates fences/prose)."""
    text = (text or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    for candidate in [text, *(_JSON_FENCE.findall(text))]:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError(f"no JSON in response: {text[:200]}")
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError(f"unterminated JSON in response: {text[:200]}")


def chat_json(
    messages: list[dict[str, Any]], *, model: str, provider: str, role: str, max_tokens: int = 4096,
    retries: int = 3, **kw: Any
) -> tuple[Any, dict[str, Any]]:
    """Call and parse JSON; re-ask on parse failure. Returns (parsed, raw_response)."""
    last: Exception | None = None
    msgs = list(messages)
    for _ in range(retries):
        r = chat(msgs, model=model, provider=provider, role=role, max_tokens=max_tokens, **kw)
        try:
            return parse_json(r["content"]), r
        except (ValueError, json.JSONDecodeError) as e:
            last = e
            msgs = list(messages) + [
                {"role": "assistant", "content": r["content"][:4000]},
                {"role": "user", "content": "Your reply was not valid JSON. Reply again with ONLY the JSON object."},
            ]
    raise RuntimeError(f"JSON parse failed: {last}")
