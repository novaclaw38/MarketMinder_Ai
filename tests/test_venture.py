import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from core import llm, venture
from core.venture import VentureEngine


class FakeStore:
    """In-memory stand-in for VentureStore supporting the filters the engine uses."""

    def __init__(self):
        self.t = {k: [] for k in ["divisions", "division_agents", "activity_log", "products", "articles", "ledger"]}

    @staticmethod
    def _match(row, params):
        for k, v in params.items():
            if k in ("order", "limit", "select"):
                continue
            op, _, val = v.partition(".")
            cur = row.get(k)
            if op == "eq" and str(cur) != val:
                return False
            if op == "neq" and str(cur) == val:
                return False
            if op == "gte" and not (cur is not None and cur >= val):
                return False
        return True

    async def select(self, table, **params):
        if table == "division_pnl":
            out = []
            for d in self.t["divisions"]:
                led = [l for l in self.t["ledger"] if l["division_id"] == d["id"]]
                s = lambda k: sum(l["amount_cents"] for l in led if l["kind"] == k)
                out.append({"division_id": d["id"], "revenue_cents": s("revenue"), "refund_cents": s("refund"),
                            "cost_cents": s("cost"), "profit_cents": s("revenue") - s("refund") - s("cost")})
            return [r for r in out if self._match(r, params)]
        rows = [r for r in self.t[table] if self._match(r, params)]
        return rows[: int(params["limit"])] if "limit" in params else rows

    async def insert(self, table, row):
        row = {"id": str(uuid.uuid4()), "status": "active" if table == "divisions" else "idle",
               "tasks_completed": 0, "cycle": 1, "baseline_profit_cents": 0,
               "started_at": datetime.now(timezone.utc).isoformat(),
               "created_at": datetime.now(timezone.utc).isoformat(), **row}
        if table in ("products", "articles"):
            row["status"] = "published"
        self.t[table].append(row)
        return row

    async def patch(self, table, match, values):
        for r in self.t[table]:
            if self._match(r, match):
                r.update(values)

    async def pnl(self, division_id):
        return (await self.select("division_pnl", division_id=f"eq.{division_id}"))[0]


IDEA = {"name": "Cafe Price Check", "thesis": "Small cafes need quick price benchmarks",
        "audience": "independent cafe owners", "product_title": "Cafe pricing worksheet",
        "price_cents": 900, "score": 8}


@pytest.fixture
def stub_llm(monkeypatch):
    async def chat_json(system, user):
        if "venture analyst" in system:
            return {"ideas": [IDEA, {**IDEA, "name": "Casino Tips", "thesis": "online casino tips", "score": 9}]}, 4
        if "strict reviewer" in system:
            return {"approved": True, "issues": []}, 1
        if "single digital product" in system:
            return {"title": "Cafe pricing worksheet", "description": "A worksheet.", "price_cents": 900,
                    "deliverable": "# Worksheet\n1. List costs"}, 2
        return {"title": "How to price a flat white", "body": "Body text"}, 2

    monkeypatch.setattr(llm, "chat_json", chat_json)


def run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def test_launch_build_publish_and_policy_rejection(stub_llm):
    async def go():
        store = FakeStore()
        engine = VentureEngine(store)
        await engine.tick()
        assert [d["name"] for d in store.t["divisions"]] == ["Cafe Price Check"]  # casino idea rejected
        assert len(store.t["products"]) == 1  # built in the launch tick
        await engine.tick()
        assert len(store.t["articles"]) == 1
        assert {a["role"] for a in store.t["division_agents"]} == {"researcher", "builder", "marketer"}
        assert all(l["kind"] == "cost" for l in store.t["ledger"])
    run(go())


def test_deleted_when_no_profit_at_deadline(stub_llm):
    async def go():
        store = FakeStore()
        engine = VentureEngine(store)
        await engine.tick()
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        store.t["divisions"][0]["deadline"] = past
        await engine.tick()
        d = store.t["divisions"][0]
        assert d["status"] == "deleted" and "no profit" in d["end_reason"]
        # a replacement division launches in the same tick; only the deleted one's assets are retired
        assert all(a["status"] == "retired" for a in store.t["division_agents"] if a["division_id"] == d["id"])
        assert all(p["status"] == "archived" for p in store.t["products"] if p["division_id"] == d["id"])
        assert len([x for x in store.t["divisions"] if x["status"] == "active"]) == 1
    run(go())


def test_renewed_when_profitable_and_support_agent_spawned(stub_llm):
    async def go():
        store = FakeStore()
        engine = VentureEngine(store)
        await engine.tick()
        await engine.tick()
        div = store.t["divisions"][0]
        await store.insert("ledger", {"division_id": div["id"], "kind": "revenue", "amount_cents": 5000, "ref": "r1"})
        await engine.tick()
        assert "support" in {a["role"] for a in store.t["division_agents"]}
        div["deadline"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        await engine.tick()
        assert div["status"] == "active" and div["cycle"] == 2 and div["baseline_profit_cents"] > 0
    run(go())


def test_budget_exhaustion_deletes_unprofitable_division(stub_llm):
    async def go():
        store = FakeStore()
        engine = VentureEngine(store)
        await engine.tick()
        div = store.t["divisions"][0]
        await engine.cost(div, div["budget_cents"], "spent")
        await engine.tick()
        assert div["status"] == "deleted" and "budget" in div["end_reason"]
    run(go())


def test_no_api_key_means_no_launch(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    async def go():
        store = FakeStore()
        await VentureEngine(store).tick()
        assert store.t["divisions"] == []
    run(go())
