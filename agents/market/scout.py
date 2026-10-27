"""
Market Scout Agent
Monitors markets, detects trends, analyzes competitors
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from urllib.parse import urljoin
import aiohttp
import html
from bs4 import BeautifulSoup
import json

from .base_agent import BaseAgent, AgentTask, AgentConfig

logger = logging.getLogger(__name__)


@dataclass
class MarketTrend:
    source: str
    headline: str
    url: str
    sentiment: str  # positive, neutral, negative
    relevance_score: float
    extracted_features: Dict[str, Any]
    published_at: datetime


@dataclass
class CompetitorAnalysis:
    company: str
    url: str
    pricing_tiers: List[Dict]
    feature_comparison: List[str]
    strengths: List[str]
    weaknesses: List[str]
    last_fetched: datetime


class MarketScoutAgent(BaseAgent):
    """Agent for market research and competitive intelligence"""
    
    def __init__(self, config: AgentConfig, mission_control_url: str = "http://localhost:8000"):
        super().__init__(config, mission_control_url)
        
        # Market sources configuration
        self.sources = {
            "tech_crunch": "https://techcrunch.com/category/startups/",
            "hackers_news": "https://news.ycombinator.com/",
            "indie_hackers": "https://www.indiehackers.com/",
            "reddit_startup": "https://www.reddit.com/r/startups/",
            "sec_edgar": "https://www.sec.gov/Archives/edgar/data/"
        }
        
        # Competitor tracking
        self.competitors = [
            {"name": "SimilarWeb", "url": "https://www.similarweb.com/", "keywords": ["analytics", "seo", "traffic"]},
            {"name": "Crunchbase", "url": "https://www.crunchbase.com/", "keywords": ["market", "competitor", "funding"]},
            {"name": "CB Insights", "url": "https://www.cbinsights.com/", "keywords": ["ai", "machine learning", "enterprise"]},
            {"name": "Gartner", "url": "https://www.gartner.com/", "keywords": ["magic quadrant", "market guide"]},
            {"name": "Forrester", "url": "https://www.forrester.com/", "keywords": ["wave", "market overview"]}
        ]
        
        # Cache for scraped data
        self._cache: Dict[str, Any] = {}
        self._last_trends: List[MarketTrend] = []
    
    async def process_task(self, task: AgentTask) -> Any:
        """Process market research tasks"""
        task_type = task.payload.get("task_type")
        
        if task_type == "scrape_trends":
            return await self._scrape_trends(task)
        elif task_type == "analyze_competitor":
            return await self._analyze_competitor(task)
        elif task_type == "search_companies":
            return await self._search_companies(task)
        elif task_type == "generate_market_report":
            return await self._generate_market_report(task)
        elif task_type == "check_pricing":
            return await self._check_competitor_pricing(task)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    async def _scrape_trends(self, task: AgentTask) -> List[MarketTrend]:
        """Scrape market trends from configured sources"""
        trends = []
        source_filter = task.payload.get("source")
        max_items = task.payload.get("max_items", 10)
        
        sources_to_scrape = [source_filter] if source_filter else list(self.sources.keys())
        
        async with aiohttp.ClientSession() as session:
            for source_name in sources_to_scrape:
                if source_name not in self.sources:
                    continue
                
                try:
                    url = self.sources[source_name]
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status != 200:
                            logger.warning(f"Failed to fetch {url}: {response.status}")
                            continue
                        
                        content = await response.text()
                        soup = BeautifulSoup(content, 'lxml')
                        
                        # Extract headlines and links (source-specific parsing)
                        items = self._extract_source_items(soup, source_name)
                        
                        for item in items[:max_items]:
                            trend = MarketTrend(
                                source=source_name,
                                headline=item.get("title", ""),
                                url=item.get("url", ""),
                                sentiment=item.get("sentiment", "neutral"),
                                relevance_score=item.get("relevance_score", 0.5),
                                extracted_features=item.get("features", {}),
                                published_at=datetime.utcnow()
                            )
                            trends.append(trend)
                            
                except Exception as e:
                    logger.error(f"Error scraping {source_name}: {e}")
        
        self._last_trends = trends
        return [t.__dict__ for t in trends]
    
    def _extract_source_items(self, soup: BeautifulSoup, source_name: str) -> List[Dict]:
        """Extract trend items from parsed HTML"""
        items = []
        
        # Generic extraction patterns
        if source_name == "tech_crunch":
            for article in soup.find_all("h2", class_="article__title"):
                link = article.find("a")
                if link and link.get("href"):
                    items.append({
                        "title": link.get_text(strip=True),
                        "url": link["href"],
                        "sentiment": "neutral",
                        "relevance_score": 0.7,
                        "features": {"section": "startups"}
                    })
        
        elif source_name == "hackers_news":
            for row in soup.find_all("tr", class_="athing"):
                title_elem = row.find("span", class_="titleline")
                if title_elem:
                    link = title_elem.find("a")
                    if link:
                        items.append({
                            "title": link.get_text(strip=True),
                            "url": link["href"],
                            "sentiment": "neutral",
                            "relevance_score": 0.6,
                            "features": {"score": row.find("span", class_="score").get_text() if row.find("span", class_="score") else "1 pt"}
                        })
        
        elif source_name == "reddit_startup":
            for post in soup.find_all("div", class_="Post__ ContainingElement"):
                title = post.find("h3")
                link = post.find("a", class_="Title")
                if title and link:
                    items.append({
                        "title": title.get_text(strip=True),
                        "url": f"https://reddit.com{link['href']}",
                        "sentiment": "neutral",
                        "relevance_score": 0.5,
                        "features": {"upvotes": "N/A"}
                    })
        
        else:
            # Generic fallback
            for link in soup.find_all("a", href=True):
                text = link.get_text(strip=True)
                if len(text) > 30 and len(text) < 300:  # Headline length heuristic
                    items.append({
                        "title": text,
                        "url": link["href"],
                        "sentiment": "neutral",
                        "relevance_score": 0.4,
                        "features": {}
                    })
        
        return items
    
    async def _analyze_competitor(self, task: AgentTask) -> CompetitorAnalysis:
        """Analyze a competitor's website and offerings"""
        competitor_name = task.payload["competitor"]
        
        # Find competitor in known list
        competitor = next((c for c in self.competitors if c["name"].lower() == competitor_name.lower()), None)
        if not competitor:
            raise ValueError(f"Unknown competitor: {competitor_name}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(competitor["url"], timeout=aiohttp.ClientTimeout(total=30)) as response:
                    content = await response.text()
                    soup = BeautifulSoup(content, 'lxml')
                    
                    # Extract pricing info
                    pricing = await self._extract_pricing(competitor["url"], session)
                    
                    # Feature extraction
                    features = self._extract_features(soup)
                    
                    analysis = CompetitorAnalysis(
                        company=competitor_name,
                        url=competitor["url"],
                        pricing_tiers=pricing,
                        feature_comparison=features,
                        strengths=[],
                        weaknesses=[],
                        last_fetched=datetime.utcnow()
                    )
                    
                    return analysis.__dict__
                    
        except Exception as e:
            logger.error(f"Competitor analysis failed: {e}")
            return {"error": str(e), "company": competitor_name}
    
    async def _extract_pricing(self, url: str, session: aiohttp.ClientSession) -> List[Dict]:
        """Extract pricing tiers from a website"""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                content = await response.text()
                soup = BeautifulSoup(content, 'lxml')
                
                tiers = []
                # Look for price elements
                price_elements = soup.find_all(string=re.compile(r'\$\d+|€\d+|£\d+'))
                
                for elem in price_elements:
                    price_text = elem.strip()
                    match = re.search(r'[$€£](\d+(?:\.\d+)?)', price_text)
                    if match:
                        tiers.append({
                            "price": float(match.group(1)),
                            "description": price_text,
                            "scraped_at": datetime.utcnow().isoformat()
                        })
                
                return tiers[:5]  # Limit to 5 tiers
                
        except Exception as e:
            logger.warning(f"Pricing extraction failed: {e}")
            return []
    
    def _extract_features(self, soup: BeautifulSoup) -> List[str]:
        """Extract feature descriptions from page"""
        features = set()
        
        # Look for bullet points, feature lists, etc.
        for ul in soup.find_all(["ul", "ol"]):
            for li in ul.find_all("li"):
                text = li.get_text(strip=True)
                if 10 < len(text) < 200:  # Reasonable feature description length
                    features.add(text)
        
        return list(features)[:10]  # Limit to top 10
    
    async def _search_companies(self, task: AgentTask) -> List[Dict]:
        """Search for companies matching criteria"""
        query = task.payload.get("query", "")
        industry = task.payload.get("industry", "")
        location = task.payload.get("location", "")
        
        results = []
        
        # Combine search terms
        search_terms = f"{query} {industry} {location}".strip()
        
        # This would integrate with actual APIs in production
        # For now, simulate with cached competitor data
        for competitor in self.competitors:
            if any(term.lower() in competitor.get("keywords", []) for term in search_terms.split()):
                results.append({
                    "name": competitor["name"],
                    "url": competitor["url"],
                    "match_reason": "keyword_match",
                    "confidence": 0.8
                })
        
        return results
    
    async def _generate_market_report(self, task: AgentTask) -> Dict[str, Any]:
        """Generate a comprehensive market report"""
        sector = task.payload.get("sector", "technology")
        timeframe = task.payload.get("timeframe", "last_quarter")
        
        # Get recent trends
        trends = await self._scrape_trends({"payload": {"max_items": 20}})
        
        # Analyze by sector
        sector_trends = [t for t in trends if sector.lower() in str(t.get("extracted_features", {})).lower()]
        
        report = {
            "sector": sector,
            "timeframe": timeframe,
            "generated_at": datetime.utcnow().isoformat(),
            "key_trends": sector_trends[:10],
            "trend_volume": len(sector_trends),
            "sentiment_distribution": {
                "positive": len([t for t in sector_trends if t.get("sentiment") == "positive"]),
                "neutral": len([t for t in sector_trends if t.get("sentiment") == "neutral"]),
                "negative": len([t for t in sector_trends if t.get("sentiment") == "negative"])
            },
            "opportunity_score": len(sector_trends) / max(1, len(trends)) * 100
        }
        
        return report


# Initialize LLM response model for trend sentiment analysis
class TrendSentimentRequest(BaseModel):
    title: str
    content: str
    url: str


# Health check endpoint response
class MarketHealth(BaseModel):
    source_status: Dict[str, str]
    last_scrape: datetime
    trends_available: int
    error_count: int