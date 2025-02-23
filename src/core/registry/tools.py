from typing import Dict, Any, Optional, Type
import importlib
import inspect
import sys
import os
from pathlib import Path
from src.core.module_interface import BaseModule
from src.utils.logging import get_logger
import logging

logger = get_logger(__name__)

class ToolRegistry:
    """Manages tool modules and their validation"""
    
    def __init__(self):
        """Initialize an empty tool registry"""
        self.tools = {}
        self.logger = logging.getLogger(__name__)
        self.logger.debug("ToolRegistry initialized")
        self.workspace_root = Path(os.getcwd())
        self.tool_schemas: Dict[str, Dict[str, Any]] = {}
        
        # Configure known tool paths
        self.tool_configs = {
            'test_tool': {
                'module_path': 'src.modules.test_tool',
                'class_name': 'TestTool',
                'schema': {
                    'required_params': ['test_param'],
                    'optional_params': ['optional_param'],
                    'return_schema': {'type': 'object', 'properties': {'success': {'type': 'boolean'}}}
                }
            },
            'google_auth': {
                'module_path': 'src.modules.google_auth',
                'class_name': 'GoogleAuthModule'
            }
            # Add other tools as needed
        }
        
        # Add workspace root to Python path if not already there
        if str(self.workspace_root) not in sys.path:
            sys.path.insert(0, str(self.workspace_root))
            logger.debug(f"Added workspace root to Python path: {self.workspace_root}")
            
    def load_tools(self) -> None:
        """Load tools based on configuration"""
        logger.debug("Loading tools from configuration...")
        
        for tool_name, config in self.tool_configs.items():
            try:
                # Import the module
                module_path = config['module_path']
                class_name = config['class_name']
                
                logger.debug(f"Loading tool {tool_name} from {module_path}")
                
                try:
                    module = importlib.import_module(module_path)
                    logger.debug(f"Successfully imported {module_path}")
                    
                    # Get the tool class
                    if hasattr(module, class_name):
                        tool_class = getattr(module, class_name)
                        
                        # Validate and register the tool
                        if self.validate_tool(tool_class):
                            self.tools[tool_name] = tool_class
                            logger.debug(f"✓ Registered tool: {tool_name}")
                        else:
                            logger.warning(f"Tool class {class_name} failed validation")
                    else:
                        logger.error(f"Class {class_name} not found in {module_path}")
                        
                except ImportError as e:
                    logger.warning(f"Could not import {module_path}: {str(e)}")
                except Exception as e:
                    logger.error(f"Error loading tool {module_path}: {str(e)}")
                    
            except Exception as e:
                logger.error(f"Error processing tool config for {tool_name}: {str(e)}")
                
        logger.info(f"Loaded {len(self.tools)} tools successfully")
        logger.debug(f"Available tools: {list(self.tools.keys())}")

    async def register_tool(self, name: str, tool_class: Type[BaseModule]) -> None:
        """Register a tool class"""
        try:
            # Validate tool class
            if not issubclass(tool_class, BaseModule):
                raise ValueError(f"Tool class must inherit from BaseModule")
                
            # Create instance for validation
            tool = tool_class()
            
            # Check required attributes
            if not hasattr(tool, 'execute'):
                raise ValueError(f"Tool must implement execute method")
            if not hasattr(tool, 'capabilities'):
                raise ValueError(f"Tool must implement capabilities property")
                
            # Store tool class
            self.tools[name] = tool_class
            self.logger.debug(f"Registered tool: {name}")
            
        except Exception as e:
            self.logger.error(f"Failed to register tool {name}: {str(e)}")
            raise

    async def get_tool(self, name: str) -> Optional[Type[BaseModule]]:
        """Get a tool by name"""
        try:
            tool_class = self.tools.get(name)
            if not tool_class:
                self.logger.warning(f"Tool {name} not found")
                return None
            return tool_class
        except Exception as e:
            self.logger.error(f"Error getting tool {name}: {str(e)}")
            return None

    async def validate_tool(self, tool_class: Type[BaseModule], service_def: Dict[str, Any]) -> bool:
        """Validate a tool against service requirements"""
        try:
            # First validate basic requirements
            if not self._validate_basic_requirements(tool_class):
                return False
                
            # Create tool instance
            tool = tool_class()
            
            # Check if tool implements required capabilities
            required_capabilities = set()
            for step in service_def.get('steps', []):
                if step.get('tool') == tool_class.__name__.lower():
                    required_capabilities.update(step.get('required_capabilities', []))
                    
            if not required_capabilities.issubset(set(tool.capabilities)):
                self.logger.warning(f"Tool {tool_class.__name__} missing required capabilities: {required_capabilities - set(tool.capabilities)}")
                return False
                
            # Validate tool schema if defined
            if not self._validate_tool_schema(tool_class):
                return False
                
            # Validate tool against service requirements
            if not self._validate_tool_for_service(tool_class, service_def):
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Tool validation failed: {str(e)}")
            return False

    def _validate_basic_requirements(self, tool_class: Type) -> bool:
        """Validate basic tool requirements"""
        try:
            # Must be a class
            if not inspect.isclass(tool_class):
                logger.debug(f"Not a class: {tool_class}")
                return False
                
            # Must inherit from BaseModule
            if not issubclass(tool_class, BaseModule) or tool_class is BaseModule:
                logger.debug(f"Not a valid tool class: {tool_class.__name__}")
                return False
                
            # Must have execute method
            if not hasattr(tool_class, "execute"):
                logger.debug(f"Missing execute method: {tool_class.__name__}")
                return False
                
            # Execute must be async
            execute_method = tool_class.execute
            if not inspect.iscoroutinefunction(execute_method):
                logger.debug(f"Execute method not async: {tool_class.__name__}")
                return False
                
            # Must have capabilities property
            if not hasattr(tool_class, "capabilities"):
                logger.debug(f"Missing capabilities: {tool_class.__name__}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error in basic validation: {str(e)}")
            return False
            
    def _validate_tool_schema(self, tool_class: Type) -> bool:
        """Validate tool's parameter and return schemas"""
        try:
            # Get tool schema
            tool_name = tool_class.__name__.lower()
            schema = self.tool_schemas.get(tool_name) or self.tool_configs.get(tool_name, {}).get('schema')
            
            if not schema:
                logger.warning(f"No schema defined for tool: {tool_name}")
                return True  # Allow tools without schemas for backward compatibility
                
            # Validate execute method signature
            sig = inspect.signature(tool_class.execute)
            params = sig.parameters
            
            # Check required parameters
            for required_param in schema.get('required_params', []):
                if required_param not in params:
                    logger.debug(f"Missing required parameter {required_param} in {tool_name}")
                    return False
                    
            # Validate return type hints
            return_annotation = sig.return_annotation
            if return_annotation != inspect.Parameter.empty:
                # TODO: Add return type validation against schema
                pass
                
            return True
            
        except Exception as e:
            logger.error(f"Error in schema validation: {str(e)}")
            return False
            
    def _validate_tool_for_service(self, tool_class: Type, service_def: Dict[str, Any]) -> bool:
        """Validate tool against service requirements"""
        try:
            tool_name = tool_class.__name__.lower()
            
            # Check if tool is used in service
            for step in service_def.get('steps', []):
                if step.get('tool', '').lower() == tool_name:
                    # Validate step parameters against tool schema
                    if not self._validate_step_params(step, tool_class):
                        return False
                        
            return True
            
        except Exception as e:
            logger.error(f"Error in service validation: {str(e)}")
            return False
            
    def _validate_step_params(self, step: Dict[str, Any], tool_class: Type) -> bool:
        """Validate step parameters against tool requirements"""
        try:
            params = step.get('params', {})
            tool_name = tool_class.__name__.lower()
            schema = self.tool_schemas.get(tool_name) or self.tool_configs.get(tool_name, {}).get('schema', {})
            
            # Check required parameters
            for required_param in schema.get('required_params', []):
                if required_param not in params:
                    logger.debug(f"Step missing required parameter: {required_param}")
                    return False
                    
            # Validate parameter types if specified
            param_types = schema.get('param_types', {})
            for param_name, param_value in params.items():
                if param_name in param_types:
                    expected_type = param_types[param_name]
                    if not isinstance(param_value, expected_type):
                        logger.debug(f"Invalid type for parameter {param_name}")
                        return False
                        
            return True
            
        except Exception as e:
            logger.error(f"Error in parameter validation: {str(e)}")
            return False 