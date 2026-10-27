"""
MarketMinder AI - Main Application
FastAPI application with all endpoints
"""

import asyncio
import logging
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json

# Import agents
from agents.base_agent import BaseAgent, AgentTask, AgentConfig
from agents.finance.controller import FinanceControllerAgent
from agents.market.scout import MarketScoutAgent
from agents.product.builder import ProductBuilderAgent
from agents.customer.success import CustomerSuccessAgent
from agents.marketing.engine import MarketingEngineAgent
from agents.sales.closer import SalesCloserAgent
from core.mission_control import MissionControl, mission_control, app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create main application
main_app = FastAPI(
    title="MarketMinder AI",
    description="AI-Powered Competitive Intelligence Platform",
    version="1.0.0"
)

# Add CORS middleware
main_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for demo data
demo_data = {
    "queries": [],
    "users": {},
    "reports": []
}


# Request/Response Models
class QueryRequest(BaseModel):
    question: str
    sector: Optional[str] = None
    timeframe: str = "last_quarter"


class TicketRequest(BaseModel):
    email: str
    subject: str
    message: str
    user_id: Optional[str] = None


class LeadRequest(BaseModel):
    email: str
    name: str
    company: str
    title: Optional[str] = None
    pain_point_importance: float = 0.7
    budget: float = 5000


class TaskRequest(BaseModel):
    task_type: str
    priority: int = 5
    payload: Dict[str, Any]


# Health check endpoint
@main_app.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# API Routes - Query Endpoint
@main_app.post("/analyze")
async def analyze_market(request: QueryRequest):
    """Main endpoint for market analysis queries"""
    task = AgentTask(
        task_id=f"query_{datetime.utcnow().timestamp()}",
        priority=5,
        task_type="answer_query",
        payload={
            "question": request.question,
            "sector": request.sector or "technology",
            "timeframe": request.timeframe
        }
    )
    
    # Route to Product Builder
    result = await mission_control.route_task({
        "task_type": "answer_query",
        "priority": 5,
        "payload": {
            "question": request.question,
            "sector": request.sector or "technology",
            "timeframe": request.timeframe
        }
    })
    
    # Store for demo
    demo_data["queries"].append({
        "id": str(datetime.utcnow().timestamp()),
        "question": request.question,
        "sector": request.sector,
        "response": result,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {
        "query": request.question,
        "response": result,
        "sources": ["MarketMinder AI Knowledge Base"],
        "timestamp": datetime.utcnow().isoformat()
    }


# API Routes - Report Generation
@main_app.post("/report")
async def generate_report(request: QueryRequest):
    """Generate a market report"""
    report_type = "trend_report" if "trend" in request.question.lower() else "competitive_analysis"
    
    report = await mission_control.route_task({
        "task_type": "generate_report",
        "priority": 4,
        "payload": {
            "request": {
                "question": request.question,
                "sector": request.sector or "technology",
                "timeframe": request.timeframe,
                "report_type": report_type
            }
        }
    })
    
    demo_data["reports"].append({
        "id": str(datetime.utcnow().timestamp()),
        "type": report_type,
        "sector": request.sector,
        "content": report,
        "created_at": datetime.utcnow().isoformat()
    })
    
    return {
        "report_type": report_type,
        "title": report.get("title", ""),
        "executive_summary": report.get("executive_summary", ""),
        "key_findings": report.get("key_findings", [])[:5],
        "recommendations": report.get("recommendations", [])[:3],
        "data_sources": report.get("data_sources", [])
    }


# API Routes - Support
@main_app.post("/support/ticket")
async def create_ticket(request: TicketRequest):
    """Create a support ticket"""
    ticket = await mission_control.route_task({
        "task_type": "create_ticket",
        "priority": 3,
        "payload": {
            "email": request.email,
            "subject": request.subject,
            "message": request.message,
            "user_id": request.user_id
        }
    })
    
    return {
        "ticket_id": ticket["ticket_id"],
        "status": "created",
        "estimated_response_time": "24 hours",
        "ticket": ticket
    }


# API Routes - Lead Generation
@main_app.post("/lead")
async def generate_lead(request: LeadRequest):
    """Generate and qualify a lead"""
    lead = await mission_control.route_task({
        "task_type": "generate_lead",
        "priority": 4,
        "payload": {
            "data": {
                "email": request.email,
                "name": request.name,
                "company": request.company,
                "title": request.title,
                "pain_point_importance": request.pain_point_importance,
                "budget": request.budget
            }
        }
    })
    
    # Qualify the lead
    opportunity = await mission_control.route_task({
        "task_type": "qualify_lead",
        "priority": 3,
        "payload": {
            "data": {
                "lead_id": lead.lead_id,
                "company": request.company,
                "decision_maker": request.name,
                "value_proposition": "AI-powered competitive intelligence",
                "budget": request.budget,
                "pain_point_importance": request.pain_point_importance
            }
        }
    })
    
    return {
        "lead_id": lead.lead_id,
        "score": lead.score,
        "status": lead.status,
        "opportunity_id": opportunity.opportunity_id,
        "next_steps": opportunity.next_activity
    }


# API Routes - Dashboard
@main_app.get("/dashboard")
async def get_dashboard():
    """Get dashboard data"""
    return mission_control.get_system_dashboard()


@main_app.get("/metrics")
async def get_metrics():
    """Get current business metrics"""
    dashboard = mission_control.get_system_dashboard()
    return {
        "mrr": dashboard["metrics"]["mrr"],
        "arr": dashboard["metrics"]["arr"],
        "churn_rate": dashboard["metrics"]["churn_rate"],
        "cac": dashboard["metrics"]["cac"],
        "ltv_cac_ratio": dashboard["metrics"]["ltv_cac_ratio"],
        "cash_balance": dashboard["metrics"]["cash_balance"],
        "cash_runway_days": dashboard["metrics"]["cash_runway_days"],
        "health_score": dashboard["health_score"]
    }


@main_app.get("/health-score")
async def get_health():
    """Get health score and status"""
    score, status = mission_control.calculate_health_score(), mission_control.get_health_status().value
    should_stop, reason = mission_control.should_terminate()
    
    return {
        "health_score": score,
        "status": status,
        "should_terminate": should_stop,
        "termination_reason": reason if should_stop else None
    }


# Agent Management Endpoints
@main_app.get("/agents")
async def list_agents():
    """List all registered agents"""
    return {
        "agents": list(mission_control.agents.keys()),
        "statuses": {
            name: health.status.value 
            for name, health in mission_control.agent_health.items()
        }
    }


@main_app.post("/agents")
async def trigger_task(task: TaskRequest):
    """Trigger a specific task on an agent"""
    try:
        result = await mission_control.route_task({
            "task_type": task.task_type,
            "priority": task.priority,
            "payload": task.payload
        })
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Landing Page
@main_app.get("/", response_class=HTMLResponse)
async def landing_page():
    """Simple landing page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MarketMinder AI</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                   max-width: 800px; margin: 0 auto; padding: 40px; background: #f5f5f5; }
            .container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; margin-top: 0; }
            .feature { padding: 20px; border-left: 4px solid #007bff; margin: 20px 0; background: #f8f9fa; }
            .cta { background: #007bff; color: white; padding: 15px 30px; text-decoration: none; 
                   border-radius: 5px; display: inline-block; margin-top: 20px; }
            .demo { margin-top: 30px; padding: 20px; background: #e9ecef; border-radius: 5px; }
            input, button { padding: 10px; margin: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏢 MarketMinder AI</h1>
            <p>Automated competitive intelligence & market research platform</p>
            
            <div class="feature">
                <h3>🔍 Intelligent Market Analysis</h3>
                <p>Ask questions about markets, competitors, or trends. Get AI-powered insights in seconds.</p>
            </div>
            
            <div class="feature">
                <h3>💰 Fully Automated Operations</h3>
                <p>Run by AI agents that handle everything from billing to support - zero human intervention required.</p>
            </div>
            
            <div class="feature">
                <h3>🎯 Real Business Results</h3>
                <p>Track MRR, churn, CAC, and more with our automated health monitoring.</p>
            </div>
            
            <div class="demo">
                <h3>Try it live</h3>
                <form action="/analyze" method="post">
                    <input type="text" name="question" placeholder="What's happening in AI startups?" 
                           style="width: 300px; padding: 10px;" required>
                    <button type="submit" class="cta">Analyze</button>
                </form>
            </div>
            
            <p><small>Powered by autonomous AI agents via Mission Control orchestrator</small></p>
        </div>
    </body>
    </html>
    """


# Startup event
@main_app.on_event("startup")
async def startup_event():
    """Initialize all agents on startup"""
    logger.info("Initializing MarketMinder AI agents...")
    
    # Configure agents
    finance_config = AgentConfig(
        name="finance_controller",
        description="Handles billing, subscriptions, and financial operations"
    )
    
    market_config = AgentConfig(
        name="market_scout", 
        description="Monitors markets and analyzes competitors"
    )
    
    product_config = AgentConfig(
        name="product_builder",
        description="Generates insights and handles queries"
    )
    
    customer_config = AgentConfig(
        name="customer_success",
        description="Handles support and retention"
    )
    
    marketing_config = AgentConfig(
        name="marketing_engine",
        description="Content creation and lead generation"
    )
    
    sales_config = AgentConfig(
        name="sales_closer",
        description="Lead qualification and conversion"
    )
    
    # Create agents
    finance_agent = FinanceControllerAgent(
        finance_config,
        db_url="sqlite:///./finance.db",  # SQLite for demo
        stripe_secret_key=os.getenv("STRIPE_SECRET_KEY", "sk_test_dummy"),
        mission_control_url="http://localhost:8000"
    )
    
    market_agent = MarketScoutAgent(market_config)
    product_agent = ProductBuilderAgent(product_config)
    customer_agent = CustomerSuccessAgent(customer_config)
    marketing_agent = MarketingEngineAgent(marketing_config)
    sales_agent = SalesCloserAgent(sales_config)
    
    # Register all agents
    mission_control.register_agent(finance_agent)
    mission_control.register_agent(market_agent)
    mission_control.register_agent(product_agent)
    mission_control.register_agent(customer_agent)
    mission_control.register_agent(marketing_agent)
    mission_control.register_agent(sales_agent)
    
    logger.info("All agents initialized and registered!")
    
    # Start mission control
    await mission_control.start()
    
    # Generate initial content
    logger.info("Generating initial market content...")
    try:
        content = await marketing_agent._create_content(AgentTask(
            task_id="init_content",
            priority=1,
            task_type="create_content",
            payload={"topic": "market trends", "audience": "tech founders"}
        ))
        logger.info(f"Created initial content: {content.title}")
    except Exception as e:
        logger.warning(f"Content generation issue (non-critical): {e}")


# Run the application
if __name__ == "__main__":
    import uvicorn
    
    # Run with uvicorn
    uvicorn.run(
        main_app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )