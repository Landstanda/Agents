from typing import Dict, Any, Optional, Type
import importlib
import inspect
from pathlib import Path
from src.core.module_interface import BaseModule
from src.utils.logging import get_logger
from src.core.registry.base_registry import BaseRegistry

class ToolRegistry(BaseRegistry):
    """Manages tool modules and their validation"""
    
    def __init__(self, tools_path: str = "src/modules"):
        super().__init__(name="tool", base_path=tools_path)
        self.workspace_root = Path("/home/jeff/Agents")  # TODO: Make configurable
        
    async def load_items(self) -> None:
        """Load all available tools from the modules directory"""
        try:
            if not self.base_path.exists():
                self.logger.warning(f"Tools directory not found: {self.base_path}")
                self._initialized = True  # Still mark as initialized even if directory doesn't exist
                return
                
            # Get all Python files in the tools directory
            for file_path in self.base_path.glob("*.py"):
                if file_path.name == "__init__.py":
                    continue
                    
                try:
                    # Convert path to module format
                    module_name = file_path.stem
                    module_path = str(file_path.parent).replace("/", ".")
                    
                    self.logger.debug(f"Loading module: {module_path}.{module_name}")
                    
                    # Import the module
                    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
                    if spec is None or spec.loader is None:
                        self.logger.error(f"Failed to load spec for {file_path}")
                        continue
                        
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Find tool class in module
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and obj.__module__ == module.__name__:
                            # Validate and register the tool
                            if await self.validate_item(obj):
                                # Use file name as tool name
                                tool_name = file_path.stem.lower()
                                await self.register_item(tool_name, obj)
                                break
                            
                except Exception as e:
                    self.logger.error(f"Error loading tool {file_path.name}: {str(e)}")
                    continue
                    
            self._log_registration_summary()
            self._initialized = True  # Mark as initialized after loading all tools
            
        except Exception as e:
            self.logger.error(f"Error loading tools: {str(e)}")
            raise
            
    async def validate_item(self, tool_class: Type) -> bool:
        """Validate that a class is a proper tool implementation"""
        try:
            self.logger.debug(f"Validating tool class: {tool_class.__name__}")
            
            # Check if it's a class
            if not inspect.isclass(tool_class):
                self.logger.error(f"{tool_class} is not a class")
                return False
                
            # Check if it inherits from BaseModule
            if not issubclass(tool_class, BaseModule) or tool_class is BaseModule:
                self.logger.error(f"{tool_class.__name__} is not a valid tool class")
                return False
                
            # Check if it has capabilities property
            if not hasattr(tool_class, "capabilities") or not tool_class.capabilities:
                self.logger.error(f"{tool_class.__name__} does not have capabilities property")
                return False
                
            # Check if it has execute method
            if not hasattr(tool_class, "execute"):
                self.logger.error(f"{tool_class.__name__} does not have execute method")
                return False
                
            # Get the execute method
            execute_method = getattr(tool_class, "execute")
            
            # Check if execute is async
            if not any([
                inspect.iscoroutinefunction(execute_method),
                inspect.iscoroutinefunction(getattr(execute_method, '__func__', None)),
                hasattr(execute_method, '__await__')
            ]):
                self.logger.error(f"{tool_class.__name__}.execute is not an async method")
                return False
                
            self.logger.debug(f"✓ {tool_class.__name__} is a valid tool class")
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating tool class: {str(e)}")
            return False 