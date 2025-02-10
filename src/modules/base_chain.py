#!/usr/bin/env python3

from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import logging
import asyncio
from datetime import datetime
from ..core.chain_interface import BaseChain

logger = logging.getLogger(__name__)

class Chain(BaseChain):
    """Base class for all chains"""
    
    def __init__(self, name: str = None, version: str = "1.0"):
        if name is None:
            super().__init__()  # Use class name from BaseChain
        else:
            self.name = name  # Override the name from BaseChain
            
        self.version = version
        self.modules = {}  # Will be populated by child classes
        self.required_variables = []  # Will be populated by child classes
        self.optional_variables = []  # Will be populated by child classes
        self.success_criteria = []  # Will be populated by child classes
        self.execution_history = []
        self._capabilities = self._initialize_capabilities()
        self.keywords = self._initialize_keywords()
    
    def _initialize_capabilities(self) -> Dict[str, Any]:
        """Initialize chain capabilities"""
        return {
            "name": self.name,
            "description": "Base chain implementation",
            "functions": [],
            "examples": [],
            "keywords": self._initialize_keywords()
        }
    
    def _initialize_keywords(self) -> List[str]:
        """Initialize keywords for request matching"""
        return []
    
    @property
    def capabilities(self) -> Dict[str, Any]:
        """Return chain capabilities"""
        return self._capabilities
    
    def can_handle_request(self, request: str) -> bool:
        """Check if this chain can handle the request"""
        return any(keyword.lower() in request.lower() for keyword in self.keywords)
    
    async def process(self, request: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a request through the chain"""
        try:
            # Convert request and context to chain variables
            chain_vars = {
                'text': request,  # The natural language request
                **(context.get('variables', {}) if context else {}),  # Any extracted variables
            }
            
            # Execute the chain with the prepared variables
            return await self.execute(chain_vars)
            
        except Exception as e:
            logger.error(f"Error in chain process(): {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'data': None
            }
    
    def validate_variables(self, chain_vars: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate that all required variables are present"""
        missing = []
        invalid = []
        
        # Check required variables
        for var in self.required_variables:
            if var not in chain_vars:
                missing.append(var)
        
        # Basic type validation could be added here
        # This would be chain-specific and implemented by child classes
        
        return {
            "missing": missing,
            "invalid": invalid
        }
    
    def log_execution(self, step: str, result: Dict[str, Any]) -> None:
        """Log execution step and result"""
        self.execution_history.append({
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "result": result
        })
        
        # Log to file
        if result.get("status") == "error":
            logger.error(f"{self.name} - {step}: {result.get('error', 'Unknown error')}")
        else:
            logger.info(f"{self.name} - {step}: {result.get('status', 'completed')}")
    
    async def execute(self, chain_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Default implementation of execute method"""
        try:
            # Convert chain_vars to request and context
            request = chain_vars.get('text', '')
            context = {k: v for k, v in chain_vars.items() if k != 'text'}
            
            # Process the request
            return await self.process(request, context)
            
        except Exception as e:
            logger.error(f"Error in chain execute(): {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'data': None
            }
    
    async def cleanup(self) -> None:
        """Cleanup any resources used by the chain"""
        # Default implementation - can be overridden by child classes
        pass
    
    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get the execution history of this chain"""
        return self.execution_history
    
    def get_chain_info(self) -> Dict[str, Any]:
        """Get information about this chain"""
        return {
            "name": self.name,
            "version": self.version,
            "required_variables": self.required_variables,
            "optional_variables": self.optional_variables,
            "success_criteria": self.success_criteria
        }
    
    async def _execute_module(self, 
                            module_name: str, 
                            method_name: str, 
                            **kwargs) -> Dict[str, Any]:
        """Execute a module method with error handling"""
        try:
            if module_name not in self.modules:
                raise ValueError(f"Module {module_name} not found")
            
            module = self.modules[module_name]
            method = getattr(module, method_name)
            
            if not method:
                raise ValueError(f"Method {method_name} not found in {module_name}")
            
            result = await method(**kwargs)
            return {
                "status": "success",
                "result": result
            }
            
        except Exception as e:
            error_msg = f"Error executing {module_name}.{method_name}: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "error": error_msg
            }
    
    async def _execute_parallel(self, 
                              tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute multiple module tasks in parallel"""
        async_tasks = []
        
        for task in tasks:
            module_name = task.get("module")
            method_name = task.get("method")
            kwargs = task.get("kwargs", {})
            
            if module_name and method_name:
                async_tasks.append(
                    self._execute_module(module_name, method_name, **kwargs)
                )
        
        results = await asyncio.gather(*async_tasks, return_exceptions=True)
        return results
    
    def _check_success_criteria(self, result: Dict[str, Any]) -> bool:
        """Check if the chain execution met all success criteria"""
        # Default implementation - should be overridden by child classes
        # that have specific success criteria
        return result.get("status") == "success" 