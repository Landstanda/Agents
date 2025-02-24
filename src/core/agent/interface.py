from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from src.models import Ticket

class AgentInterface(ABC):
    """Base interface for agent implementations"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the agent and load necessary components"""
        pass
        
    @abstractmethod
    async def process_ticket(self, ticket: Ticket) -> None:
        """Process a ticket through the execution pipeline"""
        pass
        
    @abstractmethod
    async def execute_service(self, service_name: str, ticket: Ticket) -> Dict[str, Any]:
        """Execute a specific service"""
        pass 