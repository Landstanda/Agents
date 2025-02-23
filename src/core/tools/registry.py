from typing import Dict, Any, Optional, Type
import importlib
import inspect
from pathlib import Path
import logging
from src.core.module_interface import BaseModule
from src.utils.logging import get_logger

logger = get_logger(__name__)

class ToolRegistry:
    """Manages tool modules and their validation"""
    
    def __init__(self, tools_path: str = "src/modules"):
        self.tools_path = Path(tools_path)
        self.tools: Dict[str, Type[BaseModule]] = {}
        logger.debug(f"ToolRegistry initialized with path: {tools_path}")
        
    async def load_tools(self) -> None:
        """Load all available tools from the modules directory"""
        try:
            logger.debug(f"Loading tools from: {self.tools_path}")
            
            if not self.tools_path.exists():
                raise FileNotFoundError(f"Tools directory not found: {self.tools_path}")
                
            # Get all Python files in the tools directory
            for file_path in self.tools_path.glob("*.py"):
                if file_path.name == "__init__.py":
                    continue
                    
                try:
                    # Convert path to module format
                    module_path = str(file_path.relative_to(Path("/home/jeff/Agents"))).replace("/", ".")
                    module_path = module_path[:-3]  # Remove .py extension
                    
                    logger.debug(f"Loading module: {module_path}")
                    
                    # Import the module
                    module = importlib.import_module(module_path)
                    
                    # Find tool class in module
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and obj.__module__ == module.__name__:
                            if self.validate_tool(obj):
                                # Use file name as tool name
                                tool_name = file_path.stem.lower()
                                self.tools[tool_name] = obj
                                logger.debug(f"Registered tool: {tool_name}")
                                break
                                
                except Exception as e:
                    logger.error(f"Error loading tool {file_path.name}: {str(e)}")
                    continue
                    
            logger.info(f"Loaded {len(self.tools)} tools successfully")
            
        except Exception as e:
            logger.error(f"Error loading tools: {str(e)}")
            raise
            
    def get_tool(self, name: str) -> Optional[Type[BaseModule]]:
        """Get a tool class by name"""
        return self.tools.get(name.lower())
        
    def validate_tool(self, tool_class: Type) -> bool:
        """
        Validate that a class is a proper tool implementation
        """
        try:
            logger.debug(f"Validating tool class: {tool_class.__name__}")
            
            # Check if it's a class
            if not inspect.isclass(tool_class):
                logger.error(f"{tool_class} is not a class")
                return False
                
            # Check if it inherits from BaseModule
            if not issubclass(tool_class, BaseModule) or tool_class is BaseModule:
                logger.error(f"{tool_class.__name__} is not a valid tool class")
                return False
                
            # Check if it has execute method
            if not hasattr(tool_class, "execute"):
                logger.error(f"{tool_class.__name__} does not have execute method")
                return False
                
            # Get the execute method
            execute_method = tool_class.execute
            
            # Check if execute is async
            if not any([
                inspect.iscoroutinefunction(execute_method),
                inspect.iscoroutinefunction(getattr(execute_method, '__func__', None)),
                hasattr(execute_method, '__await__')
            ]):
                logger.error(f"{tool_class.__name__}.execute is not an async method")
                return False
                
            # Check if it has capabilities property
            if not hasattr(tool_class, "capabilities"):
                logger.error(f"{tool_class.__name__} does not have capabilities property")
                return False
                
            logger.debug(f"Tool class {tool_class.__name__} is valid")
            return True
            
        except Exception as e:
            logger.error(f"Error validating tool class: {str(e)}")
            return False
            
    def register_tool(self, name: str, tool_class: Type[BaseModule]) -> None:
        """
        Register a new tool class
        """
        if self.validate_tool(tool_class):
            self.tools[name.lower()] = tool_class
            logger.debug(f"Registered tool: {name}")
        else:
            raise ValueError(f"Invalid tool class: {tool_class.__name__}") 