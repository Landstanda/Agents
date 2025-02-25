from typing import Dict, Any, Optional
import logging
from datetime import datetime
from src.models import Ticket, TicketStatus
from src.core.agent.interface import AgentInterface
from src.utils.logging import get_logger
from src.core.registry import ServiceRegistry, ToolRegistry
from src.core.agent.executor import ServiceExecutor

logger = get_logger(__name__)

class BaseAgent(AgentInterface):
    """Base agent implementation with common functionality"""
    
    def __init__(self):
        """Initialize agent with required components"""
        self.service_registry = None
        self.tool_registry = None
        self.executor = None
        self._initialized = False
        self._error_handlers = {}
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self) -> None:
        """Initialize agent components"""
        if self._initialized:
            self.logger.warning("Agent already initialized")
            return
            
        try:
            self.logger.debug("Initializing agent components...")
            
            # Initialize registries if not already set
            if not self.service_registry:
                self.service_registry = ServiceRegistry()
                await self.service_registry.initialize()
            elif not self.service_registry.initialized:
                await self.service_registry.initialize()
                
            if not self.tool_registry:
                self.tool_registry = ToolRegistry()
                await self.tool_registry.initialize()
            elif not self.tool_registry.initialized:
                await self.tool_registry.initialize()
                
            # Initialize executor if not already set
            if not self.executor:
                self.executor = ServiceExecutor(
                    service_registry=self.service_registry,
                    tool_registry=self.tool_registry
                )
                
            self._initialized = True
            self.logger.info("Agent initialization complete")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {str(e)}")
            raise
            
    async def process_ticket(self, ticket: Ticket) -> None:
        """Process a ticket through the service execution pipeline"""
        # Skip processing if ticket is None (used for initialization testing)
        if ticket is None:
            self.logger.debug("Skipping processing for None ticket (initialization test)")
            return
            
        self.logger.debug(f"Processing ticket: {ticket.ticket_id}")
        self.logger.debug(f"Service: {ticket.service}")
        self.logger.debug(f"Status: {ticket.status}")

        try:
            if not self._initialized:
                await self.initialize()

            if not self.executor:
                raise ValueError("Executor not initialized")

            # Execute service
            result = await self.executor.execute_service(ticket.service, ticket)
            
            # Update ticket with results
            ticket.execution_results.append(result)

            # Update ticket status based on results
            if result.get('status') == 'error':
                if ticket.status != TicketStatus.ERROR:  # Only update if not already in error state
                    ticket.update_status(TicketStatus.ERROR)
                ticket.add_error(result.get('error', 'Unknown error'), 'execution_error')
            else:
                ticket.update_status(TicketStatus.COMPLETED)

        except Exception as e:
            self.logger.error(f"Error executing service '{ticket.service}': {str(e)}")
            if ticket.status != TicketStatus.ERROR:  # Only update if not already in error state
                ticket.update_status(TicketStatus.ERROR)
            ticket.add_error(str(e), 'execution_error')
            
    async def execute_service(self, service_name: str, ticket: Ticket) -> Dict[str, Any]:
        """Execute a specific service"""
        if not self._initialized:
            await self.initialize()
            
        try:
            # Execute service using executor
            if not self.executor:
                raise ValueError("Executor not initialized")
                
            result = await self.executor.execute_service(service_name, ticket)
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing service '{service_name}': {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'results': []  # Include an empty results array
            } 