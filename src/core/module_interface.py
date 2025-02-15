from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

class BaseModule(ABC):
    """Base interface that all modules must implement."""
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the module's main functionality.
        
        Args:
            params: Dictionary of parameters needed for execution
            
        Returns:
            Dictionary containing the results of the execution
        """
        raise NotImplementedError("Modules must implement execute method")
        
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate input parameters.
        
        Args:
            params: Dictionary of parameters to validate
            
        Returns:
            True if parameters are valid, False otherwise
        """
        return True  # Default implementation accepts all params 