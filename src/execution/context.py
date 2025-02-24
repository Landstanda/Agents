from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from src.models import Ticket
from src.utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class StepResult:
    """Represents the result of a step execution"""
    step_number: int
    step_name: str
    success: bool
    result: Any
    error: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration: Optional[float] = None

class ExecutionContext:
    """Manages execution state and context for service execution"""
    
    def __init__(self, ticket: Ticket, service: Dict[str, Any]):
        self.ticket = ticket
        self.service = service
        self.current_step: Optional[Dict[str, Any]] = None
        self.step_results: Dict[int, StepResult] = {}
        self.variables = ticket.entities.copy()  # Initialize with a copy of ticket entities
        self.start_time = datetime.now()
        self.entities = ticket.entities if hasattr(ticket, 'entities') else {}
        self._step_start_time: Optional[datetime] = None
        self.steps_executed = []  # Track executed steps
        self.successful_steps = set()  # Track successful steps
        self.errors = []
        
    def get_current_time(self) -> datetime:
        """Get the current time"""
        return datetime.now()
        
    def get_step_execution_time(self) -> Optional[float]:
        """Get the execution time of the current step in seconds"""
        if not self._step_start_time:
            return None
        return (datetime.now() - self._step_start_time).total_seconds()
        
    def store_result(self, step_number: int, result: Dict[str, Any], success: bool = False) -> None:
        """Store a step result"""
        self.step_results[step_number] = result
        if success:
            self.successful_steps.add(step_number)
            
    def get_result(self, step_number: int) -> Optional[Dict[str, Any]]:
        """Get the result for a specific step"""
        step_result = self.step_results.get(step_number)
        if step_result:
            return step_result.result
        return None
        
    def get_step_result(self, step_number: int) -> Optional[StepResult]:
        """Get the result of a specific step"""
        return self.step_results.get(step_number)
        
    def get_all_results(self) -> List[StepResult]:
        """Get all step results in order"""
        return [self.step_results[i] for i in sorted(self.step_results.keys())]
        
    def set_current_step(self, step: Dict[str, Any], step_number: int) -> None:
        """Set the current step being executed"""
        step['step_number'] = step_number
        self.current_step = step
        self._step_start_time = datetime.now()  # Reset step timer
        
    def next_step(self, step: Dict[str, Any]) -> None:
        """Set the current execution step"""
        self.current_step = step
        logger.debug(f"Moving to step: {step.get('name')}")
        
    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a variable value from the context"""
        try:
            # Handle nested variable references
            if '.' in name:
                parts = name.split('.')
                value = self.variables
                for part in parts:
                    value = value.get(part, {})
                return value or default
            return self.variables.get(name, default)
            
        except Exception as e:
            logger.error(f"Error getting variable {name}: {str(e)}")
            return default
            
    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable in the context"""
        try:
            # Handle nested variable references
            if '.' in name:
                parts = name.split('.')
                target = self.variables
                
                # Validate the path exists or can be created
                for part in parts[:-1]:
                    if part not in target:
                        if not isinstance(target, dict):
                            raise Exception(f"Cannot set nested path '{name}': parent is not a dictionary")
                        target[part] = {}
                    elif not isinstance(target[part], dict):
                        raise Exception(f"Cannot set nested path '{name}': parent is not a dictionary")
                    target = target[part]
                    
                target[parts[-1]] = value
            else:
                self.variables[name] = value
                
            logger.debug(f"Set variable {name} = {value}")
            
        except Exception as e:
            logger.error(f"Error setting variable {name}: {str(e)}")
            raise  # Re-raise the exception for proper error handling
            
    def _update_variables(self, output_vars: Dict[str, str], result: Any) -> None:
        """Update variables from step results"""
        try:
            for var_name, result_path in output_vars.items():
                value = self._extract_value(result, result_path)
                if value is not None:
                    self.set_variable(var_name, value)
                    
        except Exception as e:
            logger.error(f"Error updating variables: {str(e)}")
            
    def _extract_value(self, data: Any, path: str) -> Any:
        """Extract a value from nested data structure using dot notation"""
        try:
            current = data
            for part in path.split('.'):
                if isinstance(current, dict):
                    current = current.get(part)
                elif isinstance(current, (list, tuple)) and part.isdigit():
                    current = current[int(part)]
                else:
                    return None
            return current
            
        except Exception:
            return None
            
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of the execution"""
        self.end_time = datetime.now()
        
        successful_steps = len(self.successful_steps)
        total_steps = len(self.step_results)
        
        return {
            'ticket_id': self.ticket.ticket_id,
            'service': self.service.get('name'),
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration': (self.end_time - self.start_time).total_seconds(),
            'total_steps': total_steps,
            'successful_steps': successful_steps,
            'success': successful_steps == total_steps,
            'results': {
                step_num: {
                    'name': result.step_name,
                    'success': result.success,
                    'error': result.error,
                    'duration': result.duration
                }
                for step_num, result in self.step_results.items()
            },
            'steps_executed': len(self.steps_executed),
            'errors': len(self.errors),
            'status': self.ticket.status.value if hasattr(self.ticket, 'status') else None
        }
        
    def has_failed_steps(self) -> bool:
        """Check if any steps have failed"""
        return any(not result.success for result in self.step_results.values())
        
    def get_failed_steps(self) -> List[StepResult]:
        """Get all failed steps"""
        return [result for result in self.step_results.values() if not result.success]
        
    def clear_variables(self) -> None:
        """Clear all variables except those from ticket entities"""
        original_entities = self.ticket.entities.copy()
        self.variables.clear()
        self.variables.update(original_entities)
        
    def rollback(self) -> None:
        """Rollback the execution context to initial state"""
        self.step_results.clear()
        self.clear_variables()
        self.current_step = None
        self.successful_steps.clear()
        self.steps_executed.clear()
        self.errors.clear()
        logger.debug("Execution context rolled back to initial state")

    def add_error(self, error_info: Dict[str, Any]) -> None:
        """Add an error to the context"""
        self.errors.append(error_info)
        if hasattr(self.ticket, 'add_error'):
            self.ticket.add_error(
                error_info.get('error', 'Unknown error'),
                error_info.get('error_type', 'unknown'),
                error_info.get('step', 'unknown')
            )
            
    def add_step(self, step_info: Dict[str, Any]) -> None:
        """Add a step to the execution history"""
        # Check if this step is already recorded (to avoid counting retries)
        step_number = step_info.get('step_number')
        step_name = step_info.get('step_name')
        tool = step_info.get('tool')
        
        # Only add if this is a new step (different number or name)
        # For alternative steps, replace the original step
        existing_steps = [s for s in self.ticket.steps_executed 
                         if s.get('step_number') == step_number]
        
        if existing_steps:
            # If this is an alternative step, replace the original step
            if tool == 'alternative_tool':
                self.ticket.steps_executed.remove(existing_steps[0])
                self.ticket.steps_executed.append(step_info)
                if existing_steps[0] in self.steps_executed:
                    self.steps_executed.remove(existing_steps[0])
                self.steps_executed.append(step_info)
        else:
            self.ticket.steps_executed.append(step_info)
            self.steps_executed.append(step_info)
            
    def get_last_error(self) -> Optional[dict]:
        """Get the last error from the error history."""
        if not self.ticket.error_history:
            return None
        return self.ticket.error_history[-1]

    def get_step_count(self) -> int:
        """Get the number of unique steps executed (excluding retries and replaced steps)"""
        return len(set(s.get('step_number') for s in self.steps_executed)) 