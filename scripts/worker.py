"""
Agent worker: runs the Python agents under Mission Control and mirrors their
health and business metrics into Supabase so the Vercel dashboard stays live.

Usage: python -m scripts.worker   (from the repo root)
"""

import asyncio
import logging
import os

from agents import (
    AgentConfig,
    CustomerSuccessAgent,
    FinanceControllerAgent,
    MarketingEngineAgent,
    MarketScoutAgent,
    ProductBuilderAgent,
    SalesCloserAgent,
)
from core.mission_control import mission_control
from core.supabase_sync import SupabaseSync
from core.venture import VentureEngine
from core.venture_store import VentureStore

logger = logging.getLogger("worker")

SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL_SECONDS", "30"))
VENTURE_INTERVAL = int(os.environ.get("VENTURE_INTERVAL_SECONDS", "300"))


def build_agents():
    def cfg(name: str, description: str) -> AgentConfig:
        return AgentConfig(name=name, description=description)

    agents = [
        MarketScoutAgent(cfg("market_scout", "Market research")),
        ProductBuilderAgent(cfg("product_builder", "Reports and insights")),
        MarketingEngineAgent(cfg("marketing_engine", "Content and leads")),
        CustomerSuccessAgent(cfg("customer_success", "Support and retention")),
        SalesCloserAgent(cfg("sales_closer", "Pipeline and deals")),
    ]

    db_url, stripe_key = os.environ.get("DATABASE_URL"), os.environ.get("STRIPE_SECRET_KEY")
    if db_url and stripe_key:
        agents.append(FinanceControllerAgent(cfg("finance_controller", "Billing and cash flow"), db_url, stripe_key))
    else:
        logger.warning("DATABASE_URL/STRIPE_SECRET_KEY not set; finance_controller not started")
    return agents


async def sync_once(sync: SupabaseSync) -> None:
    for name, agent in mission_control.agents.items():
        await sync.sync_agent(
            name,
            agent.status.value,
            agent.completed_tasks,
            agent.failed_tasks,
            len(agent.tasks),
        )
    dashboard = mission_control.get_system_dashboard()
    await sync.sync_business(dashboard["health_score"], dashboard["metrics"])


async def venture_loop(engine: VentureEngine) -> None:
    while True:
        try:
            await engine.tick()
        except Exception as e:
            logger.error(f"Venture tick failed: {e}")
        await asyncio.sleep(VENTURE_INTERVAL)


async def main():
    logging.basicConfig(level=logging.INFO)
    sync = SupabaseSync()
    for agent in build_agents():
        mission_control.register_agent(agent)
    await mission_control.start()
    venture_task = asyncio.create_task(venture_loop(VentureEngine(VentureStore())))

    try:
        while True:
            try:
                await sync_once(sync)
            except Exception as e:
                logger.error(f"Supabase sync failed: {e}")
            await asyncio.sleep(SYNC_INTERVAL)
    finally:
        venture_task.cancel()
        await mission_control.stop()
        await sync.close()


if __name__ == "__main__":
    asyncio.run(main())
