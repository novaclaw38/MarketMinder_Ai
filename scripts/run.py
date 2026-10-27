#!/usr/bin/env python3
"""
MarketMinder AI - Main Entry Point
Run this script to start the fully automated company
"""

import os
import sys
import asyncio
import signal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from api.main import main_app
from core.mission_control import mission_control
import uvicorn
import logging

logger = logging.getLogger(__name__)


def setup_environment():
    """Setup environment variables for development"""
    env_vars = {
        "STRIPE_SECRET_KEY": "sk_test_dummy_for_development",
        "STRIPE_WEBHOOK_SECRET": "whsec_dummy_for_development",
        "OPENAI_API_KEY": "sk-dummy-for-development",
        "DATABASE_URL": "sqlite:///./marketminder.db",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "development-secret-key-change-in-production",
        "INITIAL_CASH_BALANCE": "25000"
    }
    
    for key, value in env_vars.items():
        if not os.getenv(key):
            os.environ[key] = value
    
    logger.info("Environment configured")


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info("Shutdown signal received, stopping agents...")
    sys.exit(0)


async def run_with_agents():
    """Run the application with all agents"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    setup_environment()
    
    # Run uvicorn server
    logger.info("Starting MarketMinder AI Mission Control...")
    logger.info("Dashboard: http://localhost:8000/")
    logger.info("API Docs: http://localhost:8000/docs")
    logger.info("Mission Control: http://localhost:8000/dashboard")
    
    config = uvicorn.Config(
        main_app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )
    
    server = uvicorn.Server(config)
    
    # Start server
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(run_with_agents())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")