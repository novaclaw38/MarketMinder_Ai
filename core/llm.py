"""Minimal OpenAI chat client returning JSON plus a cost estimate."""

import json
import os
from typing import Any, Dict, Optional, Tuple

import httpx

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
# USD per 1M tokens for the default model; override via env if the model changes
PRICE_IN = float(os.environ.get("LLM_PRICE_IN_PER_M", "0.15"))
PRICE_OUT = float(os.environ.get("LLM_PRICE_OUT_PER_M", "0.60"))


class LLMUnavailable(RuntimeError):
    pass


async def chat_json(system: str, user: str) -> Tuple[Dict[str, Any], int]:
    """Returns (parsed JSON, cost in cents, rounded up). Raises LLMUnavailable without a key."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise LLMUnavailable("OPENAI_API_KEY is not set")
    async with httpx.AsyncClient(timeout=90) as client:
        res = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": MODEL,
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
