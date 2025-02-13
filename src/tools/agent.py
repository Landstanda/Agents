<<<<<<< HEAD
from typing import Dict, Any, Optional, List
=======
from typing import Dict, Any, Optional
>>>>>>> main
import logging
import yaml
from pathlib import Path
import importlib
import inspect
<<<<<<< HEAD
=======
from src.utils.flow_logger import FlowLogger
import re
>>>>>>> main

logger = logging.getLogger(__name__)

class Agent:
    """
<<<<<<< HEAD
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
=======
    Executes service instructions based on NLP analysis results.
    Handles execution flow and error management.
    """
    
    def __init__(self, executions_path: str = "src/services/executions.yaml", tools_path: str = "src/tools", flow_logger: Optional[FlowLogger] = None):
        self.executions_path = Path(executions_path)
        self.tools_path = Path(tools_path)
        self.flow_logger = flow_logger or FlowLogger()
        self.executions = self._load_executions()
        self.tools = {}  # Will store initialized tool instances
        self.tool_configs = {}  # Store tool configurations
        
    def _load_executions(self) -> Dict[str, Any]:
        """Load execution instructions."""
        try:
            if not self.executions_path.exists():
                logger.error(f"Executions file not found at {self.executions_path}")
                return {}
                
            with open(self.executions_path, 'r') as f:
                return yaml.safe_load(f) or {}
                
        except Exception as e:
            logger.error(f"Error loading executions: {str(e)}")
            return {}
            
    async def _get_tool(self, tool_name: str):
        """
        Get or initialize a tool instance.
        
        Args:
            tool_name: Name of the tool to load (e.g., 'calendar', 'email')
            
        Returns:
            Initialized tool instance
        """
        try:
            # Return cached tool if available
            if tool_name in self.tools:
                return self.tools[tool_name]
                
            # Import tool module dynamically
            module_path = str(self.tools_path / f"{tool_name}.py")
            if not Path(module_path).exists():
                logger.error(f"Tool module not found: {module_path}")
                raise ValueError(f"Tool not found: {tool_name}")

            # Add tool directory to Python path
            import sys
            if str(self.tools_path) not in sys.path:
                sys.path.insert(0, str(self.tools_path.parent))

            try:
                module = importlib.import_module(f"tools.{tool_name}")
            except ImportError as e:
                logger.error(f"Error importing tool module: {str(e)}")
                raise ValueError(f"Tool not found: {tool_name}")
                
            # Find the tool class in the module
            tool_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    name.lower().endswith(('tool', 'handler', 'module'))):
                    tool_class = obj
                    break
                    
            if not tool_class:
                raise ValueError(f"No tool class found in module: {module_path}")
                
            # Get tool configuration
            config = self.tool_configs.get(tool_name, {})
            
            # Initialize tool with configuration and flow logger
            tool_instance = tool_class(
                flow_logger=self.flow_logger,
                **config
            )
            
            # Cache the initialized tool
            self.tools[tool_name] = tool_instance
            
            await self.flow_logger.log_event(
                "Agent",
                "tool_initialized",
                {"tool": tool_name}
            )
            
            return tool_instance
            
        except Exception as e:
            logger.error(f"Error initializing tool {tool_name}: {str(e)}")
            await self.flow_logger.log_event(
                "Agent",
                "tool_initialization_error",
                {
                    "tool": tool_name,
                    "error": str(e)
                }
            )
            raise
            
    async def execute_service(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a service based on NLP analysis.
        
        Args:
            analysis: Dict containing:
                - service: Service name to execute
                - entities: Extracted entities for the service
                - user_info: User context information
        """
        service_name = analysis.get("service")
        entities = analysis.get("entities", {})
        user_info = analysis.get("user_info", {})
        
        # Log execution start
        await self.flow_logger.log_event(
            "Agent",
            "execute_service_start",
            {
                "service": service_name,
                "entities": entities
            }
        )
        
        try:
            # Get execution plan
            execution_plan = self.executions.get(service_name)
            if not execution_plan:
                error_msg = f"No execution plan found for service: {service_name}"
                await self.flow_logger.log_event(
                    "Agent",
                    "execute_service_error",
                    {
                        "service": service_name,
                        "error": error_msg
                    }
                )
                return {
                    "text": "An error occurred while processing your request.",
                    "params": {"error_message": error_msg}
                }
            
            # Execute each step
            results = []
            step_context = {}  # Store context between steps
            
            for step in execution_plan["steps"]:
                try:
                    tool_name = step["tool"]
                    action = step["action"]
                    
                    # Get or initialize tool
                    tool = await self._get_tool(tool_name)
                    
                    # Format parameters with entities and previous results
                    params = self._format_params(step["params"], entities, step_context)
                    
                    # Handle loops if specified
                    if "loop" in step:
                        result = await self._execute_loop(tool, action, params, step["loop"])
                    else:
                        # Execute tool action
                        result = await tool.execute(action=action, params=params)
                        
                    # Store result in context for next steps
                    step_context[step["name"]] = result
                    results.append({"step": step, "result": result})
                    
                    # Handle conditional next steps
                    if "condition" in step and not self._evaluate_condition(step["condition"], result):
                        break
                        
                except Exception as step_error:
                    # Log step failure
                    await self.flow_logger.log_event(
                        "Agent",
                        "step_execution_error",
                        {
                            "service": service_name,
                            "step": step,
                            "error": str(step_error)
                        }
                    )
                    
                    # Handle step failure according to configuration
                    if "on_failure" in step:
                        try:
                            result = await self._handle_step_failure(step, step_error)
                            if result:
                                continue
                        except Exception as recovery_error:
                            logger.error(f"Error in failure handling: {str(recovery_error)}")
                    
                    # Send to service maker for troubleshooting
                    await self._report_failure(
                        service_name=service_name,
                        steps_taken=results,
                        failed_step=step,
                        error=str(step_error)
                    )
                    
                    # Return error response using template if available
                    error_template = execution_plan["response_templates"].get("error", "An error occurred: {error_message}")
                    return {
                        "text": error_template.format(error_message=str(step_error)),
                        "params": {"error_message": str(step_error)}
                    }
            
            # Format success response using template
            response = self._format_success_response(
                execution_plan["response_templates"]["success"],
                results,
                entities
            )
            
            # Log successful execution
            await self.flow_logger.log_event(
                "Agent",
                "execute_service_success",
                {
                    "service": service_name,
                    "results": results
                }
            )
            
            return response
            
        except Exception as e:
            # Log service execution failure
            await self.flow_logger.log_event(
                "Agent",
                "execute_service_error",
                {
                    "service": service_name,
                    "error": str(e)
                }
            )
            
            # Return generic error response
            return {
                "text": "An error occurred while processing your request.",
                "params": {"error_message": str(e)}
            }
            
    async def _execute_loop(self, tool, action: str, params: Dict[str, Any], loop_config: Dict[str, Any]) -> Any:
        """Execute an action in a loop until condition is met or max iterations reached."""
        iterations = 0
        max_iterations = loop_config.get("max_iterations", 3)
        
        while iterations < max_iterations:
            result = await tool.execute(action=action, params=params)
            
            if self._evaluate_condition(loop_config["condition"], result):
                return result
                
            iterations += 1
            
            # Handle loop failure
            if iterations == max_iterations and "on_fail" in loop_config:
                return await tool.execute(action=loop_config["on_fail"], params=params)
                
        return result
        
    def _evaluate_condition(self, condition: Dict[str, Any], result: Any) -> bool:
        """Evaluate a condition based on results."""
        # Implement condition evaluation logic
        # This is a placeholder - actual implementation would depend on condition types
        return True
        
    def _format_params(self, params: Dict[str, Any], entities: Dict[str, Any], step_context: Dict[str, Any]) -> Dict[str, Any]:
        """Format parameters with entity and step context values."""
        formatted = {}
        for key, value in params.items():
            if not isinstance(value, str):
                formatted[key] = value
                continue
                
            # Handle step context references
            if "{" in value and "}" in value:
                try:
                    # Handle multiple substitutions in one string
                    result = value
                    for match in re.finditer(r'\{([^}]+)\}', value):
                        placeholder = match.group(1)
                        
                        # Handle step result references
                        if "." in placeholder:
                            parts = placeholder.split(".")
                            if parts[0] == "previous_step" and parts[1] == "result":
                                # Previous step reference
                                field = parts[-1]
                                for step_name, step_data in step_context.items():
                                    if isinstance(step_data, dict) and field in step_data:
                                        result = result.replace(match.group(0), str(step_data[field]))
                                        break
                            else:
                                # Direct step reference
                                step_name = parts[0]
                                if step_name in step_context:
                                    current = step_context[step_name]
                                    for part in parts[1:]:
                                        if isinstance(current, dict) and part in current:
                                            current = current[part]
                                        else:
                                            break
                                    result = result.replace(match.group(0), str(current))
                        
                        # Handle entity references
                        elif placeholder in entities:
                            replacement = entities[placeholder]
                            if isinstance(replacement, (list, dict)):
                                replacement = str(replacement)
                            result = result.replace(match.group(0), str(replacement))
                            
                    formatted[key] = result
                    
                except (IndexError, KeyError) as e:
                    logger.warning(f"Error formatting parameter {key}: {str(e)}")
                    formatted[key] = value
            else:
                formatted[key] = value
                
        return formatted
        
    def _format_success_response(self, template: str, results: list, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Format success response using template and results."""
        # Combine entities and results for template formatting
        params = {}
        
        # Add entities
        for key, value in entities.items():
            if isinstance(value, (str, int, float, bool)):
                params[key] = value
            else:
                params[key] = str(value)  # Convert complex types to string
        
        # Build step context for parameter formatting
        step_context = {}
        for result in results:
            if "name" in result["step"]:
                step_name = result["step"]["name"]
                step_result = result["result"]
                step_context[step_name] = step_result
                
                # Add individual result fields to params
                if isinstance(step_result, dict):
                    for field, value in step_result.items():
                        params[f"{step_name}.{field}"] = value
                params[step_name] = step_result
        
        # Use _format_params to handle complex substitutions
        template_params = {"text": template}
        formatted = self._format_params(template_params, params, step_context)
        
        try:
            text = formatted["text"]
        except KeyError as e:
            logger.error(f"Missing parameter in response template: {str(e)}")
            text = "Request completed successfully."
            
        return {
            "text": text,
            "params": params
        }
        
    async def _handle_step_failure(self, step: Dict[str, Any], error: Exception) -> Optional[Any]:
        """Handle step failure according to configuration."""
        failure_config = step["on_failure"]
        if "max_retries" in failure_config:
            # Implement retry logic
            pass
        if "action" in failure_config:
            # Execute failure handling action
            tool = await self._get_tool(step["tool"])
            return await tool.execute(action=failure_config["action"], params=step["params"])
        return None
        
    async def _report_failure(self, service_name: str, steps_taken: list, failed_step: Dict[str, Any], error: str):
        """Report service failure to ServiceMaker for troubleshooting."""
        try:
            # This would be implemented to communicate with ServiceMaker
            await self.flow_logger.log_event(
                "Agent",
                "failure_report_sent",
                {
                    "service": service_name,
                    "steps_taken": steps_taken,
                    "failed_step": failed_step,
                    "error": error
                }
            )
        except Exception as e:
            logger.error(f"Error reporting failure to ServiceMaker: {str(e)}")
>>>>>>> main
