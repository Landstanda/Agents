from typing import Dict, Any, Optional, List
import logging
import yaml
from pathlib import Path
import importlib
import inspect

logger = logging.getLogger(__name__)

class Agent:
    """
    Executes services using available tools.
    Follows service instructions to complete tasks.
    """
    
    def __init__(self, tools_path: str = "src/tools"):
        self.tools_path = Path(tools_path)
        self.tools = {}
        self.is_busy = False
        self.current_service = None
        self.load_tools()
        
    def load_tools(self):
        """Load all available tools from the tools directory."""
        try:
            # Get all Python files in tools directory
            tool_files = list(self.tools_path.glob("*.py"))
            logger.debug(f"Found tool files: {[f.name for f in tool_files]}")
            
            for file in tool_files:
                if file.stem in ['__init__', 'agent']:
                    continue
                    
                try:
                    if str(self.tools_path).startswith("/tmp"):
                        # For test environment, load directly from file
                        logger.debug(f"Loading test tool from {file}")
                        with open(file, 'r') as f:
                            code = compile(f.read(), file.name, 'exec')
                            namespace = {}
                            exec(code, namespace)
                            logger.debug(f"Namespace contents: {list(namespace.keys())}")
                            for name, obj in namespace.items():
                                if inspect.isclass(obj):
                                    logger.debug(f"Found class {name}")
                                    # Use file stem as tool name for consistency
                                    self.tools[file.stem.lower()] = obj
                    else:
                        # For production, use importlib
                        module_path = f"tools.{file.stem}"
                        logger.debug(f"Loading production tool from {module_path}")
                        module = importlib.import_module(module_path)
                        
                        # Find classes in the module
                        for name, obj in inspect.getmembers(module):
                            if inspect.isclass(obj) and obj.__module__ == module_path:
                                logger.debug(f"Found class {name}")
                                # Use file stem as tool name for consistency
                                self.tools[file.stem.lower()] = obj
                            
                except Exception as e:
                    logger.error(f"Error loading tool {file.name}: {str(e)}")
                    
            logger.debug(f"Loaded tools: {list(self.tools.keys())}")
                    
        except Exception as e:
            logger.error(f"Error loading tools: {str(e)}")
    
    async def execute_service(self, service: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a service with the given context.
        
        Args:
            service: Service definition including steps and requirements
            context: Execution context with entities and user info
            
        Returns:
            Dict containing execution results
        """
        if self.is_busy:
            return {
                'status': 'error',
                'error': 'Agent is busy with another service'
            }
            
        try:
            self.is_busy = True
            self.current_service = service
            
            # Validate service format
            if not isinstance(service, dict) or 'steps' not in service:
                raise ValueError("Invalid service format")
                
            results = []
            
            # Execute each step in sequence
            for step in service['steps']:
                step_result = await self._execute_step(step, context)
                results.append(step_result)
                
                if step_result['status'] == 'error':
                    return {
                        'status': 'error',
                        'error': step_result['error'],
                        'partial_results': results
                    }
                    
            # Check success criteria
            success = self._check_success_criteria(service, results)
            
            return {
                'status': 'success' if success else 'partial',
                'results': results,
                'success_criteria_met': success
            }
            
        except Exception as e:
            logger.error(f"Error executing service: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
        finally:
            self.is_busy = False
            self.current_service = None
    
    async def _execute_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single step in the service."""
        try:
            if not isinstance(step, dict):
                raise ValueError("Invalid step format")
                
            tool_name = step.get('tool', '').lower().replace('-', '_')
            action = step.get('action')
            params = step.get('params', {})
            
            if not tool_name or not action:
                raise ValueError("Step missing tool or action")
                
            # Get the tool class
            tool_class = self.tools.get(tool_name)
            if not tool_class:
                raise ValueError(f"Tool not found: {tool_name}")
                
            # Create tool instance
            tool = tool_class()
            
            # Get the action method
            action_method = getattr(tool, action, None)
            if not action_method:
                raise ValueError(f"Action not found: {action}")
                
            # Replace parameter templates with context values
            processed_params = {}
            for key, value in params.items():
                if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                    param_name = value[1:-1]
                    if param_name in context:
                        processed_params[key] = context[param_name]
                    else:
                        raise ValueError(f"Missing context value: {param_name}")
                else:
                    processed_params[key] = value
                    
            # Execute the action
            result = await action_method(**processed_params)
            
            return {
                'status': 'success',
                'tool': tool_name,
                'action': action,
                'result': result
            }
            
        except Exception as e:
            logger.error(f"Error executing step: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _check_success_criteria(self, service: Dict[str, Any], results: List[Dict[str, Any]]) -> bool:
        """Check if all success criteria are met."""
        criteria = service.get('success_criteria', [])
        if not criteria:
            return True
            
        # Convert results to a simple format for checking
        result_data = {
            result['tool'] + '.' + result['action']: result['result']
            for result in results
            if result['status'] == 'success'
        }
        
        # Check each criterion
        for criterion in criteria:
            if not self._evaluate_criterion(criterion, result_data):
                return False
                
        return True
    
    def _evaluate_criterion(self, criterion: str, results: Dict[str, Any]) -> bool:
        """Evaluate a single success criterion."""
        try:
            # Simple exact match for now
            return criterion in str(results)
        except Exception as e:
            logger.error(f"Error evaluating criterion: {str(e)}")
            return False 