from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseModule(ABC):
    """Base interface for all task modules"""
    
    def __init__(self):
        """Initialize base module"""
        pass
    
    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the module's primary function"""
        pass
    
    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """Return list of module capabilities"""
        pass 