from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from src.models import Ticket

@dataclass
class ExecutionContext:
    """
    Holds and manages state during service execution.
    Provides a clean interface for tracking execution progress,
    storing variables, and managing results.
    """
    
    ticket: Ticket
    service_def: Dict[str, Any]
    variables: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[int, Any] = field(default_factory=dict)
    current_step: Optional[Dict[str, Any]] = None
    start_time: datetime = field(default_factory=datetime.now)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    def store_result(self, step_number: int, result: Any) -> None:
        """Store a step result"""
        self.step_results[step_number] = {
            'result': result,
            'timestamp': datetime.now(),
            'step': self.current_step
        }
        
    def get_result(self, step_number: int) -> Optional[Dict[str, Any]]:
        """Get a step result"""
        return self.step_results.get(step_number)
        
    def set_current_step(self, step: Dict[str, Any], step_number: int) -> None:
        """Set the current execution step"""
        self.current_step = {
            **step,
            'step_number': step_number,
            'start_time': datetime.now()
        }
        
    def add_error(self, error: str, error_type: str, step: Optional[Dict[str, Any]] = None) -> None:
        """Add an error to the context"""
        self.errors.append({
            'message': error,
            'type': error_type,
            'step': step,
            'timestamp': datetime.now()
        })
        
    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a variable value with optional default"""
        return self.variables.get(name, default)
        
    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable value"""
        self.variables[name] = value
        
    def get_execution_time(self) -> float:
        """Get total execution time in seconds"""
        return (datetime.now() - self.start_time).total_seconds()
        
    def get_step_execution_time(self) -> Optional[float]:
        """Get current step execution time in seconds"""
        if not self.current_step or 'start_time' not in self.current_step:
            return None
        return (datetime.now() - self.current_step['start_time']).total_seconds()
        
    def has_errors(self) -> bool:
        """Check if any errors occurred during execution"""
        return len(self.errors) > 0
        
    def get_last_error(self) -> Optional[Dict[str, Any]]:
        """Get the most recent error"""
        return self.errors[-1] if self.errors else None
        
    def get_step_count(self) -> int:
        """Get total number of steps in the service"""
        return len(self.service_def.get('steps', []))
        
    def get_completed_steps(self) -> List[int]:
        """Get list of completed step numbers"""
        return sorted(self.step_results.keys())
        
    def get_next_step(self) -> Optional[Dict[str, Any]]:
        """Get the next step to execute"""
        completed = set(self.step_results.keys())
        for i, step in enumerate(self.service_def.get('steps', []), 1):
            if i not in completed:
                return step
        return None
        
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of the execution"""
        return {
            'total_steps': self.get_step_count(),
            'completed_steps': len(self.step_results),
            'execution_time': self.get_execution_time(),
            'error_count': len(self.errors),
            'current_step': self.current_step.get('name') if self.current_step else None,
            'has_errors': self.has_errors()
        }
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary format"""
        return {
            'ticket_id': self.ticket.ticket_id,
            'service': self.service_def.get('name'),
            'variables': self.variables,
            'step_results': {
                str(k): {
                    'result': v['result'],
                    'timestamp': v['timestamp'].isoformat(),
                    'step': v['step']
                }
                for k, v in self.step_results.items()
            },
            'current_step': self.current_step,
            'start_time': self.start_time.isoformat(),
            'errors': [
                {
                    'message': e['message'],
                    'type': e['type'],
                    'step': e['step'],
                    'timestamp': e['timestamp'].isoformat()
                }
                for e in self.errors
            ]
        } 