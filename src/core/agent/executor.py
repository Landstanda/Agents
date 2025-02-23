from typing import Dict, Any, Optional, Type
import asyncio
from src.models import Ticket, TicketStatus
from src.core.services.registry import ServiceRegistry
from src.core.tools.registry import ToolRegistry
from src.execution.context import ExecutionContext
from src.core.module_interface import BaseModule, ModuleResponse
from src.utils.logging import get_logger
import logging

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
            
    async def execute_service(self, service_def: Dict[str, Any], ticket: Ticket) -> Dict[str, Any]:
        """Execute a service with the given ticket"""
        try:
            # Create execution context
            context = ExecutionContext(ticket, service_def)
            
            # Execute each step in sequence
            results = []
            for i, step in enumerate(service_def['steps'], 1):
                context.set_current_step(step, i)
                
                # Get tool for step
                tool_name = step['tool']
                tool_class = await self.tool_registry.get_tool(tool_name)
                if not tool_class:
                    raise ValueError(f"Tool '{tool_name}' not found")
                    
                # Create tool instance
                tool = tool_class()
                
                # Execute tool with parameters
                try:
                    parameters = step.get('parameters', {})
                    parameters['context'] = context
                    result = await tool.execute(**parameters)
                    
                    # Store result
                    context.store_result(i, {
                        'status': 'completed',
                        'results': result
                    })
                    results.append(result)
                    
                except Exception as e:
                    error_result = {
                        'status': 'error',
                        'error': str(e)
                    }
                    context.store_result(i, error_result)
                    return error_result
                    
            return {
                'status': 'completed',
                'results': results
            }
            
        except Exception as e:
            self.logger.error(f"Error executing service: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    async def _execute_step(self, step: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Execute a single step in the service"""
        try:
            # Get tool for step
            tool_name = step['tool']
            tool_class = await self.tool_registry.get_tool(tool_name)
            if not tool_class:
                raise ValueError(f"Tool '{tool_name}' not found")
                
            # Create tool instance
            tool = tool_class()
            
            # Execute tool with parameters
            parameters = step.get('parameters', {})
            parameters['context'] = context
            
            result = await tool.execute(**parameters)
            return {
                'status': 'completed',
                'results': result
            }
            
        except Exception as e:
            self.logger.error(f"Error executing step: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def _prepare_parameters(self, step: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Prepare parameters for tool execution"""
        params = step.get('parameters', {}).copy()
        
        # Replace any template variables with actual values
        for key, value in params.items():
            if isinstance(value, str) and value.startswith('$'):
                var_name = value[1:]
                if var_name in context.variables:
                    params[key] = context.variables[var_name]
                    
        return params
        
    async def _execute_step_with_retry(
        self, 
        step: Dict[str, Any], 
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Execute a step with retry logic"""
        max_attempts = step.get('retry_count', 3)
        delay_seconds = step.get('retry_delay', 5)
        
        for attempt in range(max_attempts):
            try:
                result = await self._execute_step(step, context)
                
                if result.get('success', False):
                    return result
                    
                # Check if we should retry
                if attempt < max_attempts - 1:
                    error_type = result.get('error_type', '')
                    if self._should_retry(error_type, step):
                        logger.warning(f"Retrying step {step.get('name')} after error: {result.get('error')}")
                        await asyncio.sleep(delay_seconds)
                        continue
                        
                return result
                
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.error(f"Error executing step: {str(e)}")
                    await asyncio.sleep(delay_seconds)
                    continue
                return {
                    'success': False,
                    'error': str(e),
                    'error_type': 'execution_error'
                }
                
        return {
            'success': False,
            'error': f"Step failed after {max_attempts} attempts",
            'error_type': 'max_retries_exceeded'
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