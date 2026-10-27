"""
Product Builder Agent
Generates insights, reports, and handles user queries
"""

import asyncio
import logging
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from pydantic import BaseModel

from .base_agent import BaseAgent, AgentTask, AgentConfig

logger = logging.getLogger(__name__)


@dataclass
class CompetitiveInsight:
    question: str
    insight: str
    sources: List[str]
    confidence: float
    generated_at: datetime


@dataclass
class MarketReport:
    title: str
    executive_summary: str
    key_findings: List[str]
    recommendations: List[str]
    data_sources: List[str]
    generated_at: datetime
    report_type: str
    sector: Optional[str] = None


class ReportRequest(BaseModel):
    """Request model for report generation"""
    question: str
    sector: Optional[str] = None
    timeframe: str = "last_quarter"
    format: str = "text"  # text, json, markdown


class ProductBuilderAgent(BaseAgent):
    """Agent for generating insights and handling user queries"""
    
    def __init__(self, config: AgentConfig, mission_control_url: str = "http://localhost:8000"):
        super().__init__(config, mission_control_url)
        
        # Template cache for report generation
        self.templates = {
            "competitive_analysis": """
# Competitive Analysis: {sector}

## Executive Summary
{summary}

## Key Findings
{findings}

## Recommendations
{recommendations}

## Data Sources
{sources}
            """,
            "trend_report": """
# Market Trend Report: {sector}

## Overview
{trend_summary}

## Notable Trends
{trends}

## Implications
{implications}
            """
        }
        
        # Response templates for common queries
        self.response_templates = {
            "pricing_comparison": """
**Pricing Comparison for [COMPANY]**

| Plan | Price | Features |
|------|-------|----------|
{plans}

**Our Advantage**: {advantage}

*Compared as of {date}*
            """,
            "feature_request": """
**Feature Analysis: {feature}**

This feature appears in {count} of {total} solutions we've analyzed.

**Top implementations**:
{implementations}

**Recommendation**: {recommendation}
            """
        }
    
    async def process_task(self, task: AgentTask) -> Any:
        """Process product-related tasks"""
        task_type = task.payload.get("task_type")
        
        if task_type == "answer_query":
            return await self._answer_query(task)
        elif task_type == "generate_report":
            return await self._generate_report(task)
        elif task_type == "extract_insight":
            return await self._extract_insight(task)
        elif task_type == "summarize_data":
            return await self._summarize_data(task)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    async def _answer_query(self, task: AgentTask) -> str:
        """Answer a user query about markets, competitors, or products"""
        question = task.payload.get("question", "")
        context = task.payload.get("context", {})
        
        # Simple keyword-based routing for MVP
        query_lower = question.lower()
        
        if "price" in query_lower or "pricing" in query_lower:
            return await self._handle_pricing_query(question, context)
        elif "feature" in query_lower:
            return await self._handle_feature_query(question, context)
        elif "competitor" in query_lower or "competitor" in query_lower:
            return await self._handle_competitor_query(question, context)
        else:
            return await self._handle_generic_query(question, context)
    
    async def _handle_pricing_query(self, question: str, context: Dict) -> str:
        """Handle pricing-related queries"""
        # Extract company name from question
        company_match = re.search(r'(.+?)\s+(pricing|price|tier)', question, re.IGNORECASE)
        company = company_match.group(1) if company_match else "Unknown"
        
        # This would normally fetch from Market Scout Agent cache
        # For MVP, return structured response
        return f"""
**Pricing Analysis for {company}**

Based on analysis of publicly available pricing information:

1. **Starter Tier**: $29/month - Basic features for small teams
2. **Professional Tier**: $99/month - Advanced features, unlimited queries
3. **Enterprise Tier**: $299/month - API access, custom integrations

*Note: Pricing varies by region and promotional offers. Check the official pricing page for current rates.*
        """
    
    async def _handle_feature_query(self, question: str, context: Dict) -> str:
        """Handle feature-related queries"""
        feature_match = re.search(r'how\s+(?:does|is) (.+?) (?:implemented|built|structured)', question, re.IGNORECASE)
        feature = feature_match.group(1) if feature_match else "the feature"
        
        return f"""
**Implementation Analysis: {feature}**

**Common Approaches**:
1. RESTful API endpoints with GraphQL fallback
2. Event-driven architecture with message queues
3. Microservice pattern for scalability

**Best Practices**:
- Use feature flags for gradual rollout
- Implement comprehensive logging
- Design for horizontal scaling

**Security Considerations**:
- Input validation on all endpoints
- Rate limiting to prevent abuse
- Authentication via JWT tokens
        """
    
    async def _handle_competitor_query(self, question: str, context: Dict) -> str:
        """Handle competitor comparison queries"""
        competitor_match = re.search(r'vs\.?|compared to|versus(?:\s+)?(.+?)(?:\s+and|\s*,|\s+$)', question, re.IGNORECASE)
        
        return """
**Competitive Analysis**

**SimilarWeb**:
- Strengths: Traffic analytics, global rankings
- Weaknesses: Expensive, complex for small businesses
- Pricing: Starts at $199/month

**Crunchbase**:
- Strengths: Company data, funding information
- Weaknesses: Limited real-time data
- Pricing: Pro at $29/month, Enterprise at $99/month

**Our Unique Value**:
- Free tier available with basic insights
- AI-powered trend analysis
- GDPR-compliant data handling
- Personalized recommendations
        """
    
    async def _handle_generic_query(self, question: str, context: Dict) -> str:
        """Handle generic queries using LLM reasoning"""
        # For now, return placeholder - would integrate with LLM in production
        return f"""
**Answer to: {question}**

Based on our market analysis and competitive intelligence dataset:

[AI-generated response would appear here in production]

*Powered by MarketMinder AI's knowledge graph*
        """
    
    async def _generate_report(self, task: AgentTask) -> Dict[str, Any]:
        """Generate a market or competitive report"""
        request_data = task.payload.get("request", {})
        
        # Parse request
        question = request_data.get("question", "")
        sector = request_data.get("sector", "technology")
        report_type = request_data.get("report_type", "competitive_analysis")
        
        # Generate report based on type
        if report_type == "competitive_analysis":
            report = await self._generate_competitive_report(sector)
        elif report_type == "trend_report":
            report = await self._generate_trend_report(sector)
        else:
            report = await self._generate_generic_report(question, sector)
        
        return report.__dict__
    
    async def _generate_competitive_report(self, sector: str) -> MarketReport:
        """Generate competitive analysis report"""
        return MarketReport(
            title=f"Competitive Analysis: {sector}",
            executive_summary=f"This report analyzes the competitive landscape in the {sector} sector, identifying key players, market positioning, and opportunities for differentiation.",
            key_findings=[
                f"Market is dominated by 3-5 major players in {sector}",
                "Pricing varies significantly based on feature depth",
                "AI/ML features are becoming table stakes",
                "GDPR compliance is a key differentiator in EU markets"
            ],
            recommendations=[
                "Focus on AI-powered insights as differentiation",
                "Target SMB segment with simplified pricing",
                "Develop partnerships with complementary tools",
                "Invest in data visualization to improve user experience"
            ],
            data_sources=[
                "Public company filings",
                "Product websites",
                "Industry reports",
                "Customer reviews"
            ],
            generated_at=datetime.utcnow(),
            report_type="competitive_analysis",
            sector=sector
        )
    
    async def _generate_trend_report(self, sector: str) -> MarketReport:
        """Generate market trend report"""
        return MarketReport(
            title=f"Market Trends: {sector}",
            executive_summary=f"Quarterly analysis of emerging trends in the {sector} sector.",
            key_findings=[
                "AI integration accelerating across all use cases",
                "Shift toward subscription-based pricing models",
                "Increased focus on sustainability and ESG metrics",
                "Remote work driving need for collaboration features"
            ],
            recommendations=[
                "Monitor AI regulation developments",
                "Plan for hybrid work model support",
                "Invest in sustainability reporting features",
                "Explore international expansion opportunities"
            ],
            data_sources=[
                "Industry publications",
                "Conference presentations",
                "Social media sentiment analysis",
                "Search trend data"
            ],
            generated_at=datetime.utcnow(),
            report_type="trend_report",
            sector=sector
        )
    
    async def _generate_generic_report(self, question: str, sector: str) -> MarketReport:
        """Generate report based on user question"""
        return MarketReport(
            title=f"Market Analysis: {question[:50]}",
            executive_summary=f"Analysis generated in response to: {question}",
            key_findings=[
                "Market intelligence extracted from multiple sources",
                "Competitive positioning mapped",
                "Opportunities identified through trend analysis",
                "Recommendations based on best practices"
            ],
            recommendations=[
                "Evaluate current market position",
                "Identify gaps in offerings",
                "Develop go-to-market strategy",
                "Monitor competitive responses"
            ],
            data_sources=["Automated market scanning", "Competitive analysis", "Trend monitoring"],
            generated_at=datetime.utcnow(),
            report_type="custom"
        )
    
    async def _extract_insight(self, task: AgentTask) -> CompetitiveInsight:
        """Extract a specific insight from data"""
        data = task.payload.get("data", "")
        question = task.payload.get("question", "")
        
        # Extract key insight from data
        insight = f"Analysis of {len(data)} data points reveals patterns relevant to: {question}"
        
        return CompetitiveInsight(
            question=question,
            insight=insight,
            sources=["MarketScan", "CompetitiveIntelligence", "TrendAnalysis"],
            confidence=0.75,
            generated_at=datetime.utcnow()
        )
    
    async def _summarize_data(self, task: AgentTask) -> str:
        """Summarize larger datasets or reports"""
        data = task.payload.get("data", "")
        max_length = task.payload.get("max_length", 500)
        
        if len(data) <= max_length:
            return data
        
        # Truncate with summary
        summary = data[:max_length-100] + "\n\n... [truncated for brevity]"
        return summary
    
    async def handle_user_query(self, query: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Main entry point for handling user queries"""
        task = AgentTask(
            task_id=f"user_query_{datetime.utcnow().timestamp()}",
            priority=5,
            task_type="answer_query",
            payload={
                "question": query,
                "user_id": user_id,
                "context": {"timestamp": datetime.utcnow().isoformat()}
            }
        )
        
        result = await self.execute_task(task)
        return {
            "query": query,
            "response": result,
            "response_time_ms": 100,  # Would measure actual time
            "sources": ["MarketMinder AI Knowledge Base"]
        }