from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class ChainInterface(ABC):
    """Abstract base class defining the interface for all chains in the system."""
    
    @abstractmethod
    async def process(self, request: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a request through the chain.
        
        Args:
            request (str): The request to process
            context (Optional[Dict[str, Any]]): Additional context for processing
            
        Returns:
            Dict[str, Any]: The processing result containing at least:
                - 'status': str ('success' or 'error')
                - 'message': str (response message or error description)
                - 'data': Optional[Any] (any additional data)
        """
        pass
    
    @abstractmethod
    async def execute(self, chain_vars: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the chain's core functionality.
        
        Args:
            chain_vars (Dict[str, Any]): Variables needed for chain execution
            
        Returns:
            Dict[str, Any]: The execution result containing at least:
                - 'status': str ('success' or 'error')
                - 'message': str (response message or error description)
                - 'data': Optional[Any] (any additional data)
        """
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """
        Get the capabilities of this chain.
        
        Returns:
            Dict[str, Any]: Description of chain capabilities including:
                - name: str (name of the chain)
                - description: str (what the chain does)
                - functions: List[str] (available functions)
                - examples: List[str] (example requests)
                - keywords: List[str] (keywords for request matching)
        """
        pass
    
    @abstractmethod
    def can_handle_request(self, request: str) -> bool:
        """
        Check if this chain can handle the given request.
        
        Args:
            request (str): The request to check
            
        Returns:
            bool: True if the chain can handle the request, False otherwise
        """
        pass

class BaseChain(ChainInterface):
    """Base implementation of a chain with common functionality."""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self._capabilities = self._initialize_capabilities()
        self.keywords = self._initialize_keywords()
    
    def _initialize_capabilities(self) -> Dict[str, Any]:
        """Initialize the chain's capabilities. Override in subclass."""
        return {
            "name": self.name,
            "description": "Base chain implementation",
            "functions": [],
            "examples": [],
            "keywords": self._initialize_keywords()
        }
    
    def _initialize_keywords(self) -> List[str]:
        """Initialize keywords for request matching. Override in subclass."""
        return []
    
    @property
    def capabilities(self) -> Dict[str, Any]:
        """Return the chain's capabilities."""
        return self._capabilities
    
    def can_handle_request(self, request: str) -> bool:
        """Check if the chain can handle the request based on keywords."""
        return any(keyword.lower() in request.lower() for keyword in self.keywords)
    
    async def process(self, request: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a request by converting it to chain variables and executing."""
        try:
            # Convert request and context to chain variables
            chain_vars = {
                'text': request,
                **(context or {})
            }
            
            # Execute the chain with the prepared variables
            return await self.execute(chain_vars)
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error processing request in {self.name}: {str(e)}",
                "data": None
            }
    
    async def execute(self, chain_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Default implementation that should be overridden by subclasses."""
        return {
            "status": "error",
            "message": f"Execute method not implemented for {self.name}",
            "data": None
        } 