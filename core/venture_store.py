"""Supabase (PostgREST) access for the venture engine."""

import os
from typing import Any, Dict, List, Optional

import httpx


class VentureStore:
    def __init__(self, url: Optional[str] = None, service_key: Optional[str] = None, client: Optional[httpx.AsyncClient] = None):
        if client is not None:
            self._client = client
            return
        url = url or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
        key = service_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError("NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        self._client = httpx.AsyncClient(
            base_url=f"{url.rstrip('/')}/rest/v1",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=15,
        )

    async def close(self):
        await self._client.aclose()

    async def select(self, table: str, **params: str) -> List[Dict[str, Any]]:
        res = await self._client.get(f"/{table}", params=params)
        res.raise_for_status()
        return res.json()

    async def insert(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        res = await self._client.post(f"/{table}", headers={"Prefer": "return=representation"}, json=row)
        res.raise_for_status()
        return res.json()[0]

    async def insert_ignore_duplicate(self, table: str, row: Dict[str, Any], on_conflict: str) -> None:
        res = await self._client.post(
            f"/{table}",
            params={"on_conflict": on_conflict},
            headers={"Prefer": "resolution=ignore-duplicates"},
            json=row,
        )
        res.raise_for_status()

    async def patch(self, table: str, match: Dict[str, str], values: Dict[str, Any]) -> None:
        res = await self._client.patch(f"/{table}", params=match, json=values)
        res.raise_for_status()

    async def pnl(self, division_id: str) -> Dict[str, int]:
        rows = await self.select("division_pnl", division_id=f"eq.{division_id}")
        return rows[0] if rows else {"revenue_cents": 0, "refund_cents": 0, "cost_cents": 0, "profit_cents": 0}
