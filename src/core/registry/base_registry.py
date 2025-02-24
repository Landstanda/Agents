from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type
import logging
from src.utils.logging import get_logger
from pathlib import Path

class BaseRegistry(ABC):
    """Base class for all registries"""
    
    def __init__(self, name: str, base_path: Optional[str] = None):
        """Initialize registry with name and optional base path"""
        self.name = name
        self.base_path = Path(base_path) if base_path else None
        self.items: Dict[str, Any] = {}
        self.logger = get_logger(f"{name}_registry")
        self._initialized = False
        
    @abstractmethod
    async def load_items(self) -> None:
        """Load items into registry"""
        pass
        
    @abstractmethod
    async def validate_item(self, item: Any) -> bool:
        """Validate an item before registration"""
        pass
        
    async def register_item(self, name: str, item: Any) -> None:
        """Register an item if valid"""
        try:
            if await self.validate_item(item):
                self.items[name.lower()] = item
                self.logger.debug(f"✓ Registered {name}")
            else:
                raise ValueError(f"Invalid item: {name}")
        except Exception as e:
            self.logger.error(f"Error registering {name}: {str(e)}")
            raise
            
    def get_item(self, name: str) -> Optional[Any]:
        """Get an item by name"""
        return self.items.get(name.lower())
        
    def list_items(self) -> Dict[str, Any]:
        """Get all registered items"""
        return self.items.copy()
        
    @property
    def initialized(self) -> bool:
        """Check if registry is initialized"""
        return self._initialized
        
    async def initialize(self) -> None:
        """Initialize the registry"""
        if self._initialized:
            self.logger.warning(f"{self.name} registry already initialized")
            return
            
        try:
            await self.load_items()
            self._initialized = True
            self.logger.info(f"{self.name} registry initialization complete")
        except Exception as e:
            self.logger.error(f"Failed to initialize {self.name} registry: {str(e)}")
            raise
            
    def _log_registration_summary(self) -> None:
        """Log summary of registered items"""
        self.logger.debug(f"\n=== {self.name} Registry Summary ===")
        self.logger.debug(f"Total items: {len(self.items)}")
        self.logger.debug("Registered items:")
        for item_name in self.items:
            self.logger.debug(f"  - {item_name}")
            
    def __contains__(self, name: str) -> bool:
        """Check if an item exists in the registry"""
        return name.lower() in self.items
        
    def __len__(self) -> int:
        """Get number of registered items"""
        return len(self.items) 