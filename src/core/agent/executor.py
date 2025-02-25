from typing import Dict, Any, Optional, Type
import asyncio
from src.models import Ticket, TicketStatus
from src.core.services.registry import ServiceRegistry
from src.core.tools.registry import ToolRegistry
from src.execution.context import ExecutionContext
from src.core.module_interface import BaseModule, ModuleResponse
from src.utils.logging import get_logger
import logging
from datetime import datetime

logger = get_logger(__name__)

class ServiceExecutor:
    """Handles service execution and step processing"""
    
    def __init__(self, service_registry: ServiceRegistry, tool_registry: ToolRegistry):
        self.service_registry = service_registry
        self.tool_registry = tool_registry
        self._execution_locks: Dict[str, asyncio.Lock] = {}
        self._service_locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)
        self.logger.debug("ServiceExecutor initialized")
        
        # Monitoring hooks
        self.on_step_start = None
        self.on_step_complete = None
        
    async def initialize(self) -> None:
        """Initialize the executor"""
        if not self.service_registry.initialized:
            await self.service_registry.initialize()
        if not self.tool_registry.initialized:
            await self.tool_registry.initialize()
            
    async def _get_execution_lock(self, ticket_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific ticket execution"""
        async with self._global_lock:
            if ticket_id not in self._execution_locks:
                self._execution_locks[ticket_id] = asyncio.Lock()
            return self._execution_locks[ticket_id]
            
    async def _get_service_lock(self, service_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific service"""
        async with self._global_lock:
            if service_id not in self._service_locks:
                self._service_locks[service_id] = asyncio.Lock()
            return self._service_locks[service_id]
            
    async def execute_service(self, service_name: str, ticket: Ticket) -> Dict[str, Any]:
        """Execute a service with the given ticket"""
        results = []  # Initialize results array outside the try block
        try:
            # Validate service exists
            service_def = self.service_registry.get_item(service_name)
            if not service_def:
                error_msg = f"Service '{service_name}' not found"
                self.logger.error(error_msg)
                ticket.update_status(TicketStatus.ERROR)
                return {
                    'status': 'error',
                    'error': error_msg,
                    'results': results
                }
                
            # Create execution context with service definition
            context = ExecutionContext(ticket=ticket, service=service_def)
            
            # Set ticket status to ANALYZING before executing steps
            ticket.update_status(TicketStatus.ANALYZING)
            
            # Execute each step in sequence
            for i, step in enumerate(service_def.get('steps', [])):
                # Set step number
                step['step_number'] = i + 1
                
                self.logger.info(f"Executing step {i+1}: {step.get('name', 'Unnamed step')}")
                
                # Notify step start
                ticket.update_status(TicketStatus.EXECUTING)
                
                # Execute step
                step_result = await self._execute_step(step, context)
                results.append(step_result)
                
                # Check if step failed
                if step_result.get('status') == 'error':
                    self.logger.error(f"Step {i+1} failed: {step_result.get('error', 'Unknown error')}")
                    ticket.update_status(TicketStatus.ERROR)
                    
                    # Return early with error
                    return {
                        'status': 'error',
                        'error': step_result.get('error', f"Step {i+1} failed"),
                        'results': results
                    }
                
                # Log step completion
                self.logger.info(f"Completed step {i+1}: {step.get('name', 'Unnamed step')}")
                
                # TODO: Implement success criteria evaluation
                
            # All steps completed successfully
            ticket.update_status(TicketStatus.COMPLETED)
            
            # Create final result object
            final_result = {
                'status': 'completed',
                'results': results
            }
            
            # Extract event_id from the calendar step result if it exists
            # This is specifically for the schedule_meeting service
            if service_def.get('name') == 'Schedule Meeting' and len(results) > 1:
                calendar_result = results[1]  # The second step is the calendar step
                if isinstance(calendar_result.get('results'), dict) and 'event_id' in calendar_result.get('results', {}):
                    final_result['event_id'] = calendar_result['results']['event_id']
            
            return final_result
            
        except Exception as e:
            self.logger.error(f"Error executing service: {str(e)}")
            ticket.update_status(TicketStatus.ERROR)
            return {
                'status': 'error',
                'error': f"Error executing service: {str(e)}",
                'results': results  # Include the results array even when an exception occurs
            }

    async def _execute_step(self, step: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Execute a single step in the service"""
        try:
            # Get tool for step
            tool_name = step['tool']
            tool_class = self.tool_registry.get_item(tool_name)
            if not tool_class:
                raise ValueError(f"Tool '{tool_name}' not found")
                
            # Create tool instance
            tool = tool_class() if isinstance(tool_class, type) else tool_class
            
            # Set current step in context
            step_number = step.get('step_number', 0)
            context.set_current_step(step, step_number if step_number > 0 else 1)
            
            # If there's an action specified, add it to the ticket entities
            if 'action' in step:
                context.ticket.entities['operation'] = step['action']
            
            # Execute tool with context only, not passing other parameters directly
            result = await tool.execute(context=context)
            
            # Check if the tool execution was successful
            if isinstance(result, dict) and result.get('success') is False:
                self.logger.error(f"Tool execution failed: {result.get('error', 'Unknown error')}")
                # Update ticket status to reflect the error
                context.ticket.update_status(TicketStatus.ERROR)
                return {
                    'status': 'error',
                    'error': result.get('error', 'Tool execution failed'),
                    'results': result
                }
            
            # Store the result in context
            context.store_result(step_number if step_number > 0 else 1, result)
            
            return {
                'status': 'completed',
                'results': result
            }
            
        except Exception as e:
            self.logger.error(f"Error executing step: {str(e)}")
            # Update ticket status to reflect the error
            context.ticket.update_status(TicketStatus.ERROR)
            return {
                'status': 'error',
                'error': str(e)
            }

    def _prepare_parameters(self, step: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Prepare parameters for tool execution"""
        params = step.get('params', {}).copy()
        
        # Replace any template variables with actual values
        for key, value in params.items():
            if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                var_name = value[1:-1]
                params[key] = context.get_variable(var_name, context.ticket.entities.get(var_name))
                    
        return params
        
    async def _execute_step_with_retry(self, step: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Execute a step with retry logic"""
        max_attempts = step.get('retry_count', 1)
        delay = step.get('retry_delay', 0.1)
        backoff = step.get('retry_backoff', 2)
        attempt = 1
        first_error = None

        while attempt <= max_attempts:
            result = await self._execute_step(step, context)
            
            if result.get('success', False):
                return {
                    'success': True,
                    'status': 'completed',
                    'result': result.get('result', {}),
                    'alternative_used': False
                }

            error_type = result.get('error_type', 'unknown')
            error_msg = result.get('error', 'Unknown error')
            
            # Record error
            context.add_error({
                'step': step.get('name', 'unknown'),
                'error': error_msg,
                'error_type': error_type,
                'message': error_msg,
                'attempt': attempt,
                'timestamp': datetime.now().isoformat()
            })

            # Save first error for later
            if first_error is None:
                first_error = result

            if error_type == 'permanent_error' or attempt >= max_attempts:
                # Try alternative step
                alternative_step = step.get('alternative_step')
                if alternative_step:
                    alternative_step['step_number'] = step.get('step_number', 0)
                    alternative_result = await self._execute_step(alternative_step, context)
                    if alternative_result.get('success', False):
                        return {
                            'success': True,
                            'status': 'completed',
                            'result': alternative_result.get('result', {}),
                            'alternative_used': True
                        }
                
                # No alternative step or alternative step failed
                return {
                    'success': False,
                    'error': error_msg if error_type == 'permanent_error' else f'Max retries ({max_attempts}) exceeded: {error_msg}',
                    'error_type': 'permanent_error',
                    'status': 'error'
                }

            # Retryable error, not yet at max attempts
            await asyncio.sleep(delay)
            delay *= backoff
            attempt += 1

        # All attempts failed
        return {
            'success': False,
            'error': first_error.get('error', 'Unknown error'),
            'error_type': 'permanent_error',
            'status': 'error'
        }
        
    def _evaluate_success(
        self, 
        result: Dict[str, Any], 
        criteria: Dict[str, Any]
    ) -> bool:
        """Evaluate if a step result meets success criteria"""
        if not criteria:
            return result.get('success', False)
            
        criteria_type = criteria.get('type', 'all')
        conditions = criteria.get('conditions', [])
        
        if criteria_type == 'all':
            return all(self._evaluate_condition(cond, result) for cond in conditions)
        elif criteria_type == 'any':
            return any(self._evaluate_condition(cond, result) for cond in conditions)
        else:
            return False
            
    def _evaluate_condition(self, condition: str, result: Dict[str, Any]) -> bool:
        """Evaluate a single success condition"""
        try:
            # Create safe evaluation environment
            eval_globals = {"__builtins__": {}}
            eval_locals = {
                "response": result,
                "True": True,
                "False": False,
                "None": None
            }
            
            return bool(eval(condition, eval_globals, eval_locals))
            
        except Exception as e:
            logger.error(f"Error evaluating condition: {str(e)}")
            return False
            
    def _validate_required_entities(
        self, 
        service_def: Dict[str, Any], 
        entities: Dict[str, Any]
    ) -> list:
        """Validate that all required entities are present"""
        required = service_def.get('required_entities', [])
        return [entity for entity in required if entity not in entities]
        
    def _should_retry(self, error_type: str, step: Dict[str, Any]) -> bool:
        """Determine if a step should be retried based on error type"""
        retry_conditions = step.get('retry_conditions', {})
        return retry_conditions.get(error_type, False) 