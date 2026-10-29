"""
Finance Controller Agent
Handles all billing, subscriptions, cash flow, and financial metrics
"""

import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import stripe
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from ..base_agent import BaseAgent, AgentTask, AgentConfig

logger = logging.getLogger(__name__)
Base = declarative_base()


class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(String, nullable=False)
    subscription_id = Column(String, unique=True, nullable=False)
    plan_tier = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="usd")
    status = Column(String, default="active")
    trial_end = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Invoice(Base):
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(String, nullable=False)
    invoice_id = Column(String, unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, default="draft")
    invoice_date = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    subscription_id = Column(String, nullable=True)


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    payment_id = Column(String, unique=True, nullable=False)
    customer_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="usd")
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


class FinanceMetrics(BaseModel):
    """Financial metrics for health dashboard"""
    mrr: float
    arr: float
    total_revenue: float
    churn_rate: float
    cac: float
    ltv: float
    ltv_cac_ratio: float
    cash_balance: float
    cash_runway_days: float
    billing_errors: int


class FinanceControllerAgent(BaseAgent):
    """Agent responsible for all financial operations"""
    
    def __init__(self, config: AgentConfig, db_url: str, stripe_secret_key: str, mission_control_url: str = "http://localhost:8000"):
        super().__init__(config, mission_control_url)
        
        self.db_url = db_url
        stripe.api_key = stripe_secret_key
        
        # Setup database
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db_session = SessionLocal()
        
        # Financial tracking
        self.subscriptions: Dict[str, Subscription] = {}
        self.billing_errors = 0
        self._financial_loop_task: Optional[asyncio.Task] = None
    
    async def process_task(self, task: AgentTask) -> Any:
        """Process financial tasks"""
        task_type = task.payload.get("task_type")
        
        if task_type == "create_invoice":
            return await self._create_invoice(task)
        elif task_type == "generate_subscription":
            return await self._generate_subscription(task)
        elif task_type == "webhook_handler":
            return await self._handle_webhook(task)
        elif task_type == "calculate_metrics":
            return await self._calculate_metrics(task)
        elif task_type == "billing_check":
            return await self._perform_billing_check(task)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    async def _create_invoice(self, task: AgentTask) -> Dict[str, Any]:
        """Create a new invoice"""
        customer_id = task.payload["customer_id"]
        amount = task.payload["amount"]
        
        try:
            invoice = stripe.Invoice.create(
                customer=customer_id,
                amount_paid=int(amount * 100),  # Convert to cents
                currency="usd",
                metadata={"source": "marketminder-ai"}
            )
            
            return {
                "status": "success",
                "invoice_id": invoice.id,
                "amount": amount
            }
        except Exception as e:
            self.billing_errors += 1
            return {"status": "error", "message": str(e)}
    
    async def _generate_subscription(self, task: AgentTask) -> Dict[str, Any]:
        """Generate a new subscription"""
        customer_id = task.payload["customer_id"]
        price_id = task.payload["price_id"]
        trial_days = task.payload.get("trial_days", 7)
        
        try:
            # Create customer if doesn't exist
            try:
                customer = stripe.Customer.retrieve(customer_id)
            except stripe.CustomerNotFoundError:
                customer = stripe.Customer.create(
                    email=task.payload["email"],
                    metadata={"source": "marketminder-ai"}
                )
            
            # Create subscription
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{"price": price_id}],
                trial_period_days=trial_days,
                expand=["latest_invoice.payment_intent"]
            )
            
            # Store in database
            db_sub = Subscription(
                customer_id=customer.id,
                subscription_id=subscription.id,
                plan_tier=task.payload.get("plan_tier", "starter"),
                amount=float(subscription.latest_invoice.amount_paid) / 100,
                status=subscription.status,
                current_period_end=datetime.fromtimestamp(subscription.current_period_end)
            )
            self.db_session.add(db_sub)
            self.db_session.commit()
            
            return {
                "status": "success",
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
            }
        except Exception as e:
            self.billing_errors += 1
            return {"status": "error", "message": str(e)}
    
    async def _handle_webhook(self, task: AgentTask) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        payload = task.payload["data"]
        sig_header = task.payload["sig_header"]
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
            )
        except ValueError as e:
            return {"status": "error", "message": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            return {"status": "error", "message": "Invalid signature"}
        
        # Handle different event types
        if event["type"] == "invoice.payment_succeeded":
            invoice = event["data"]["object"]
            payment = Payment(
                payment_id=invoice["payment_intent"],
                customer_id=invoice["customer"],
                amount=invoice["amount_paid"] / 100,
                status="completed"
            )
            self.db_session.add(payment)
            self.db_session.commit()
        
        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            db_sub = self.db_session.query(Subscription).filter_by(subscription_id=subscription["id"]).first()
            if db_sub:
                db_sub.status = "cancelled"
                self.db_session.commit()
        
        return {"status": "success", "event_type": event["type"]}
    
    async def _calculate_metrics(self, task: AgentTask) -> FinanceMetrics:
        """Calculate financial metrics for dashboard"""
        # Get active subscriptions for MRR calculation
        active_subs = self.db_session.query(Subscription).filter(
            Subscription.status == "active",
            Subscription.current_period_end > datetime.utcnow()
        ).all()
        
        mrr = sum(sub.amount for sub in active_subs)
        arr = mrr * 12
        
        # Calculate churn (simplified - 30 day window)
        last_30_days = datetime.utcnow() - timedelta(days=30)
        new_subs = self.db_session.query(Subscription).filter(
            Subscription.created_at > last_30_days
        ).count()
        
        cancelled_subs = self.db_session.query(Subscription).filter(
            Subscription.status == "cancelled",
            Subscription.updated_at > last_30_days
        ).count()
        
        churn_rate = (cancelled_subs / max(1, new_subs + cancelled_subs)) * 100
        
        # Simplified metrics
        total_revenue = sum(p.amount for p in self.db_session.query(Payment).filter(Payment.status == "completed").all())
        
        return FinanceMetrics(
            mrr=mrr,
            arr=arr,
            total_revenue=total_revenue,
            churn_rate=churn_rate,
            cac=0.0,  # Will be calculated differently
            ltv=0.0,  # Will be calculated differently
            ltv_cac_ratio=0.0,
            cash_balance=self._get_cash_balance(),
            cash_runway_days=self._calculate_cash_runway(),
            billing_errors=self.billing_errors
        )
    
    async def _perform_billing_check(self, task: AgentTask) -> Dict[str, Any]:
        """Check for billing issues: dunning, failed payments, expiring cards"""
        issues = []
        
        # Check for subscriptions due for renewal
        due_subscriptions = self.db_session.query(Subscription).filter(
            Subscription.current_period_end <= datetime.utcnow() + timedelta(days=3),
            Subscription.status == "active"
        ).all()
        
        for sub in due_subscriptions:
            try:
                stripe.Subscription.modify(
                    sub.subscription_id,
                    cancel_at_period_end=True
                )
                issues.append({
                    "type": "dunning",
                    "subscription_id": sub.subscription_id,
                    "customer_id": sub.customer_id
                })
            except Exception as e:
                issues.append({"type": "error", "message": str(e)})
        
        return {"issues": issues, "checked_at": datetime.utcnow().isoformat()}
    
    def _get_cash_balance(self) -> float:
        """Get current cash balance from environment/config"""
        # In production, this would query actual bank/PSP
        # For now, we track from revenue minus expenses
        return float(os.getenv("INITIAL_CASH_BALANCE", "25000"))
    
    def _calculate_cash_runway(self) -> float:
        """Calculate days of cash runway based on burn rate"""
        # Simplified: assume MRR is monthly burn (conservative)
        if self.mrr_callback:
            mrr = self.mrr_callback()
            if mrr > 0:
                return self._get_cash_balance() / (mrr / 30)
        return 0.0
    
    def set_mrr_callback(self, callback: callable):
        """Set callback for MRR value (used in cash runway calculation)"""
        self.mrr_callback = callback
    
    async def run_daily_checks(self):
        """Run daily billing health checks"""
        while self._running:
            try:
                # Update metrics
                metrics = await self._calculate_metrics({"payload": {"task_type": "calculate_metrics"}})
                
                # Report to mission control
                await self.report_health()
                
                # Check for dunning
                await self.execute_task(AgentTask(
                    task_id="daily_billing_check",
                    priority=5,
                    task_type="billing_check",
                    payload={}
                ))
                
            except Exception as e:
                logger.error(f"Daily billing check failed: {e}")
            
            await asyncio.sleep(86400)  # 24 hours
    
    async def start(self):
        """Start the agent"""
        self._running = True
        await self._ensure_session()
        
        # Start daily check loop
        self._financial_loop_task = asyncio.create_task(self.run_daily_checks())
        logger.info(f"Finance Controller {self.config.name} started")