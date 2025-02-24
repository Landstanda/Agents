from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Deque
import logging
import asyncio
from datetime import datetime
from src.models import Ticket, TicketStatus
from src.core.agent.base_agent import BaseAgent
from src.utils.flow_logger import FlowLogger
from src.core.module_interface import ModuleResponse
from src.core.success_evaluator import SuccessEvaluator
from src.execution.context import ExecutionContext
from collections import deque

logger = logging.getLogger(__name__)

class ExecutionStatus(Enum):
    """Represents the internal execution status of a step or service"""
    SUCCESS = auto()
    RETRYING = auto()
    TRYING_ALTERNATIVE = auto()
    FAILED = auto()
    PERMANENT_ERROR = auto()

@dataclass
class StepResult:
    """Represents the result of a single step execution"""
    step_name: str
    success: bool
    status: ExecutionStatus
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    result_data: Dict[str, Any] = field(default_factory=dict)
    retries: int = 0
    max_retries: int = 0
    has_alternative: bool = False
    alternative_tried: bool = False
    alternative_succeeded: bool = False

@dataclass
class ServiceExecutionState:
    """Tracks the overall state of service execution"""
    steps_succeeded: List[str] = field(default_factory=list)
    steps_failed: List[str] = field(default_factory=list)
    current_step: Optional[str] = None
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    execution_status: ExecutionStatus = ExecutionStatus.SUCCESS
    has_permanent_error: bool = False

    def update_from_step_result(self, result: StepResult) -> None:
        """Update service state based on step result"""
        if result.success or result.alternative_succeeded:
            self.steps_succeeded.append(result.step_name)
            if result.step_name in self.steps_failed:
                self.steps_failed.remove(result.step_name)
        else:
            if result.step_name not in self.steps_failed:
                self.steps_failed.append(result.step_name)
            
            if result.status == ExecutionStatus.PERMANENT_ERROR:
                self.has_permanent_error = True
                self.execution_status = ExecutionStatus.PERMANENT_ERROR
            elif result.status == ExecutionStatus.FAILED:
                if not result.has_alternative or (result.has_alternative and result.alternative_tried and not result.alternative_succeeded):
                    self.execution_status = ExecutionStatus.FAILED

    def get_ui_status(self) -> TicketStatus:
        """Convert execution status to UI status"""
        if self.has_permanent_error or self.execution_status == ExecutionStatus.FAILED:
            return TicketStatus.ERROR
        if self.steps_succeeded and not self.error_history:
            return TicketStatus.COMPLETED
        return TicketStatus.ERROR

    def add_error(self, error: Dict[str, Any]) -> None:
        """Add an error to the history"""
        self.error_history.append(error)
        if error["type"] in ["permanent_error", "service_not_found", "max_retries_error"]:
            self.has_permanent_error = True
            self.execution_status = ExecutionStatus.PERMANENT_ERROR

    def should_continue(self) -> bool:
        """Determine if execution should continue"""
        return not (self.has_permanent_error or self.execution_status == ExecutionStatus.FAILED)

    def get_final_error(self) -> Optional[str]:
        """Get the final error message"""
        if not self.error_history:
            return None
        
        # If we have a permanent error, use that
        for error in reversed(self.error_history):
            if error["type"] == "permanent_error":
                return error["message"]
        
        # Otherwise use the last error
        return self.error_history[-1]["message"]

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
        
    async def execute_service(self, service_name: str, ticket: Ticket) -> dict:
        """Execute a service with the given name using the provided ticket."""
        self.logger.info(f"Starting execution of service: {service_name}")
        
        # Initialize execution state
        execution_state = ServiceExecutionState()
        
        # Get service definition
        service_def = self.service_registry.get_item(service_name)
        if not service_def:
            error_msg = f"Service '{service_name}' not found"
            error = {
                "message": error_msg,
                "type": "service_not_found",
                "step": None,
                "timestamp": datetime.now()
            }
            execution_state.add_error(error)
            self._record_error(ticket, error_msg, "service_not_found", None)
            ticket.status = execution_state.get_ui_status()
            return {"success": False, "error": error_msg, "status": "error"}

        # Validate service definition
        try:
            for step in service_def["steps"]:
                if "tool" in step and not self.tool_registry.get_item(step["tool"]):
                    error_msg = f"Tool '{step['tool']}' not found"
                    error = {
                        "message": error_msg,
                        "type": "service_not_found",
                        "step": step["name"],
                        "timestamp": datetime.now()
                    }
                    execution_state.add_error(error)
                    self._record_error(ticket, error_msg, "service_not_found", step["name"])
                    ticket.status = execution_state.get_ui_status()
                    return {"success": False, "error": error_msg, "status": "error"}
        except (KeyError, TypeError) as e:
            error_msg = f"Invalid service definition: {str(e)}"
            error = {
                "message": error_msg,
                "type": "service_not_found",
                "step": None,
                "timestamp": datetime.now()
            }
            execution_state.add_error(error)
            self._record_error(ticket, error_msg, "service_not_found", None)
            ticket.status = execution_state.get_ui_status()
            return {"success": False, "error": error_msg, "status": "error"}

        # Execute each step
        steps_executed = []
        for step in service_def["steps"]:
            execution_state.current_step = step["name"]
            step_result = await self._execute_step_with_retry(step, ticket)
            execution_state.update_from_step_result(step_result)
            
            # Record step execution
            step_info = {
                "step": step["name"],
                "tool": step.get("tool") if not step_result.alternative_succeeded else "alternative_tool",
                "action": step.get("action"),
                "params": step.get("params", {}),
                "result": {
                    "success": step_result.success or step_result.alternative_succeeded,
                    "error": step_result.error_message,
                    "status": step_result.status.name.lower(),
                    "data": step_result.result_data,
                    "alternative_used": step_result.alternative_succeeded
                },
                "timestamp": datetime.now()
            }
            steps_executed.append(step_info)

            # Break if we should not continue
            if not execution_state.should_continue():
                break

        # Update ticket state
        ticket.steps_executed = deque(steps_executed, maxlen=ticket.steps_executed.maxlen)
        ticket.status = execution_state.get_ui_status()

        # Return final result
        status = "error" if execution_state.has_permanent_error or execution_state.execution_status == ExecutionStatus.FAILED else "completed"
        error = execution_state.get_final_error()
        return {
            "success": bool(execution_state.steps_succeeded) and not execution_state.has_permanent_error,
            "status": status,
            "error": error or step_result.error_message  # Use step error if no final error
        }

    async def _execute_step_with_retry(self, step: dict, ticket: Ticket) -> StepResult:
        """Execute a step with retry logic and alternative step handling"""
        step_result = StepResult(
            step_name=step["name"],
            success=False,
            status=ExecutionStatus.SUCCESS,
            max_retries=step.get("retry_count", 3),
            has_alternative="alternative_step" in step
        )
        
        retry_delay = step.get("retry_delay", 0.1)
        attempt = 0
        initial_error_count = len(ticket.error_history)

        # Try main step with retries
        while attempt < step_result.max_retries:
            try:
                result = await self._execute_step(step, ticket)
                if result["success"]:
                    step_result.success = True
                    step_result.status = ExecutionStatus.SUCCESS  # Update status to SUCCESS
                    step_result.result_data = result.get("result", {})
                    self._cleanup_error_history(ticket, initial_error_count)
                    return step_result
                
                # Handle failure
                step_result.error_type = result.get("error_type", "retryable_error")
                step_result.error_message = result.get("error", f"Failed attempt {attempt + 1}")
                step_result.retries = attempt + 1
                
                if step_result.error_type == "permanent_error":
                    step_result.status = ExecutionStatus.PERMANENT_ERROR
                    self._record_error(ticket, step_result.error_message, step_result.error_type, step["name"])
                    return step_result  # Return immediately for permanent errors
                
                step_result.status = ExecutionStatus.RETRYING
                self._record_error(ticket, step_result.error_message, step_result.error_type, step["name"])
                
                attempt += 1
                if attempt < step_result.max_retries:
                    await asyncio.sleep(retry_delay * (2 ** (attempt - 1)))
                
            except Exception as e:
                step_result.error_type = "retryable_error"
                step_result.error_message = str(e)
                step_result.retries = attempt + 1
                step_result.status = ExecutionStatus.RETRYING
                self._record_error(ticket, str(e), "retryable_error", step["name"])
                
                attempt += 1
                if attempt < step_result.max_retries:
                    await asyncio.sleep(retry_delay * (2 ** (attempt - 1)))

        # Try alternative step if available
        if step_result.has_alternative:
            step_result.status = ExecutionStatus.TRYING_ALTERNATIVE
            step_result.alternative_tried = True
            
            alt_step = step["alternative_step"]
            alt_step["name"] = step["name"]  # Use same name for error tracking
            alt_result = await self._execute_step(alt_step, ticket)
            
            if alt_result["success"]:
                step_result.success = True
                step_result.alternative_succeeded = True
                step_result.status = ExecutionStatus.SUCCESS
                step_result.result_data = alt_result.get("result", {})
                self._cleanup_error_history(ticket, initial_error_count)
                return step_result

        # Final failure state
        step_result.status = ExecutionStatus.FAILED
        if not step_result.error_message:
            step_result.error_message = f"Max retries ({step_result.max_retries}) exceeded"
            self._record_error(ticket, step_result.error_message, "max_retries_error", step["name"])
        return step_result

    def _cleanup_error_history(self, ticket: Ticket, initial_error_count: int) -> None:
        """Clean up error history after successful retry or alternative"""
        if len(ticket.error_history) > initial_error_count:
            ticket.error_history = ticket.error_history[:initial_error_count]
            ticket.errors = deque([], maxlen=ticket.errors.maxlen)

    async def _execute_step(self, step: Dict[str, Any], ticket: Ticket) -> Dict[str, Any]:
        """Execute a single step with consistent error handling"""
        try:
            # Validate tool
            tool_name = step.get('tool')
            if not tool_name:
                error = {
                    'success': False,
                    'error': 'Tool name not specified',
                    'error_type': 'permanent_error'
                }
                self._record_error(ticket, error['error'], error['error_type'], step.get('name', 'unknown'))
                return error

            tool_class = self.tool_registry.get_item(tool_name)
            if not tool_class:
                error = {
                    'success': False,
                    'error': f"Tool '{tool_name}' not found",
                    'error_type': 'permanent_error'
                }
                self._record_error(ticket, error['error'], error['error_type'], step.get('name', 'unknown'))
                return error

            # Create tool instance
            try:
                tool = (tool_class() if isinstance(tool_class, type) else 
                       tool_class() if callable(tool_class) else tool_class)
            except Exception as e:
                error = {
                    'success': False,
                    'error': f"Failed to create tool instance: {str(e)}",
                    'error_type': 'permanent_error'
                }
                self._record_error(ticket, error['error'], error['error_type'], step.get('name', 'unknown'))
                return error

            # Execute tool
            try:
                context = ExecutionContext(ticket, ticket.service)
                result = await tool.execute(context=context)
                
                if not isinstance(result, dict):
                    result = {'success': False, 'error': 'Invalid tool response format'}

                # Record successful execution
                if result.get('success', False):
                    ticket.add_step(
                        step_name=step.get('name', 'unknown'),
                        tool=tool_name,
                        action=step.get('action', 'unknown'),
                        params=step.get('params', {}),
                        result=result.get('result', {})
                    )
                else:
                    self._record_error(
                        ticket,
                        result.get('error', 'Unknown error'),
                        result.get('error_type', 'unknown'),
                        step.get('name', 'unknown')
                    )
                
                return result

            except Exception as e:
                error = {
                    'success': False,
                    'error': f"Error executing tool: {str(e)}",
                    'error_type': 'execution_error'
                }
                self._record_error(ticket, error['error'], error['error_type'], step.get('name', 'unknown'))
                return error

        except Exception as e:
            error = {
                'success': False,
                'error': f"Error executing step: {str(e)}",
                'error_type': 'execution_error'
            }
            self._record_error(ticket, error['error'], error['error_type'], step.get('name', 'unknown'))
            return error

    def _record_error(self, ticket: Ticket, message: str, error_type: str, step_name: str) -> None:
        """Record an error with consistent format"""
        error = {
            "message": message,
            "type": error_type,
            "step": step_name,
            "context": None,
            "timestamp": datetime.now()
        }
        ticket.error_history.append(error)
        ticket.errors.append(error)

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

    def _create_execution_summary(self, context: ExecutionContext) -> Dict[str, Any]:
        """Create a summary of the service execution"""
        return {
            "status": "completed" if context.ticket.status == TicketStatus.COMPLETED else "error",
            "execution_details": context.get_execution_summary(),
            "steps_executed": [step for step in context.ticket.steps_executed],
            "errors": [error for error in context.ticket.errors]
        } 

    async def _execute_tool_action(self, tool_name: str, action: str, context: ExecutionContext) -> Dict[str, Any]:
        """Execute a tool action and evaluate its success"""
        try:
            # Get tool instance
            tool_class = self.tool_registry.get_item(tool_name)
            if not tool_class:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not found",
                    "error_type": "tool_not_found"
                }
            
            # Create tool instance
            tool = tool_class() if isinstance(tool_class, type) else tool_class
            
            # Execute tool
            response = await tool.execute(context, action=action)
            
            # Convert ModuleResponse to dict if needed
            if not isinstance(response, dict):
                response = response.to_dict() if hasattr(response, 'to_dict') else {
                    "success": False,
                    "error": "Invalid tool response format",
                    "error_type": "invalid_response"
                }
            
            # Evaluate success
            success_evaluator = SuccessEvaluator()
            success = success_evaluator.evaluate(
                context.current_step.get("success_criteria", {}), 
                response
            )
            
            if success.get("success", False):
                # Store successful result
                context.store_result(
                    step_number=context.current_step.get('step_number'),
                    result=response,
                    success=True
                )
                context.add_step(context.current_step)
                
            return success
            
        except Exception as e:
            error_msg = str(e)
            context.add_error(error_msg, "execution_error", context.current_step)
            return {
                "success": False,
                "error": error_msg,
                "error_type": "execution_error"
            } 