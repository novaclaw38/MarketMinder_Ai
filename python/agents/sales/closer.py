"""
Sales Closer Agent
Handles lead qualification, demo scheduling, and objection handling
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from ..base_agent import BaseAgent, AgentTask, AgentConfig

logger = logging.getLogger(__name__)


class LeadStatus(Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    DEMO_SCHEDULED = "demo_scheduled"
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATING = "negotiating"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


@dataclass
class SalesOpportunity:
    opportunity_id: str
    lead_id: str
    company: str
    decision_maker: str
    value_proposition: str
    objection: Optional[str]
    stage: LeadStatus
    probability: float  # 0-100
    expected_value: float
    last_contact: datetime
    next_activity: str
    timeline: str  # days


class SalesCloserAgent(BaseAgent):
    """Agent for sales automation and lead conversion"""
    
    def __init__(self, config: AgentConfig, mission_control_url: str = "http://localhost:8000"):
        super().__init__(config, mission_control_url)
        
        # Objection handling database
        self.objection_responses = {
            "too_expensive": {
                "acknowledge": "I understand budget considerations are important",
                "redirect": "Let me show you the ROI you can expect",
                "offer": "We have financing options and volume discounts"
            },
            "need_more_time": {
                "acknowledge": "Taking time to evaluate is smart",
                "redirect": "What specific questions do you need answered?",
                "offer": "I can provide a detailed whitepaper or case studies"
            },
            "competitor_love": {
                "acknowledge": "Their solution might look good on paper",
                "redirect": "What specific outcomes are you missing?",
                "offer": "Let me show you what sets us apart in a side-by-side"
            },
            "not_a_priority": {
                "acknowledge": "I hear this isn't top priority right now",
                "redirect": "When would be a better time to revisit this?",
                "offer": "I can check back in 3 months with new insights"
            },
            "data_privacy": {
                "acknowledge": "Data compliance is critical",
                "redirect": "Our GDPR and SOC2 compliance goes beyond requirements",
                "offer": "I can connect you with our compliance team"
            }
        }
        
        # Success stories database (would be in DB in production)
        self.case_studies = [
            {
                "company": "TechFlow Solutions",
                "challenge": "Manual competitor analysis took 20 hours/week",
                "solution": "Automated weekly reports with trend alerts",
                "results": "22 hours saved weekly, 3x more market insights",
                "roi": "$120,000 annual savings"
            },
            {
                "company": "Nexus Analytics",
                "challenge": "Scattered competitive intelligence across tools",
                "solution": "Centralized dashboard with real-time updates",
                "results": "Unified view, 40% faster decision-making",
                "roi": "$85,000 in efficiency gains"
            }
        ]
        
        # In-memory storage
        self.opportunities: Dict[str, SalesOpportunity] = {}
        self.demos_scheduled: Dict[str, datetime] = {}
    
    async def process_task(self, task: AgentTask) -> Any:
        """Process sales automation tasks"""
        task_type = task.payload.get("task_type")
        
        if task_type == "qualify_lead":
            return await self._qualify_lead(task)
        elif task_type == "handle_objection":
            return await self._handle_objection(task)
        elif task_type == "schedule_demo":
            return await self._schedule_demo(task)
        elif task_type == "create_proposal":
            return await self._create_proposal(task)
        elif task_type == "follow_up":
            return await self._follow_up(task)
        elif task_type == "analyze_pipeline":
            return await self._analyze_pipeline(task)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    async def _qualify_lead(self, task: AgentTask) -> SalesOpportunity:
        """Qualify a lead using BANT framework"""
        lead_data = task.payload.get("data", {})
        
        # BANT scoring (Budget, Authority, Need, Timeline)
        budget = lead_data.get("budget", 5000)  # Monthly budget
        authority = 0.7  # Self-reported, would be verified
        need = lead_data.get("pain_point_importance", 0.8)
        timeline = lead_data.get("decision_timeline", 30)
        
        # Calculate qualification score
        qualification_score = (budget / 10000 * 0.3 + authority * 0.2 + need * 0.3 + (1 - timeline/90) * 0.2) * 100
        
        # Determine qualification level
        if qualification_score >= 80:
            stage = LeadStatus.QUALIFIED
            probability = 75
        elif qualification_score >= 60:
            stage = LeadStatus.CONTACTED
            probability = 45
        else:
            stage = LeadStatus.NEW
            probability = 20
        
        opportunity = SalesOpportunity(
            opportunity_id=f"OPP{uuid.uuid4().hex[:12]}",
            lead_id=lead_data.get("lead_id", str(uuid.uuid4())),
            company=lead_data.get("company", "Unknown"),
            decision_maker=lead_data.get("decision_maker", "Unknown Person"),
            value_proposition=lead_data.get("value_proposition", "AI-powered competitive intelligence"),
            objection=lead_data.get("objection"),
            stage=stage,
            probability=probability,
            expected_value=max(0, budget * 12),  # Estimated annual value
            last_contact=datetime.utcnow(),
            next_activity=self._get_next_activity(stage),
            timeline=f"{max(0, 30 - timeline)} days to close" if stage != LeadStatus.NEW else "Nurture"
        )
        
        self.opportunities[opportunity.opportunity_id] = opportunity
        return opportunity
    
    def _get_next_activity(self, stage: LeadStatus) -> str:
        """Determine next sales activity based on stage"""
        activities = {
            LeadStatus.NEW: "Send welcome email with case studies",
            LeadStatus.CONTACTED: "Schedule discovery call",
            LeadStatus.QUALIFIED: "Send customized demo",
            LeadStatus.DEMO_SCHEDULED: "Follow up on demo attendance",
            LeadStatus.PROPOSAL_SENT: "Address questions, negotiate terms",
            LeadStatus.NEGOTIATING: "Finalize contract terms",
            LeadStatus.CLOSED_WON: "Onboard customer",
            LeadStatus.CLOSED_LOST: "Handle end-of-cycle outreach"
        }
        return activities.get(stage, "Review opportunity")
    
    async def _handle_objection(self, task: AgentTask) -> Dict[str, str]:
        """Handle sales objection with appropriate response"""
        opportunity_id = task.payload.get("opportunity_id")
        objection_type = task.payload.get("objection", "need_more_time")
        
        opportunity = self.opportunities.get(opportunity_id)
        if not opportunity:
            return {"error": "Opportunity not found"}
        
        objection_handler = self.objection_responses.get(objection_type, self.objection_responses["need_more_time"])
        
        # Generate response based on objection
        if objection_type == "too_expensive":
            response = f"""
I completely understand budget considerations. Rather than focusing on price, let me show you the specific value you'll receive:

**Expected ROI**: {opportunity.decision_maker} would see approximately ${opportunity.expected_value / 10:,.0f} in time savings from reduced manual research.

**Flexible Tiers**: We offer 3 pricing levels starting at $29/month, scaling with usage.

**Case Study**: At {self.case_studies[0]['company']}, they saved {self.case_studies[0]['results'].split(',')[0].strip()} after implementing our solution.

Would reviewing the specific features that justify this investment work for your timeline?
            """
        elif objection_type == "need_more_time":
            response = f"""
Absolutely, taking time to evaluate ensures the right decision. To help accelerate your process:

1. **Quick Wins**: Our free tier lets you test core functionality immediately
2. **Implementation**: Starts in under 15 minutes
3. **Support**: Dedicated onboarding specialist assigned

What specific questions do you need answered in the next 48 hours to move forward?
            """
        elif objection_type == "competitor_love":
            response = f"""
That's great you've done your research! The question I'd love to explore is:

**What outcomes are you still missing** from their solution?

I've found that many teams who thought they were "sticking with what they know" discovered critical gaps in our comparison:

{self._get_competitor_comparison()}

Would you be open to a 15-minute call to explore what you might be missing?
            """
        else:
            response = f"""
I appreciate you sharing that concern. Let me address it directly:

{objection_handler['acknowledge']}

{objection_handler['redirect']}

{objection_handler['offer']}

What specific aspect would you like me to elaborate on?
            """
        
        # Update opportunity
        if opportunity:
            opportunity.objection = objection_type
            opportunity.next_activity = "Address objection with personalized response"
        
        return {
            "response": response,
            "next_step": opportunity.next_activity if opportunity else "follow_up",
            "timestep_hours": 24
        }
    
    def _get_competitor_comparison(self) -> str:
        """Generate competitive feature comparison"""
        return """
| Feature | Our AI | Competitor A | Competitor B |
|---------|--------|--------------|--------------|
| Automated Insights | ✓ | Manual research | ✓ |
| Real-time Alerts | ✓ | Weekly |  Monthly |
| GDPR Compliant | ✓ | EU only | Global |
| Pricing Analysis | ✓ | ✓ | Limited |
| Social Listening | ✓ | Add-on | Not offered |

Our customers typically find 2-3 capabilities missing from their previous solutions.
        """
    
    async def _schedule_demo(self, task: AgentTask) -> Dict[str, Any]:
        """Schedule a demo meeting"""
        opportunity_id = task.payload.get("opportunity_id")
        proposed_time = task.payload.get("proposed_time")
        timezone = task.payload.get("timezone", "UTC")
        
        opportunity = self.opportunities.get(opportunity_id)
        if not opportunity:
            return {"error": "Opportunity not found"}
        
        demo_id = f"DEM{uuid.uuid4().hex[:8]}"
        scheduled_time = datetime.fromisoformat(proposed_time) if proposed_time else datetime.utcnow() + timedelta(days=2, hours=14)
        
        self.demos_scheduled[demo_id] = scheduled_time
        
        # Update opportunity
        opportunity.stage = LeadStatus.DEMO_SCHEDULED
        opportunity.next_activity = f"Send calendar invite and prep materials for {scheduled_time.strftime('%Y-%m-%d %H:%M %Z')}"
        
        calendar_invite = {
            "summary": f"MarketMinder AI Demo with {opportunity.decision_maker}",
            "description": f"30-minute personalized demo of MarketMinder AI's competitive intelligence platform.\n\nAgenda:\n1. Your current challenges with {opportunity.value_proposition}\n2. Live platform walkthrough\n3. Q&A and pricing discussion\n\nMeeting link: https://zoom.marketminder.ai/{demo_id}",
            "start": scheduled_time.isoformat(),
            "end": (scheduled_time + timedelta(minutes=30)).isoformat(),
            "timezone": timezone
        }
        
        return {
            "demo_id": demo_id,
            "scheduled_time": scheduled_time.isoformat(),
            "calendar_invite": calendar_invite,
            "join_link": f"https://zoom.marketminder.ai/{demo_id}",
            "reminder_minutes": [24, 60]  # Reminders 24h and 1h before
        }
    
    async def _create_proposal(self, task: AgentTask) -> Dict[str, Any]:
        """Generate a sales proposal"""
        opportunity_id = task.payload.get("opportunity_id")
        plan_tier = task.payload.get("plan_tier", "professional")
        
        opportunity = self.opportunities.get(opportunity_id)
        if not opportunity:
            return {"error": "Opportunity not found"}
        
        pricing = {
            "starter": {"price": 29, "features": ["3 analyses/day", "Basic reports", "Email support"]},
            "professional": {"price": 99, "features": ["Unlimited analyses", "Custom reports", "Priority support", "API access"]},
            "enterprise": {"price": 299, "features": ["All Professional features", "Custom integrations", "Dedicated CSM", "SLA guarantee"]}
        }
        
        plan = pricing.get(plan_tier, pricing["professional"])
        
        proposal = f"""
# Proposal for {opportunity.company}

## Executive Summary
MarketMinder AI will help {opportunity.company} gain a competitive edge through automated market intelligence and real-time competitive analysis.

## Solution
{plan_tier.title()} Plan at ${plan['price']}/month

### Key Features
{chr(10).join(f'• {f}' for f in plan['features'])}

### Implementation Timeline
• Week 1: Account setup and data configuration
• Week 2: Initial analysis and dashboard deployment
• Week 3: Team training and workflow optimization
• Ongoing: Continuous monitoring and optimization

## Investment
| Plan | Monthly | Annual Savings |
|------|---------|----------------|
| {plan_tier.title()} | ${plan['price']}/month | Value clearly exceeds cost |

*Special Offer: 20% discount for annual billing*

## Next Steps
1. Review and approve proposal
2. Sign agreement (digital)
3. Schedule onboarding session

**Limited-time offer valid until {datetime.utcnow() + timedelta(days=14):%Y-%m-%d}**

Questions? Reply to this email or call {opportunity.decision_maker} directly.
        """
        
        opportunity.stage = LeadStatus.PROPOSAL_SENT
        opportunity.next_activity = "Follow up on proposal status in 3 days"
        
        return {
            "proposal_id": f"PROP{uuid.uuid4().hex[:10]}",
            "opportunity_id": opportunity_id,
            "document": proposal,
            "expires_at": datetime.utcnow() + timedelta(days=14),
            "sent_at": datetime.utcnow().isoformat()
        }
    
    async def _follow_up(self, task: AgentTask) -> str:
        """Automated follow-up sequence"""
        lead_id = task.payload.get("lead_id")
        opportunity_id = task.payload.get("opportunity_id")
        
        opportunity = None
        if opportunity_id and opportunity_id in self.opportunities:
            opportunity = self.opportunities[opportunity_id]
        
        if not opportunity:
            return "No valid opportunity"
        
        # Follow-up based on stage
        if opportunity.stage == LeadStatus.CONTACTED:
            message = f"""
Hi {opportunity.decision_maker},

Following up on my email about {opportunity.value_proposition}. 

I'd love to hear if you have 15 minutes this week to discuss how we can help {opportunity.company} gain market advantages.

Best,
Sales AI @ MarketMinder
            """
            opportunity.next_activity = "Demo scheduling follow-up"
        
        elif opportunity.stage == LeadStatus.QUALIFIED:
            message = f"""
Great speaking with you, {opportunity.decision_maker}!

As discussed, I'm sending over the demo link for Tuesday at 2pm:

**MarketMinder AI Demo**
{opportunity.value_proposition}

Looking forward to showing you the platform!

- Sales AI @ MarketMinder
            """
            opportunity.next_activity = "Send calendar confirmation"
        
        elif opportunity.stage == LeadStatus.PROPOSAL_SENT:
            message = f"""
Hi {opportunity.decision_maker},

Checking in on the proposal I sent last week. The 20% discount expires soon ({datetime.utcnow() + timedelta(days=14):%Y-%m-%d}).

Would you like me to clarify any aspect of the proposal?

Best,
Sales AI
            """
            opportunity.next_activity = "Proposal follow-up call"
        
        else:
            message = "No automated follow-up template available for this stage"
        
        opportunity.last_contact = datetime.utcnow()
        return message
    
    async def _analyze_pipeline(self, task: AgentTask) -> Dict[str, Any]:
        """Analyze sales pipeline and forecast revenue"""
        opportunities = list(self.opportunities.values())
        
        stage_counts = {}
        stage_values = {}
        
        for opp in opportunities:
            stage_name = opp.stage.value
            if stage_name not in stage_counts:
                stage_counts[stage_name] = 0
                stage_values[stage_name] = 0
            stage_counts[stage_name] += 1
            stage_values[stage_name] += opp.expected_value * (opp.probability / 100)
        
        total_pipeline_value = sum(opp.expected_value * (opp.probability / 100) for opp in opportunities)
        weighted_close_rate = sum(opp.probability for opp in opportunities) / max(1, len(opportunities))
        
        return {
            "total_opportunities": len(opportunities),
            "pipeline_value": round(total_pipeline_value, 2),
            "weighted_close_rate": round(weighted_close_rate / 100, 2),
            "forecast_conversion": round(total_pipeline_value * weighted_close_rate / 100, 2),
            "stage_breakdown": stage_counts,
            "stage_forecast": {k: round(v, 2) for k, v in stage_values.items()},
            "next_90_days": sum(opp.expected_value for opp in opportunities if opp.stage in [LeadStatus.QUALIFIED, LeadStatus.DEMO_SCHEDULED])
        }
    
    async def calculate_sales_metrics(self) -> Dict[str, float]:
        """Calculate sales performance metrics"""
        opportunities = list(self.opportunities.values())
        
        if not opportunities:
            return {"conversion_rate": 0, "avg_deal_size": 0, "win_rate": 0}
        
        won = [o for o in opportunities if o.stage == LeadStatus.CLOSED_WON]
        total = len(opportunities)
        
        return {
            "conversion_rate": len(won) / max(1, total) * 100,
            "avg_deal_size": sum(o.expected_value for o in won) / max(1, len(won)),
            "win_rate": len(won) / max(1, len([o for o in opportunities if o.stage in [LeadStatus.PROPOSAL_SENT, LeadStatus.NEGOTIATING]])) * 100,
            "pipeline_velocity": sum(1 / max(1, (o.last_contact - o.created_at).days) for o in opportunities) / total
        }
    
    def create_sequenced_campaign(self, leads: List[str], sequence: List[Dict]) -> Dict:
        """Create automated follow-up sequence for multiple leads"""
        campaigns = {}
        
        for lead_id in leads:
            for step_num, step in enumerate(sequence):
                task = AgentTask(
                    task_id=f"seq_{lead_id}_{step_num}_{datetime.utcnow().timestamp()}",
                    priority=3,
                    task_type="follow_up",
                    payload={"lead_id": lead_id}
                )
                # Would schedule actual tasks in production
            
            campaigns[lead_id] = {
                "sequence": sequence,
                "status": "scheduled",
                "start_date": datetime.utcnow().isoformat()
            }
        
        return campaigns