from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from src.models import Ticket
from src.execution.context import ExecutionContext

class ModuleResponse:
    """Standardized response format for all modules"""
    
    # Protected attributes that shouldn't be overwritten by data
    _protected_attrs = {'success', 'data', 'error', 'error_type', 'to_dict', 'from_dict'}
    
    def __init__(self, success: bool, data: Dict[str, Any] = None, error: str = None, error_type: str = None):
        """Initialize a ModuleResponse with success status and optional data/error information."""
        # Set base attributes
        self._success = success
        self._data = data or {}
        self._error = error
        self._error_type = error_type
        
        # Add data fields as direct attributes if they don't conflict
        for key, value in (data or {}).items():
            if key not in self._protected_attrs:
                setattr(self, key, value)
    
    @property
    def success(self) -> bool:
        """Get success status."""
        return self._success
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get response data."""
        return self._data
    
    @property
    def error(self) -> Optional[str]:
        """Get error message if any."""
        return self._error
    
    @property
    def error_type(self) -> Optional[str]:
        """Get error type if any."""
        return self._error_type
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary format"""
        result = {
            "success": self._success,
            "data": self._data
        }
        if self._error:
            result["error"] = self._error
        if self._error_type:
            result["error_type"] = self._error_type
            
        # Add direct attributes to root level
        for key, value in self._data.items():
            if key not in self._protected_attrs:
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