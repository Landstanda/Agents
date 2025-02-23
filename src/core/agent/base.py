from typing import Dict, Any, Optional, Type, List
from abc import ABC, abstractmethod
import logging
from src.models import Ticket, TicketStatus
from src.core.module_interface import BaseModule, ModuleResponse
from src.utils.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)

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

class Agent(AgentInterface):
    """Core agent implementation"""
    
    def __init__(self):
        """Initialize agent with required components"""
        self.service_registry = None
        self.tool_registry = None
        self.executor = None
        self._initialized = False
        self._error_handlers = {}
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Agent instance created")
        
    async def _handle_execution_error(self, ticket: Ticket, error: Exception, step: Optional[Dict[str, Any]] = None):
        """Handle execution errors and update dependent steps"""
        self.logger.error(f"Error in ticket {ticket.ticket_id}: {str(error)}")
        
        # Update ticket status
        ticket.update_status(TicketStatus.ERROR)
        ticket.add_error(str(error), "execution_error", step.get('name') if step else None)
        
        # Find dependent steps
        if step and ticket.execution_plan:
            dependent_steps = self._find_dependent_steps(step, ticket.execution_plan)
            for dep_step in dependent_steps:
                await self._mark_step_blocked(ticket, dep_step, f"Blocked by error in step {step.get('name')}")
                
    def _find_dependent_steps(self, failed_step: Dict[str, Any], execution_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find steps that depend on the failed step"""
        dependent_steps = []
        failed_step_num = failed_step.get('step_number')
        
        for step in execution_plan:
            dependencies = step.get('depends_on', [])
            if failed_step_num in dependencies:
                dependent_steps.append(step)
                # Recursively find steps that depend on this step
                dependent_steps.extend(self._find_dependent_steps(step, execution_plan))
                
        return dependent_steps
        
    async def _mark_step_blocked(self, ticket: Ticket, step: Dict[str, Any], reason: str):
        """Mark a step as blocked and update ticket state"""
        step['status'] = 'blocked'
        step['blocked_reason'] = reason
        ticket.add_error(f"Step {step.get('name')} blocked: {reason}", "step_blocked", step.get('name'))
        
    async def _handle_dependent_steps(self, ticket: Ticket, error_info: Dict[str, Any]):
        """Handle steps that depend on a failed step"""
        failed_step = error_info.get('step')
        if failed_step and ticket.execution_plan:
            dependent_steps = self._find_dependent_steps(failed_step, ticket.execution_plan)
            for step in dependent_steps:
                await self._mark_step_blocked(ticket, step, f"Depends on failed step {failed_step.get('name')}")
                
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
                await self.service_registry.load_services()
                
            if not self.tool_registry:
                self.tool_registry = ToolRegistry()
                await self.tool_registry.load_tools()
                
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
        self.logger.debug("\n" + "="*50)
        self.logger.debug(f"Processing ticket: {ticket.ticket_id}")
        self.logger.debug(f"Service: {ticket.service}")
        self.logger.debug(f"Status: {ticket.status}")

        try:
            if not self._initialized:
                await self.initialize()

            if not self.executor:
                raise ValueError("Executor not initialized")

            # Get service definition
            service_def = self.service_registry.get_service(ticket.service)
            if not service_def:
                raise ValueError(f"Service '{ticket.service}' not found")

            # Execute service
            result = await self.executor.execute_service(service_def, ticket)
            
            # Update ticket with results
            ticket.execution_results.append(result)

            # Check if any step had an error
            has_error = False
            for step_result in result.get('results', []):
                if isinstance(step_result, dict):
                    if step_result.get('status') == 'error' or not step_result.get('success', True):
                        has_error = True
                        error_msg = step_result.get('error', 'Unknown error')
                        ticket.add_error(error_msg, 'step_error', None)
                        break

            if has_error or result.get('status') == 'error':
                ticket.status = TicketStatus.ERROR
            else:
                ticket.status = TicketStatus.COMPLETED

        except Exception as e:
            self.logger.error(f"Error executing service '{ticket.service}': {str(e)}")
            ticket.status = TicketStatus.ERROR
            ticket.errors.append({
                'message': str(e),
                'type': 'execution_error',
                'step': None,
                'timestamp': datetime.now()
            })
            
    async def execute_service(self, service_name: str, ticket: Ticket) -> Dict[str, Any]:
        """Execute a specific service"""
        if not self._initialized:
            await self.initialize()
            
        try:
            # Get service definition
            service_def = self.service_registry.get_service(service_name)
            if not service_def:
                raise ValueError(f"Service '{service_name}' not found")
                
            # Execute service using executor
            if not self.executor:
                raise ValueError("Executor not initialized")
                
            result = await self.executor.execute_service(service_def, ticket)
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing service '{service_name}': {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            } 