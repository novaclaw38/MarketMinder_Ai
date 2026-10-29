"""
Venture engine: researches business ideas, launches them as divisions with their own
agents, budget and P&L, and deletes any division that has not made a profit within its window.

Autonomy model: no human approval is requested at runtime. Safety comes from hard limits in
core/policy.py (forbidden categories, allowed actions) and from budget caps enforced here.
"""

import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from core import channels as channel_mod, llm, policy
from core.venture_store import VentureStore

logger = logging.getLogger("venture")

HONESTY_RULES = (
    "Rules you must follow: never invent statistics, quotes, testimonials, customer names or sources; "
    "if you are not sure of a fact, leave it out or say it is an estimate. Say plainly that the content "
    "is AI-generated. Do not give financial, legal or medical advice. Do not promise results."
)


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def now() -> datetime:
    return datetime.now(timezone.utc)


def slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]
    return f"{base}-{uuid.uuid4().hex[:6]}"


class VentureEngine:
    def __init__(self, store: VentureStore, channels: Optional[List[channel_mod.Channel]] = None,
                 indexnow: Optional[channel_mod.IndexNow] = None):
        self.store = store
        self.channels = channel_mod.build_channels() if channels is None else channels
        self.indexnow = indexnow or channel_mod.IndexNow()
        self.site_url = os.environ.get("SITE_URL", "").rstrip("/")
        self.daily_post_cap = _env_int("DAILY_POST_CAP_PER_CHANNEL", 3)
        self.max_divisions = _env_int("MAX_ACTIVE_DIVISIONS", 3)
        self.division_budget = _env_int("DIVISION_BUDGET_CENTS", 2000)
        self.global_budget = _env_int("GLOBAL_BUDGET_CENTS", 6000)
        self.lifetime_loss_cap = _env_int("LIFETIME_LOSS_CAP_CENTS", 10000)
        self.window = timedelta(days=_env_int("WINDOW_DAYS", 7))
        self.max_agents = _env_int("MAX_AGENTS_PER_DIVISION", 8)
        self.currency = os.environ.get("DEFAULT_CURRENCY", "usd")

    # ---- main loop -------------------------------------------------------

    async def tick(self) -> None:
        for division in await self._active():
            await self.evaluate(division)
        await self.launch_if_capacity()
        for division in await self._active():
            try:
                await self.run_agents(division)
            except llm.LLMUnavailable:
                await self.log(division, "system", "blocked", "GROQ_API_KEY missing; division cannot work")
            except Exception as e:
                logger.exception("division %s step failed", division["slug"])
                await self.log(division, "system", "error", f"step failed: {e}")

    async def _active(self) -> List[Dict[str, Any]]:
        return await self.store.select("divisions", status="eq.active", order="started_at.asc")

    # ---- the deadline: profit or be deleted --------------------------------

    async def evaluate(self, division: Dict[str, Any]) -> None:
        pnl = await self.store.pnl(division["id"])
        cycle_profit = pnl["profit_cents"] - division["baseline_profit_cents"]
        deadline = datetime.fromisoformat(division["deadline"])

        if pnl["cost_cents"] >= division["budget_cents"] and cycle_profit <= 0:
            await self.wind_down(division, "budget exhausted without profit")
        elif now() >= deadline:
            if cycle_profit > 0:
                await self.store.patch("divisions", {"id": f"eq.{division['id']}"}, {
                    "cycle": division["cycle"] + 1,
                    "baseline_profit_cents": pnl["profit_cents"],
                    "deadline": (now() + self.window).isoformat(),
                })
                await self.log(division, "orchestrator", "renewed",
                               f"Profit {cycle_profit}c this cycle; renewed for another window")
            else:
                await self.wind_down(division, "no profit within the window")

    async def wind_down(self, division: Dict[str, Any], reason: str) -> None:
        """Delete a division: stop selling, retire agents, keep the ledger for accounting."""
        did = f"eq.{division['id']}"
        await self.store.patch("divisions", {"id": did}, {
            "status": "deleted", "ended_at": now().isoformat(), "end_reason": reason})
        await self.store.patch("division_agents", {"division_id": did}, {"status": "retired"})
        await self.store.patch("products", {"division_id": did}, {"status": "archived"})
        await self.store.patch("articles", {"division_id": did}, {"status": "archived"})
        await self.log(division, "orchestrator", "deleted", f"Division deleted: {reason}")
        logger.warning("Deleted division %s: %s", division["name"], reason)

    # ---- research and launch ----------------------------------------------

    async def launch_if_capacity(self) -> None:
        active = await self._active()
        capacity = self.max_divisions - len(active)
        committed = sum(d["budget_cents"] for d in active)
        if capacity <= 0 or committed + self.division_budget > self.global_budget:
            return

        all_pnl = await self.store.select("division_pnl")
        if sum(p["profit_cents"] for p in all_pnl) <= -self.lifetime_loss_cap:
            logger.error("Lifetime loss cap reached; not launching new divisions")
            return

        try:
            ideas, cost = await self.research(await self._lessons())
        except llm.LLMUnavailable:
            logger.warning("GROQ_API_KEY missing; cannot research")
            return

        launched = []
        for idea in sorted(ideas, key=lambda i: i.get("score", 0), reverse=True):
            if len(launched) >= min(capacity, (self.global_budget - committed) // self.division_budget):
                break
            ok, why = policy.screen_idea(idea)
            if not ok:
                logger.info("Rejected idea %r: %s", idea.get("name"), why)
                continue
            launched.append(await self.spawn_division(idea))
        for division in launched:
            await self.cost(division, cost // len(launched), "Market research")

    async def _lessons(self) -> List[str]:
        dead = await self.store.select("divisions", status="eq.deleted", select="name,thesis,end_reason", limit="10")
        return [f"{d['name']}: {d['thesis']} (deleted: {d['end_reason']})" for d in dead]

    async def research(self, lessons: List[str]) -> tuple:
        system = (
            "You are a venture analyst picking businesses that can earn their first profit within 7 days "
            "with almost no capital, run entirely by software. Each must sell a digital product that can be "
            "generated and delivered instantly and automatically, to a clearly defined audience, and be "
            "discoverable through search-indexed web pages. Prefer a narrow niche with an urgent, specific need "
            "and a low price (USD 5-49). " + HONESTY_RULES + " Reply as JSON: "
            '{"ideas":[{"name":str,"thesis":str,"audience":str,"product_title":str,"price_cents":int,'
            '"score":number 1-10,"why_it_could_work_this_week":str}]}. Give 5 distinct ideas.'
        )
        user = "Failed before (avoid repeating): " + ("; ".join(lessons) if lessons else "nothing yet")
        data, cost = await llm.chat_json(system, user)
        return data.get("ideas", []), cost

    async def spawn_division(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        division = await self.store.insert("divisions", {
            "name": idea["name"], "slug": slugify(idea["name"]), "thesis": idea["thesis"],
            "audience": idea["audience"], "budget_cents": self.division_budget,
            "score": idea.get("score", 0), "deadline": (now() + self.window).isoformat(),
        })
        division["_idea"] = idea
        for role in ("researcher", "builder", "marketer"):
            await self.spawn_agent(division, role, "initial team")
        await self.log(division, "orchestrator", "launched",
                       f"Launched '{idea['name']}' for {idea['audience']}; deadline {division['deadline']}",
                       {"idea": idea})
        return division

    # ---- agents -------------------------------------------------------------

    async def spawn_agent(self, division: Dict[str, Any], role: str, reason: str) -> bool:
        agents = await self.store.select("division_agents", division_id=f"eq.{division['id']}", status="neq.retired")
        if len(agents) >= self.max_agents:
            return False
        await self.store.insert("division_agents", {
            "division_id": division["id"], "role": role, "spawned_reason": reason})
        await self.log(division, "orchestrator", "agent_spawned", f"Spawned {role}: {reason}")
        return True

    async def _touch_agent(self, division: Dict[str, Any], role: str) -> None:
        agents = await self.store.select("division_agents", division_id=f"eq.{division['id']}",
                                         role=f"eq.{role}", status="neq.retired", limit="1")
        if agents:
            await self.store.patch("division_agents", {"id": f"eq.{agents[0]['id']}"}, {
                "tasks_completed": agents[0]["tasks_completed"] + 1, "last_active_at": now().isoformat()})

    async def run_agents(self, division: Dict[str, Any]) -> None:
        pnl = await self.store.pnl(division["id"])
        if pnl["cost_cents"] >= division["budget_cents"]:
            return  # out of budget: wait for revenue or the deadline
        products = await self.store.select("products", division_id=f"eq.{division['id']}", status="eq.published")
        started = datetime.fromisoformat(division["started_at"])

        if not products:
            await self.build_product(division)
            return

        # Scale rules: agents are added only when they have evidence to act on
        if pnl["revenue_cents"] > 0:
            await self.spawn_agent(division, "support", "first revenue received")
            if pnl["profit_cents"] > 0 and (pnl["profit_cents"] // 2000) >= 1:
                await self.spawn_agent(division, "marketer", "profit funds more content")
        elif now() - started >= timedelta(days=2) and len(products) < 2:
            await self.spawn_agent(division, "experimenter", "no revenue after 2 days: test a new offer")
            await self.build_product(division, variant_of=products[0])
            return

        recent = await self.store.select(
            "articles", division_id=f"eq.{division['id']}",
            created_at=f"gte.{(now() - timedelta(hours=12)).isoformat()}")
        if len(recent) < 2:
            await self.publish_article(division, products[0])

    # ---- work: build, review, publish -------------------------------------------

    async def build_product(self, division: Dict[str, Any], variant_of: Optional[Dict[str, Any]] = None) -> None:
        context = f"Business: {division['name']}. Thesis: {division['thesis']}. Audience: {division['audience']}."
        if variant_of:
            context += (f" The existing offer '{variant_of['title']}' at {variant_of['price_cents']}c has not sold. "
                        "Create a clearly different offer: new angle or format, different price point.")
        system = (
            "You create a single digital product that is delivered instantly as text. " + HONESTY_RULES +
            " The deliverable must be genuinely useful and specific (a checklist, template pack, structured guide "
            "or worked analysis), 500-900 words, markdown. Reply as JSON: "
            '{"title":str,"description":str (max 60 words, honest, no hype),"price_cents":int,"deliverable":str}.'
        )
        data, cost = await llm.chat_json(system, context)
        await self.cost(division, cost, "Product drafting")

        ok, why = policy.screen_text(f"{data.get('title','')} {data.get('description','')} {data.get('deliverable','')}")
        price = data.get("price_cents")
        if not ok or not isinstance(price, int) or not policy.MIN_PRICE_CENTS <= price <= policy.MAX_PRICE_CENTS:
            await self.log(division, "builder", "rejected", f"Product failed policy screen: {why or 'bad price'}")
            return

        review, rcost = await llm.chat_json(
            "You are a strict reviewer. Reject content that contains invented statistics, fake sources or quotes, "
            "unprovable claims, financial/legal/medical advice, or that is generic filler. Reply as JSON: "
            '{"approved":bool,"issues":[str]}.', data["deliverable"] + "\n\nDescription: " + data["description"])
        await self.cost(division, rcost, "Product review")
        if not review.get("approved"):
            await self.log(division, "reviewer", "rejected", "Product rejected by reviewer",
                           {"issues": review.get("issues", [])})
            return

        product = await self.store.insert("products", {
            "division_id": division["id"], "slug": slugify(data["title"]), "title": data["title"],
            "description": data["description"], "price_cents": price, "currency": self.currency,
            "deliverable": data["deliverable"]})
        await self._touch_agent(division, "builder")
        await self.log(division, "builder", "product_published",
                       f"Published '{product['title']}' at {price}c: /p/{product['slug']}")
        await self.distribute(division, "product", product["title"], f"/p/{product['slug']}")

    async def publish_article(self, division: Dict[str, Any], product: Dict[str, Any]) -> None:
        system = (
            "You write one helpful, search-friendly article (400-700 words, markdown) for the audience below that "
            "teaches something real and naturally leads to the product, which you may mention once at the end "
            "without hype. " + HONESTY_RULES + ' Reply as JSON: {"title":str,"body":str}.')
        user = (f"Audience: {division['audience']}. Product: {product['title']} - {product['description']}. "
                "Pick a specific question this audience would search for.")
        data, cost = await llm.chat_json(system, user)
        await self.cost(division, cost, "Article drafting")
        ok, why = policy.screen_text(f"{data.get('title','')} {data.get('body','')}")
        if not ok:
            await self.log(division, "marketer", "rejected", f"Article failed policy screen: {why}")
            return
        article = await self.store.insert("articles", {
            "division_id": division["id"], "product_id": product["id"],
            "slug": slugify(data["title"]), "title": data["title"], "body": data["body"]})
        await self._touch_agent(division, "marketer")
        await self.log(division, "marketer", "article_published", f"Published article: /blog/{article['slug']}")
        await self.distribute(division, "article", article["title"], f"/blog/{article['slug']}", article["body"])

    # ---- distribution -------------------------------------------------------------

    async def distribute(self, division: Dict[str, Any], kind: str, title: str, path: str,
                         body: Optional[str] = None) -> None:
        """Announce new content on every enabled channel, within per-channel daily caps."""
        if not self.site_url or not policy.action_allowed("distribute_post"):
            return
        url = f"{self.site_url}{path}"
        since = (now() - timedelta(hours=24)).isoformat()
        async with httpx.AsyncClient(timeout=20) as client:
            if self.indexnow.enabled():
                try:
                    await self.indexnow.ping(client, url)
                    await self.log(division, "marketer", "indexed", f"Submitted {path} to IndexNow")
                except Exception as e:
                    logger.warning("IndexNow failed: %s", e)

            for channel in self.channels:
                if kind == "product" and channel.name == "devto":
                    continue
                recent = await self.store.select(
                    "distributions", division_id=f"eq.{division['id']}", channel=f"eq.{channel.name}",
                    status="eq.posted", created_at=f"gte.{since}")
                if len(recent) >= self.daily_post_cap:
                    continue
                row = {"division_id": division["id"], "channel": channel.name, "kind": kind, "target_url": url}
                try:
                    ref = await channel.post(client, title, url, body)
                    await self.store.insert("distributions", {**row, "status": "posted", "external_ref": ref})
                    await self.log(division, "marketer", "distributed", f"Posted to {channel.name}: {ref}")
                except Exception as e:
                    # One failure must not trigger retries or a posting storm
                    await self.store.insert("distributions", {**row, "status": "failed", "error": str(e)[:300]})
                    await self.log(division, "marketer", "distribution_failed", f"{channel.name} failed: {e}")

    # ---- bookkeeping ----------------------------------------------------------------

    async def cost(self, division: Dict[str, Any], cents: int, description: str) -> None:
        await self.store.insert("ledger", {
            "division_id": division["id"], "kind": "cost", "amount_cents": cents,
            "description": description, "ref": f"cost:{uuid.uuid4()}"})

    async def log(self, division: Dict[str, Any], role: str, kind: str, summary: str,
                  payload: Optional[Dict[str, Any]] = None) -> None:
        await self.store.insert("activity_log", {
            "division_id": division["id"], "agent_role": role, "kind": kind,
            "summary": summary, "payload": payload})
