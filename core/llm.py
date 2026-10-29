"""Minimal chat client (Groq by default, OpenAI as fallback) returning JSON plus a cost estimate."""

import json
import os
from typing import Any, Dict, Optional, Tuple

import httpx

# USD per 1M tokens; defaults match llama-3.3-70b-versatile on Groq. Override via env if the model changes.
PRICE_IN = float(os.environ.get("LLM_PRICE_IN_PER_M", "0.59"))
PRICE_OUT = float(os.environ.get("LLM_PRICE_OUT_PER_M", "0.79"))


def _provider():
    """Returns (url, key, model) for the configured provider, or None."""
    if os.environ.get("GROQ_API_KEY"):
        return ("https://api.groq.com/openai/v1/chat/completions", os.environ["GROQ_API_KEY"],
                os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"))
    if os.environ.get("OPENAI_API_KEY"):
        return ("https://api.openai.com/v1/chat/completions", os.environ["OPENAI_API_KEY"],
                os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    return None


class LLMUnavailable(RuntimeError):
    pass


async def chat_json(system: str, user: str) -> Tuple[Dict[str, Any], int]:
    """Returns (parsed JSON, cost in cents, rounded up). Raises LLMUnavailable without a key."""
    provider = _provider()
    if not provider:
        raise LLMUnavailable("GROQ_API_KEY is not set")
    url, key, model = provider
    async with httpx.AsyncClient(timeout=90) as client:
        res = await client.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
    res.raise_for_status()
    body = res.json()
    usage = body.get("usage", {})
    dollars = (usage.get("prompt_tokens", 0) * PRICE_IN + usage.get("completion_tokens", 0) * PRICE_OUT) / 1_000_000
    cost_cents = max(1, int(-(-dollars * 100 // 1)))
    return json.loads(body["choices"][0]["message"]["content"]), cost_cents
