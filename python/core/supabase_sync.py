"""
Supabase sync for MarketMinder AI
Mirrors agent health and business metrics into the tables the Vercel
dashboard reads (agent_status, health_check, metrics) via PostgREST.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseSync:
    def __init__(self, url: Optional[str] = None, service_key: Optional[str] = None):
        url = url or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
        key = service_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError("NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        self._client = httpx.AsyncClient(
            base_url=f"{url.rstrip('/')}/rest/v1",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=15,
        )
        # tasks/errors already reported per agent, so each sync adds only the delta
        # (the Vercel cron also increments tasks_completed for market_scout)
        self._reported: Dict[str, Dict[str, int]] = {}

    async def close(self):
        await self._client.aclose()

    async def sync_agent(self, name: str, status: str, completed: int, failed: int, queue: int) -> None:
        prev = self._reported.get(name, {"completed": 0, "failed": 0})
        resp = await self._client.get(
            "/agent_status",
            params={"agent_name": f"eq.{name}", "select": "tasks_completed,error_count"},
        )
        resp.raise_for_status()
        rows = resp.json()
        row = rows[0] if rows else {"tasks_completed": 0, "error_count": 0}

        payload = {
            "agent_name": name,
            "status": status,
            "last_updated": _now(),
            "tasks_completed": (row["tasks_completed"] or 0) + completed - prev["completed"],
            "error_count": (row["error_count"] or 0) + failed - prev["failed"],
            "queue_length": queue,
        }
        resp = await self._client.post(
            "/agent_status",
            params={"on_conflict": "agent_name"},
            headers={"Prefer": "resolution=merge-duplicates"},
            json=payload,
        )
        resp.raise_for_status()
        self._reported[name] = {"completed": completed, "failed": failed}

    async def sync_business(self, health_score: float, metrics: Dict[str, Any]) -> None:
        health = {
            "health_score": health_score,
            "mrr": metrics.get("mrr", 0),
            "churn_rate": metrics.get("churn_rate", 0),
            "cash_runway_days": int(metrics.get("cash_runway_days", 0)),
            "cac": metrics.get("cac", 0),
            "ltv_cac": metrics.get("ltv_cac_ratio", 0),
            "last_updated": _now(),
        }
        resp = await self._client.patch("/health_check", params={"id": "eq.1"}, json=health)
        resp.raise_for_status()

        for metric_name, value in (
            ("mrr", metrics.get("mrr", 0)),
            ("churn_rate", metrics.get("churn_rate", 0)),
            ("cac", metrics.get("cac", 0)),
            ("ltv_cac", metrics.get("ltv_cac_ratio", 0)),
        ):
            resp = await self._client.patch(
                "/metrics",
                params={"metric_name": f"eq.{metric_name}"},
                json={"value": value, "last_updated": _now()},
            )
            resp.raise_for_status()
