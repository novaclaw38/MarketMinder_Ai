"""
Base Agent Framework for MarketMinder AI
All specialized agents inherit from this base class
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
import aiohttp
import json
from pydantic import BaseModel, ValidationError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    OFFLINE = "offline"
    NEEDS_ATTENTION = "needs_attention"


@dataclass
class AgentTask:
    """Represents a task to be processed by an agent"""
    task_id: str
    priority: int  # 1-10, 10 is highest
    task_type: str
    payload: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    assigned_agent: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class AgentConfig(BaseModel):
    """Configuration for an agent"""
    name: str
    description: str
    max_concurrent_tasks: int = 5
    task_timeout_seconds: int = 300
    auto_restart: bool = True
    health_check_interval: int = 30
    notification_email: Optional[str] = None


class BaseAgent(ABC):
    """Abstract base class for all agents in the system"""
    
    def __init__(self, config: AgentConfig, mission_control_url: str = "http://localhost:8000"):
        self.config = config
        self.mission_control_url = mission_control_url
        self.status = AgentStatus.IDLE
        self.tasks: List[AgentTask] = []
        self.completed_tasks = 0
        self.failed_tasks = 0
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info(f"Agent {config.name} initialized")
    
    async def _ensure_session(self):
        """Ensure HTTP session is active"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
    
    async def close(self):
        """Cleanup resources"""
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()
    
    @abstractmethod
    async def process_task(self, task: AgentTask) -> Any:
        """Process a specific task. Must be implemented by subclasses."""
        pass
    
    async def execute_task(self, task: AgentTask) -> Any:
        """Execute a task with error handling and timing"""
        self.status = AgentStatus.PROCESSING
        task.assigned_agent = self.config.name
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Agent {self.config.name} starting task {task.task_type}")
            result = await asyncio.wait_for(
                self.process_task(task),
                timeout=self.config.task_timeout_seconds
            )
            
            task.result = result
            self.completed_tasks += 1
            self.status = AgentStatus.IDLE
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Task completed in {duration:.2f}s")
            
            return result
            
        except asyncio.TimeoutError:
            task.error = f"Task timed out after {self.config.task_timeout_seconds}s"
            self.failed_tasks += 1
            self.status = AgentStatus.ERROR
            logger.error(task.error)
            raise
            
        except Exception as e:
            task.error = str(e)
            self.failed_tasks += 1
            self.status = AgentStatus.ERROR
            logger.error(f"Task failed: {e}")
            raise
    
    async def report_health(self) -> Dict[str, Any]:
        """Report health status to Mission Control"""
        health_data = {
            "agent_name": self.config.name,
            "status": self.status.value,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "queue_size": len(self.tasks),
            "uptime": datetime.utcnow().isoformat()
        }
        
        try:
            await self._ensure_session()
            async with self._session.post(
                f"{self.mission_control_url}/agents/health",
                json=health_data
            ) as response:
                return await response.json()
        except Exception as e:
            logger.warning(f"Failed to report health: {e}")
            return health_data
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics for dashboard"""
        return {
            "tasks_completed": self.completed_tasks,
            "tasks_failed": self.failed_tasks,
            "current_queue": len(self.tasks),
            "success_rate": (self.completed_tasks / max(1, self.completed_tasks + self.failed_tasks)) * 100,
            "status": self.status.value
        }