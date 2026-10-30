"""
Customer Success Agent
Handles support tickets, retention, and feature requests
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from ..base_agent import BaseAgent, AgentTask, AgentConfig

logger = logging.getLogger(__name__)


class TicketPriority(Enum):
    P0 = "p0"  # Revenue threat
    P1 = "p1"  # Bug/workflow issue
    P2 = "p2"  # Question/enhancement
    P3 = "p3"  # General inquiry


class TicketStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    AWAITING_USER = "awaiting_user"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass
class SupportTicket:
    ticket_id: str
    user_id: str
    email: str
    priority: TicketPriority
    status: TicketStatus
    subject: str
    message: str
    created_at: datetime
    last_updated: datetime
    resolved_at: Optional[datetime] = None
    sentiment_score: float = 0.5  # -1 to 1, negative = frustrated
    category: str = "general"


@dataclass
class ChurnRisk:
    user_id: str
    risk_score: float  # 0-1
    risk_factors: List[str]
    predicted_churn_date: Optional[datetime]
    intervention_suggested: str


class CustomerSuccessAgent(BaseAgent):
    """Agent for customer support and retention"""
    
    def __init__(self, config: AgentConfig, mission_control_url: str = "http://localhost:8000"):
        super().__init__(config, mission_control_url)
        
        # Ticket categories
        self.categories = [
            "billing", "technical", "account", "feature_request",
            "pricing", "onboarding", "api", "general"
        ]
        
        # Response templates
        self.templates = {
            "billing_inquiry": """
Thank you for reaching out about billing questions.

**Common Billing Queries**:
1. Invoice requests: Available in your billing dashboard
2. Payment issues: Check your card payment method
3. Cancellation: Can be done anytime, no refunds after trial

**Helpful Resources**:
- [Billing Documentation](https://docs.marketminder.ai/billing)
- [FAQ](https://marketminder.ai/faq)

If your issue isn't resolved, please reply with your customer ID: {customer_id}
            """,
            
            "technical_issue": """
Thank you for reporting this technical issue.

**Immediate Steps**:
1. Try refreshing your browser
2. Clear browser cache and cookies
3. Try a different browser

**Common Fixes**:
- Ensure you're using latest browser version
- Disable ad-blockers for our platform
- Check your internet connection

If the issue persists, our engineering team will investigate. Reference: {issue_id}
            """,
            
            "feature_request": """
We appreciate your feature request!

**Request Submitted**: {feature_name}

**Our Response Process**:
1. Feature requests are reviewed quarterly
2. You'll receive an update within 2 weeks
3. Votes from other users help prioritize requests

**Quick Workaround**: [describe alternative approaches]

Track your request here: https://feedback.marketminder.ai/requests/{request_id}
            """,
            
            "onboarding": """
Welcome to MarketMinder AI! Let's get you started.

**Quick Start Guide**:
1. Complete your profile setup
2. Connect your first data source
3. Run your first analysis

**First Tips**:
- Start with a simple competitor analysis
- Set up email alerts for trending topics
- Explore our template library

Need help? Reply to this email or join our community chat.
            """,
            
            "proactive_retention": """
We've noticed your recent activity has decreased. We miss you!

**What's New**:
- {new_feature}
- {new_feature_2}

**Questions**:
- Is there something blocking you?
- How can we make your experience better?

Reply directly to schedule a quick 10-min call with our team.
            """,
            
            "churn_prevention": """
We noticed your subscription is expiring soon. Before you go...

**Your Account Status**: {days_left} days left

**What You'll Miss**:
- Unlimited competitive analyses
- Custom market reports
- Priority support
- {usage_stats}

**Special Offer**: Reply "STAY" for 20% off your next month.

We'd love to hear how we can do better.
            """
        }
        
        # In-memory ticket storage (would use DB in production)
        self.tickets: Dict[str, SupportTicket] = {}
        self.churn_risks: Dict[str, ChurnRisk] = {}
        self.user_profiles: Dict[str, Dict] = {}
    
    async def process_task(self, task: AgentTask) -> Any:
        """Process customer success tasks"""
        task_type = task.payload.get("task_type")
        
        if task_type == "create_ticket":
            return await self._create_ticket(task)
        elif task_type == "categorize_ticket":
            return await self._categorize_ticket(task)
        elif task_type == "generate_response":
            return await self._generate_response(task)
        elif task_type == "detect_churn_risk":
            return await self._detect_churn_risk(task)
        elif task_type == "proactive_outreach":
            return await self._proactive_outreach(task)
        elif task_type == "resolve_ticket":
            return await self._resolve_ticket(task)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    async def _create_ticket(self, task: AgentTask) -> SupportTicket:
        """Create a new support ticket"""
        payload = task.payload
        
        ticket_id = f"TCKT{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{hash(payload.get('email', '')) % 10000:04d}"
        
        ticket = SupportTicket(
            ticket_id=ticket_id,
            user_id=payload.get("user_id", "unknown"),
            email=payload.get("email"),
            priority=TicketPriority.P3,  # Default, will be categorized
            status=TicketStatus.OPEN,
            subject=payload.get("subject", "Support Request"),
            message=payload.get("message", ""),
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow()
        )
        
        self.tickets[ticket_id] = ticket
        
        # Categorize the ticket
        category = await self._categorize_ticket(AgentTask(
            task_id="categorize",
            priority=1,
            task_type="categorize_ticket",
            payload={"ticket_id": ticket_id}
        ))
        ticket.category = category
        
        # Generate initial response
        response = await self._generate_response(AgentTask(
            task_id="response",
            priority=1,
            task_type="generate_response",
            payload={"ticket_id": ticket_id}
        ))
        
        return ticket.__dict__
    
    async def _categorize_ticket(self, task: AgentTask) -> str:
        """Categorize ticket based on content"""
        ticket_id = task.payload.get("ticket_id")
        ticket = self.tickets.get(ticket_id)
        
        if not ticket:
            return "general"
        
        content = (ticket.subject + " " + ticket.message).lower()
        
        # Keyword-based categorization
        category_keywords = {
            "billing": ["bill", "invoice", "charge", "payment", "refund", "cancel"],
            "technical": ["bug", "error", "crash", "broken", "not working", "fail"],
            "account": ["login", "password", "account", "profile", "settings"],
            "feature_request": ["feature", "request", "suggestion", "wish", "add"],
            "pricing": ["price", "cost", "tier", "plan", "cheap", "expensive"],
            "onboarding": ["help", "start", "begin", "setup", "tutorial"],
            "api": ["api", "endpoint", "integration", "webhook"],
        }
        
        for category, keywords in category_keywords.items():
            if any(kw in content for kw in keywords):
                # Determine priority based on category
                if category == "billing":
                    ticket.priority = TicketPriority.P1
                elif category == "technical":
                    ticket.priority = TicketPriority.P1
                elif category == "feature_request":
                    ticket.priority = TicketPriority.P2
                return category
        
        return "general"
    
    async def _generate_response(self, task: AgentTask) -> str:
        """Generate appropriate response for ticket"""
        ticket_id = task.payload.get("ticket_id")
        ticket = self.tickets.get(ticket_id)
        
        if not ticket:
            return "Ticket not found"
        
        # Get user usage data
        usage = self.user_profiles.get(ticket.user_id, {})
        
        # Generate template-based response
        template_key = ticket.category
        if template_key not in self.templates:
            template_key = "general"
        
        template = self.templates[template_key]
        
        # Fill in placeholders
        response = template.format(
            customer_id=ticket.user_id,
            issue_id=ticket.ticket_id,
            feature_name=ticket.subject,
            request_id=ticket.ticket_id,
            new_feature="AI-powered competitor analysis",
            new_feature_2="Enhanced trend alerts",
            days_left="30",
            usage_stats="You've analyzed 42 competitors this month"
        )
        
        # Update ticket
        ticket.last_updated = datetime.utcnow()
        if template_key in ["billing", "technical", "account"]:
            ticket.status = TicketStatus.RESOLVED
        
        return response
    
    async def _detect_churn_risk(self, task: AgentTask) -> ChurnRisk:
        """Detect users at risk of churning"""
        user_id = task.payload.get("user_id")
        profile = self.user_profiles.get(user_id, {})
        
        risk_factors = []
        risk_score = 0.5  # Default
        
        # Check activity patterns
        last_login = profile.get("last_login")
        if last_login:
            days_since = (datetime.utcnow() - last_login).days
            if days_since > 30:
                risk_factors.append("inactive_30_days")
                risk_score += 0.3
            elif days_since > 14:
                risk_factors.append("inactive_14_days")
                risk_score += 0.1
        
        # Check support ticket sentiment
        user_tickets = [t for t in self.tickets.values() if t.user_id == user_id]
        negative_tickets = [t for t in user_tickets if t.sentiment_score < -0.3]
        if negative_tickets:
            risk_factors.append("negative_support_sentiment")
            risk_score += 0.2
        
        # Check usage decline
        usage_history = profile.get("usage_history", [])
        if usage_history:
            recent_avg = sum(usage_history[-7:]) / 7 if len(usage_history) >= 7 else usage_history[-1]
            older_avg = sum(usage_history[:7]) / 7 if len(usage_history) >= 7 else recent_avg
            if recent_avg < older_avg * 0.5:
                risk_factors.append("usage_decline")
                risk_score += 0.25
        
        # Predicted churn date
        predicted_churn = None
        if risk_score > 0.5:
            days_until_churn = int(60 * (1 - risk_score))
            predicted_churn = datetime.utcnow() + timedelta(days=days_until_churn)
        
        intervention = self._suggest_intervention(risk_score, risk_factors)
        
        return ChurnRisk(
            user_id=user_id,
            risk_score=min(1.0, risk_score),
            risk_factors=risk_factors,
            predicted_churn_date=predicted_churn,
            intervention_suggested=intervention
        )
    
    def _suggest_intervention(self, risk_score: float, factors: List[str]) -> str:
        """Suggest appropriate intervention based on risk factors"""
        if "negative_support_sentiment" in factors:
            return "apology_and_discount_offer"
        elif "inactive_30_days" in factors:
            return "personal_outreach_email"
        elif "usage_decline" in factors:
            return "feature_demonstration"
        else:
            return "general_re_engagement"
    
    async def _proactive_outreach(self, task: AgentTask) -> List[Dict]:
        """Identify users for proactive outreach"""
        outreach_list = []
        
        for user_id, profile in self.user_profiles.items():
            risk = await self._detect_churn_risk(AgentTask(
                task_id="risk_detect",
                priority=3,
                task_type="detect_churn_risk",
                payload={"user_id": user_id}
            ))
            
            if risk.risk_score > 0.3:
                user_ticket = next((t for t in self.tickets.values() if t.user_id == user_id and t.status == TicketStatus.OPEN), None)
                
                outreach_list.append({
                    "user_id": user_id,
                    "email": profile.get("email"),
                    "risk_score": risk.risk_score,
                    "intervention": risk.intervention_suggested,
                    "existing_tickets": len([t for t in self.tickets.values() if t.user_id == user_id])
                })
        
        return outreach_list
    
    async def _resolve_ticket(self, task: AgentTask) -> bool:
        """Mark ticket as resolved"""
        ticket_id = task.payload.get("ticket_id")
        resolution = task.payload.get("resolution", "User confirmed issue resolved")
        
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            return False
        
        ticket.status = TicketStatus.RESOLVED
        ticket.resolved_at = datetime.utcnow()
        
        logger.info(f"Ticket {ticket_id} resolved: {resolution}")
        return True
    
    async def update_user_profile(self, user_id: str, updates: Dict[str, Any]):
        """Update user profile with activity data"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                "email": "",
                "last_login": datetime.utcnow(),
                "usage_history": [],
                "total_queries": 0,
                "plan": "starter"
            }
        
        profile = self.user_profiles[user_id]
        profile.update(updates)
    
    async def get_support_metrics(self) -> Dict[str, Any]:
        """Get support metrics for health dashboard"""
        total_tickets = len(self.tickets)
        open_tickets = len([t for t in self.tickets.values() if t.status == TicketStatus.OPEN])
        avg_resolution_time = 0
        
        resolved = [t for t in self.tickets.values() if t.status == TicketStatus.RESOLVED]
        if resolved:
            times = [(t.resolved_at - t.created_at).total_seconds() for t in resolved if t.resolved_at]
            avg_resolution_time = sum(times) / len(times) if times else 0
        
        urgency_distribution = {p.value: 0 for p in TicketPriority}
        for ticket in self.tickets.values():
            urgency_distribution[ticket.priority.value] += 1
        
        return {
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "avg_resolution_time_seconds": avg_resolution_time,
            "urgency_distribution": urgency_distribution,
            "tickets_by_category": {c: len([t for t in self.tickets.values() if t.category == c]) for c in self.categories}
        }
    
    async def monitor_churn_risks(self):
        """Periodically check for churn risks"""
        while self._running:
            try:
                # Check for new churn risks
                active_users = list(self.user_profiles.keys())
                
                for user_id in active_users[:10]:  # Sample for demo
                    risk = await self._detect_churn_risk(AgentTask(
                        task_id="risk_check",
                        priority=3,
                        task_type="detect_churn_risk",
                        payload={"user_id": user_id}
                    ))
                    
                    if risk.risk_score > 0.4:
                        self.churn_risks[user_id] = risk
                
                # Proactive outreach
                outreach = await self._proactive_outreach({"payload": {}})
                
                if outreach:
                    logger.info(f"Identified {len(outreach)} users for proactive outreach")
                
                await asyncio.sleep(3600)  # Check hourly
                
            except Exception as e:
                logger.error(f"Churn monitoring error: {e}")
                await asyncio.sleep(60)