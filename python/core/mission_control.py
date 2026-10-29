"""
Mission Control - Central Orchestrator for MarketMinder AI
Coordinates all agents, monitors health, handles escalation
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from agents.base_agent import BaseAgent, AgentTask, AgentConfig, AgentStatus

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    OPTIMAL = "optimal"
    YELLOW = "yellow"
    RED = "red"
    CRITICAL = "critical"


@dataclass
class BusinessMetrics:
    mrr: float = 0.0
    arr: float = 0.0
    total_revenue: float = 0.0
    churn_rate: float = 0.0
    cac: float = 0.0
    ltv: float = 0.0
    ltv_cac_ratio: float = 0.0
    cash_balance: float = 25000.0
    cash_runway_days: float = 365.0
    billing_errors: int = 0
    support_tickets_open: int = 0
    conversion_rate: float = 0.0
    lead_count: int = 0


@dataclass
class AgentHealth:
    name: str
    status: AgentStatus
    completed_tasks: int = 0
    failed_tasks: int = 0
    queue_size: int = 0
    last_heartbeat: Optional[datetime] = None


class MissionControl:
    """Central orchestrator for all AI agents"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.health_threshold_optimal = 80.0
        self.health_threshold_yellow = 60.0
        self.health_threshold_red = 40.0
        
        self.metrics = BusinessMetrics()
        self.agent_health: Dict[str, AgentHealth] = {}
        
        # Failure conditions (kill switch triggers)
        self.failure_conditions = {
            "mrr_crash": {"threshold": 1500, "metric": "mrr", "active": False},
            "cash_runway_critical": {"threshold": 30, "metric": "cash_runway_days", "active": False},
            "health_score_crash": {"threshold": 40, "metric": "health_score", "active": False},
            "churn_spike": {"threshold": 10, "metric": "churn_rate", "active": False}
        }
        
        # Review checkpoints
        self.review_points = {
            "week_2": datetime.utcnow() + timedelta(days=14),
            "month_1": datetime.utcnow() + timedelta(days=30),
            "month_2": datetime.utcnow() + timedelta(days=60),
            "month_3": datetime.utcnow() + timedelta(days=90)
        }
        
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False
    
    def register_agent(self, agent: BaseAgent):
        """Register an agent with mission control"""
        self.agents[agent.config.name] = agent
        self.agent_health[agent.config.name] = AgentHealth(
            name=agent.config.name,
            status=AgentStatus.IDLE
        )
        logger.info(f"Agent {agent.config.name} registered with Mission Control")
    
    async def route_task(self, task: Dict[str, Any]) -> Any:
        """Route a task to the appropriate agent"""
        task_type = task.get("task_type")
        priority = task.get("priority", 5)
        payload = task.get("payload", {})
        
        # Map task types to agents
        task_router = {
            # Finance tasks
            "create_invoice": "finance_controller",
            "generate_subscription": "finance_controller",
            "webhook_handler": "finance_controller",
            "calculate_metrics": "finance_controller",
            "billing_check": "finance_controller",
            
            # Market research tasks
            "scrape_trends": "market_scout",
            "analyze_competitor": "market_scout",
            "search_companies": "market_scout",
            "generate_market_report": "market_scout",
            "check_pricing": "market_scout",
            
            # Product tasks
            "answer_query": "product_builder",
            "generate_report": "product_builder",
            "extract_insight": "product_builder",
            "summarize_data": "product_builder",
            
            # Customer success tasks
            "create_ticket": "customer_success",
            "categorize_ticket": "customer_success",
            "generate_response": "customer_success",
            "detect_churn_risk": "customer_success",
            "proactive_outreach": "customer_success",
            "resolve_ticket": "customer_success",
            
            # Marketing tasks
            "create_content": "marketing_engine",
            "generate_lead": "marketing_engine",
            "segment_audience": "marketing_engine",
            "run_campaign": "marketing_engine",
            "analyze_performance": "marketing_engine",
            
            # Sales tasks
            "qualify_lead": "sales_closer",
            "handle_objection": "sales_closer",
            "schedule_demo": "sales_closer",
            "create_proposal": "sales_closer",
            "follow_up": "sales_closer",
            "analyze_pipeline": "sales_closer"
        }
        
        target_agent_name = task_router.get(task_type)
        if not target_agent_name:
            raise ValueError(f"Unknown task type: {task_type}")
        
        agent = self.agents.get(target_agent_name)
        if not agent:
            raise ValueError(f"Agent {target_agent_name} not registered")
        
        # Create and queue task
        agent_task = AgentTask(
            task_id=f"task_{datetime.utcnow().timestamp()}_{priority}",
            priority=priority,
            task_type=task_type,
            payload=payload
        )
        
        return await agent.execute_task(agent_task)
    
    def calculate_health_score(self) -> float:
        """Calculate overall health score based on all metrics"""
        metrics_weights = {
            "mrr": 0.2,
            "churn_rate": 0.15,
            "cac": 0.1,
            "ltv_cac_ratio": 0.15,
            "cash_runway": 0.15,
            "conversion_rate": 0.15,
            "billing_errors": 0.1
        }
        
        scores = {}
        
        # MRR Score
        scores["mrr"] = min(100, (self.metrics.mrr / 5000) * 100)
        
        # Churn Score
        scores["churn_rate"] = max(0, 100 - (self.metrics.churn_rate / 10) * 200)
        
        # CAC Score (inverse - lower is better)
        scores["cac"] = max(0, 100 - (self.metrics.cac / 150) * 100)
        
        # LTV:CAC Score
        scores["ltv_cac_ratio"] = min(100, (self.metrics.ltv_cac_ratio / 3) * 100)
        
        # Cash Runway Score
        scores["cash_runway"] = min(100, (self.metrics.cash_runway_days / 90) * 100)
        
        # Conversion Rate Score
        scores["conversion_rate"] = min(100, (self.metrics.conversion_rate / 3) * 100)
        
        # Billing Errors Score (inverse)
        scores["billing_errors"] = max(0, 100 - (self.metrics.billing_errors / 10))
        
        # Weighted average
        health_score = sum(
            scores[metric] * weight 
            for metric, weight in metrics_weights.items()
        )
        
        return round(health_score, 2)
    
    def get_health_status(self) -> HealthStatus:
        """Get current health status"""
        score = self.calculate_health_score()
        
        if score >= self.health_threshold_optimal:
            return HealthStatus.OPTIMAL
        elif score >= self.health_threshold_yellow:
            return HealthStatus.YELLOW
        elif score >= self.health_threshold_red:
            return HealthStatus.RED
        else:
            return HealthStatus.CRITICAL
    
    def check_failure_conditions(self) -> List[Dict]:
        """Check if any failure conditions are triggered"""
        triggered = []
        
        # MRR Collapse
        if self.metrics.mrr < self.failure_conditions["mrr_crash"]["threshold"]:
            self.failure_conditions["mrr_crash"]["active"] = True
            triggered.append({
                "condition": "mrr_crash",
                "value": self.metrics.mrr,
                "threshold": self.failure_conditions["mrr_crash"]["threshold"],
                "severity": "critical"
            })
        
        # Cash Runway Critical
        if self.metrics.cash_runway_days < self.failure_conditions["cash_runway_critical"]["threshold"]:
            self.failure_conditions["cash_runway_critical"]["active"] = True
            triggered.append({
                "condition": "cash_runway_critical",
                "value": self.metrics.cash_runway_days,
                "threshold": self.failure_conditions["cash_runway_critical"]["threshold"],
                "severity": "critical"
            })
        
        # Health Score Crash
        if self.calculate_health_score() < self.health_threshold_red:
            self.failure_conditions["health_score_crash"]["active"] = True
            triggered.append({
                "condition": "health_score_crash",
                "value": self.calculate_health_score(),
                "threshold": self.health_threshold_red,
                "severity": "critical"
            })
        
        # Churn Spike
        if self.metrics.churn_rate > self.failure_conditions["churn_spike"]["threshold"]:
            self.failure_conditions["churn_spike"]["active"] = True
            triggered.append({
                "condition": "churn_spike",
                "value": self.metrics.churn_rate,
                "threshold": self.failure_conditions["churn_spike"]["threshold"],
                "severity": "critical"
            })
        
        return triggered
    
    def update_metrics(self, new_metrics: Dict[str, Any]):
        """Update business metrics"""
        for key, value in new_metrics.items():
            if hasattr(self.metrics, key):
                setattr(self.metrics, key, value)
    
    async def update_agent_health(self, agent_name: str, health_data: Dict[str, Any]):
        """Update health status for a specific agent"""
        if agent_name in self.agent_health:
            self.agent_health[agent_name].status = AgentStatus(health_data.get("status", "idle"))
            self.agent_health[agent_name].completed_tasks = health_data.get("completed_tasks", 0)
            self.agent_health[agent_name].failed_tasks = health_data.get("failed_tasks", 0)
            self.agent_health[agent_name].queue_size = health_data.get("queue_size", 0)
            self.agent_health[agent_name].last_heartbeat = datetime.utcnow()
    
    def get_system_dashboard(self) -> Dict[str, Any]:
        """Generate dashboard data for Mission Control UI"""
        return {
            "health_score": self.calculate_health_score(),
            "health_status": self.get_health_status().value,
            "metrics": {
                "mrr": self.metrics.mrr,
                "arr": self.metrics.arr,
                "total_revenue": self.metrics.total_revenue,
                "churn_rate": self.metrics.churn_rate,
                "cac": self.metrics.cac,
                "ltv_cac_ratio": self.metrics.ltv_cac_ratio,
                "cash_balance": self.metrics.cash_balance,
                "cash_runway_days": self.metrics.cash_runway_days
            },
            "agents": {
                name: {
                    "status": health.status.value,
                    "completed_tasks": health.completed_tasks,
                    "failed_tasks": health.failed_tasks,
                    "queue_size": health.queue_size,
                    "uptime": (datetime.utcnow() - health.last_heartbeat).total_seconds() if health.last_heartbeat else 0
                }
                for name, health in self.agent_health.items()
            },
            "failure_conditions": {
                name: data for name, data in self.failure_conditions.items() if data.get("active", False)
            },
            "review_points": {
                name: date.isoformat() for name, date in self.review_points.items()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_reviews(self) -> Dict[str, str]:
        """Get current review point status"""
        now = datetime.utcnow()
        reviews = {}
        
        for name, review_date in self.review_points.items():
            if now >= review_date:
                reviews[name] = "due"
            else:
                reviews[name] = "pending"
        
        return reviews
    
    def should_terminate(self) -> tuple:
        """Check if business should terminate (return True and reason)"""
        failures = self.check_failure_conditions()
        
        if failures:
            reasons = [f["condition"] for f in failures]
            return True, f"Failure conditions triggered: {', '.join(reasons)}"
        
        # Check if we've passed the 90-day review point and didn't meet targets
        if datetime.utcnow() >= self.review_points["month_3"]:
            if self.metrics.mrr < 5000 or self.calculate_health_score() < 50:
                return True, "Post-review point: Did not meet minimum targets ($5K MRR or Health < 50)"
        
        return False, ""
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                # Update agent health
                for name, agent in self.agents.items():
                    health_data = await agent.report_health()
                    await self.update_agent_health(name, health_data)
                
                # Check for failures
                failures = self.check_failure_conditions()
                if failures:
                    logger.critical(f"Failure conditions detected: {failures}")
                    # Would trigger alert/notification in production
                
                # Check review points
                reviews = self.get_reviews()
                if "month_3" in reviews and reviews["month_3"] == "due":
                    should_stop, reason = self.should_terminate()
                    if should_stop:
                        logger.critical(f"Kill switch triggered: {reason}")
                        # Would trigger actual termination in production
                        break
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def start(self):
        """Start mission control"""
        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Mission Control started")
    
    async def stop(self):
        """Stop mission control"""
        self._running = False
        for agent in self.agents.values():
            await agent.close()
        if self._monitoring_task:
            await self._monitoring_task
        logger.info("Mission Control stopped")


# Global mission control instance
mission_control = MissionControl()


# FastAPI endpoints for mission control
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Mission Control API", version="1.0.0")


@app.get("/dashboard")
async def get_dashboard():
    """Get full dashboard data"""
    return mission_control.get_system_dashboard()


@app.post("/agents/health")
async def agent_health(health_data: Dict[str, Any]):
    """Receive health update from agent"""
    await mission_control.update_agent_health(
        health_data.get("agent_name"),
        health_data
    )
    return {"status": "updated"}


@app.post("/tasks")
async def route_task(task: Dict[str, Any]):
    """Route a task to appropriate agent"""
    try:
        result = await mission_control.route_task(task)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/health-score")
async def get_health_score():
    """Get current health score"""
    return {
        "health_score": mission_control.calculate_health_score(),
        "health_status": mission_control.get_health_status().value,
        "should_terminate": mission_control.should_terminate()
    }


@app.post("/metrics")
async def update_metrics(metrics: Dict[str, Any]):
    """Update business metrics"""
    mission_control.update_metrics(metrics)
    return {"status": "updated"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)