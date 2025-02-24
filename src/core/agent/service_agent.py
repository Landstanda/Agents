from typing import Dict, Any, Optional, List
import logging
import asyncio
from datetime import datetime
from src.models import Ticket, TicketStatus
from src.core.agent.base_agent import BaseAgent
from src.utils.flow_logger import FlowLogger
from src.core.module_interface import ModuleResponse
from src.core.success_evaluator import SuccessEvaluator
from src.core.execution.context import ExecutionContext

logger = logging.getLogger(__name__)

class ServiceAgent(BaseAgent):
    """
    Service-specific agent implementation that extends BaseAgent with additional
    functionality for service execution and management.
    """
    
    def __init__(self, flow_logger: Optional[FlowLogger] = None):
        """Initialize the service agent"""
        super().__init__()
        self._busy_lock = asyncio.Lock()
        self.is_busy = False
        self.current_service = None
        self.flow_logger = flow_logger or FlowLogger()
        self.success_evaluator = SuccessEvaluator()
        
    async def execute_service(self, service_name: str, ticket: Ticket) -> Dict[str, Any]:
        """Execute a service with enhanced handling and monitoring"""
        logger.info(f"\n=== Starting service execution for ticket {ticket.ticket_id} ===")
        logger.info(f"Service: {service_name}")
        
        # Use async lock to check and set busy state
        async with self._busy_lock:
            if self.is_busy:
                logger.warning("⚠️ Agent is busy with another service")
                ticket.update_status(TicketStatus.ERROR)
                ticket.add_error("Agent is busy with another service", "execution_error")
                return {'status': 'error', 'error': 'Agent is busy with another service'}
            self.is_busy = True
        
        try:
            # Initialize if needed
            if not self._initialized:
                await self.initialize()
            
            # Get and validate service
            service_def = self.service_registry.get_item(service_name)
            if not service_def:
                raise ValueError(f"Service '{service_name}' not found")
                
            # Create execution context
            context = ExecutionContext(ticket=ticket, service_def=service_def)
            
            # Execute service steps
            for step_num, step in enumerate(service_def['steps'], 1):
                # Update context with current step
                context.set_current_step(step, step_num)
                
                # Execute step with retry
                step_result = await self._execute_step_with_retry(step, context)
                context.store_result(step_num, step_result)
                
                # Check for step failure
                if not step_result.get('success', False):
                    error_msg = step_result.get('error', 'Step failed without specific error')
                    logger.error(f"Step {step_num} failed: {error_msg}")
                    await self._handle_step_failure(context, step, error_msg)
                    return {
                        'status': 'error',
                        'error': f"Step {step_num} failed: {error_msg}",
                        'step': step_num,
                        'execution_summary': context.get_execution_summary()
                    }
            
            # All steps completed successfully
            success_response = {
                'status': 'success',
                'execution_summary': context.get_execution_summary(),
                'results': context.step_results
            }
            
            # Log success
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "ServiceAgent",
                    "service_execution_complete",
                    {
                        'service': service_name,
                        'ticket_id': ticket.ticket_id,
                        'execution_summary': context.get_execution_summary()
                    }
                )
            
            return success_response
            
        except Exception as e:
            logger.error(f"Error executing service: {str(e)}")
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "ServiceAgent",
                    "service_execution_error",
                    {
                        'service': service_name,
                        'ticket_id': ticket.ticket_id,
                        'error': str(e)
                    }
                )
            return {
                'status': 'error',
                'error': str(e)
            }
        finally:
            # Release busy state
            async with self._busy_lock:
                self.is_busy = False
                
    async def _execute_step_with_retry(
        self, 
        step: Dict[str, Any], 
        context: ExecutionContext,
        max_attempts: int = 3,
        delay_seconds: float = 2.0
    ) -> Dict[str, Any]:
        """Execute a step with retry logic"""
        for attempt in range(max_attempts):
            try:
                result = await self._execute_step(step, context)
                
                # Check success criteria
                if self.success_evaluator.evaluate_success(result, step.get('success_criteria', {})):
                    return {
                        'success': True,
                        'result': result,
                        'attempt': attempt + 1,
                        'execution_time': context.get_step_execution_time()
                    }
                
                # If we get here, step didn't meet success criteria
                error_msg = f"Step failed to meet success criteria (attempt {attempt + 1}/{max_attempts})"
                logger.warning(error_msg)
                context.add_error(error_msg, "success_criteria_failure", step)
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay_seconds)
                    continue
                    
                return {
                    'success': False,
                    'error': error_msg,
                    'result': result,
                    'attempt': attempt + 1,
                    'execution_time': context.get_step_execution_time()
                }
                
            except Exception as e:
                error_msg = f"Error executing step: {str(e)}"
                logger.error(error_msg)
                context.add_error(error_msg, "execution_error", step)
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay_seconds)
                    continue
                    
                return {
                    'success': False,
                    'error': error_msg,
                    'attempt': attempt + 1,
                    'execution_time': context.get_step_execution_time()
                }
                
    async def _execute_step(self, step: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Execute a single step"""
        try:
            # Get tool for step
            tool_name = step['tool']
            tool_class = self.tool_registry.get_item(tool_name)
            if not tool_class:
                raise ValueError(f"Tool '{tool_name}' not found")
            
            # Create tool instance
            tool = tool_class()
            
            # Prepare parameters
            params = self._prepare_parameters(step, context)
            
            # Execute tool
            result = await tool.execute(**params)
            
            # Convert ModuleResponse to dict if needed
            if isinstance(result, ModuleResponse):
                result = result.to_dict()
            
            return result
            
        except Exception as e:
            logger.error(f"Error in step execution: {str(e)}")
            raise
            
    def _prepare_parameters(self, step: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Prepare parameters for tool execution"""
        params = step.get('params', {}).copy()
        
        # Add context to params
        params['context'] = context
        
        # Replace any template variables
        for key, value in params.items():
            if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                var_name = value[1:-1]
                params[key] = context.get_variable(var_name, context.ticket.entities.get(var_name))
                    
        return params
        
    async def _handle_step_failure(
        self, 
        context: ExecutionContext,
        failed_step: Dict[str, Any], 
        error_msg: str
    ) -> None:
        """Handle step failure and update context"""
        step_name = failed_step.get('name', 'Unknown step')
        context.add_error(error_msg, "step_failure", failed_step)
        context.ticket.add_error(error_msg, "step_failure", step_name)
        
        if self.flow_logger:
            await self.flow_logger.log_event(
                "ServiceAgent",
                "step_failure",
                {
                    'ticket_id': context.ticket.ticket_id,
                    'step_name': step_name,
                    'error': error_msg,
                    'execution_summary': context.get_execution_summary()
                }
            ) 