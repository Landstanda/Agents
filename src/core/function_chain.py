from typing import List, Dict, Any
from .module_interface import BaseModule

class FunctionChain:
    """Manages sequences of module executions"""
    
    def __init__(self, modules: List[BaseModule]):
        self.modules = modules
    
    def execute_chain(self, initial_params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all modules in sequence"""
        current_params = initial_params
        
        for module in self.modules:
            if module.validate_params(current_params):
                current_params = module.execute(current_params)
            else:
                raise ValueError(f"Invalid parameters for module: {module.__class__.__name__}")
                
        return current_params 