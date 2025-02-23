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
        self.variables: Dict[str, Any] = {}
        self.start_time = datetime.now()
        self.entities = ticket.entities if hasattr(ticket, 'entities') else {}
        
    def store_result(self, step_number: int = None, result: Dict[str, Any] = None, success: bool = True, error: Optional[str] = None, step: int = None) -> None:
        """Store the result of a step execution. Supports both step_number and step parameters."""
        # Handle both step_number and step parameters for backward compatibility
        step_num = step_number if step_number is not None else step
        if step_num is None:
            raise ValueError("Either step_number or step must be provided")

        end_time = datetime.now()
        step_result = StepResult(
            step_number=step_num,
            step_name=self.current_step.get('name', '') if self.current_step else '',
            success=success,
            result=result,
            error=error,
            end_time=end_time,
            duration=(end_time - self.start_time).total_seconds()
        )
        self.step_results[step_num] = step_result
        
        # Update variables with step results if specified
        if success and self.current_step and 'output_vars' in self.current_step:
            self._update_variables(self.current_step['output_vars'], result)
            
        logger.debug(f"Stored result for step {step_num}")

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
        self.current_step = {**step, 'step_number': step_number}
        
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
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = value
            else:
                self.variables[name] = value
                
            logger.debug(f"Set variable {name} = {value}")
            
        except Exception as e:
            logger.error(f"Error setting variable {name}: {str(e)}")
            
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
        
        successful_steps = sum(1 for result in self.step_results.values() if result.success)
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
            }
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
        logger.debug("Execution context rolled back to initial state") 