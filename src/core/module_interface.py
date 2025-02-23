from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from src.models import Ticket
from src.execution.context import ExecutionContext

class ModuleResponse:
    """Standardized response format for all modules"""
    
    def __init__(self, success: bool, data: Dict[str, Any] = None, error: str = None, error_type: str = None):
        self.success = success
        self.data = data or {}
        self.error = error
        self.error_type = error_type
        
        # Add data fields as direct attributes for compatibility
        for key, value in (data or {}).items():
            setattr(self, key, value)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary format"""
        result = {
            "success": self.success,
            "data": self.data
        }
        if self.error:
            result["error"] = self.error
        if self.error_type:
            result["error_type"] = self.error_type
            
        # Add direct attributes to root level
        for key, value in self.data.items():
            result[key] = value
            
        return result
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModuleResponse':
        """Create ModuleResponse from dictionary"""
        # Extract core fields
        success = data.get("success", False)
        error = data.get("error")
        error_type = data.get("error_type")
        
        # Get all other fields as data
        data_fields = {k: v for k, v in data.items() 
                      if k not in {"success", "error", "error_type"}}
        
        return cls(
            success=success,
            data=data_fields,
            error=error,
            error_type=error_type
        )

class BaseModule(ABC):
    """Base interface for all tool modules"""
    
    @abstractmethod
    async def execute(self, context: ExecutionContext, **params) -> Dict[str, Any]:
        """Execute the module's functionality"""
        pass
        
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """Return list of module capabilities"""
        pass 