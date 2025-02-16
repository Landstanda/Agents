from typing import Dict, Any, Optional, List
import logging
import yaml
from pathlib import Path
import importlib
import inspect
from src.utils.flow_logger import FlowLogger
import re
from src.models import Ticket, TicketStatus
from src.core.module_interface import BaseModule
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class Agent:
    """
    Executes services using available tools.
    Follows service instructions to complete tasks.
    """
    
    def __init__(self, services_path: str = "src/services/service_definitions.yaml",
                 tools_path: str = "src/tools",
                 modules_path: str = "src/modules",
                 flow_logger: Optional[FlowLogger] = None):
        """Initialize the Agent with paths to services and tools."""
        workspace_root = Path("/home/jeff/Agents")
        self.services_path = workspace_root / services_path
        self.tools_path = workspace_root / tools_path
        self.modules_path = workspace_root / modules_path
        self.services: Dict[str, Any] = {}
        self.tools: Dict[str, Any] = {}
        self.is_busy = False
        self.current_service = None
        self.flow_logger = flow_logger or FlowLogger()
        
        logger.debug(f"Initializing Agent with paths:")
        logger.debug(f"Services path: {self.services_path}")
        logger.debug(f"Tools path: {self.tools_path}")
        logger.debug(f"Modules path: {self.modules_path}")
        
        # Note: _load_tools and load_services are async and will be called explicitly
        
    async def initialize(self):
        """Initialize the agent asynchronously."""
        await self._load_tools()
        await self.load_services()
        
    async def load_services(self):
        """Load services from the services file."""
        try:
            if not self.services_path.exists():
                logger.warning(f"Services file not found at {self.services_path}")
                return
                
            with open(self.services_path, 'r') as f:
                self.services = yaml.safe_load(f) or {}
                
            logger.info(f"Loaded {len(self.services)} services")
            await self.flow_logger.log_event(
                "Agent",
                "services_loaded",
                {"services_count": len(self.services)}
            )
            
        except Exception as e:
            logger.error(f"Error loading services: {str(e)}")
            await self.flow_logger.log_event(
                "Agent",
                "services_load_error",
                {"error": str(e)}
            )
            raise
        
    async def _load_tools(self):
        """Load all available tools from both tools and modules directories."""
        tool_paths = [self.tools_path, self.modules_path]
        workspace_root = Path("/home/jeff/Agents")
        
        logger.debug("\n=== Loading Tools ===")
        logger.debug(f"Workspace root: {workspace_root}")
        logger.debug(f"Tool paths to search: {[str(p) for p in tool_paths]}")
        
        def validate_module(obj):
            """Validate that a class is a proper module implementation"""
            logger.debug(f"\nValidating module: {obj.__name__ if inspect.isclass(obj) else obj}")
            
            # Check if it's a class
            if not inspect.isclass(obj):
                logger.debug(f"❌ {obj} is not a class")
                return False
                
            # Check if it inherits from BaseModule but is not BaseModule itself
            if not issubclass(obj, BaseModule) or obj is BaseModule:
                logger.debug(f"❌ {obj.__name__} is not a valid module class")
                return False
                
            # Check if it has execute method
            if not hasattr(obj, "execute"):
                logger.debug(f"❌ {obj.__name__} does not have execute method")
                return False
                
            # Get the execute method
            execute_method = obj.execute
            
            # Check if execute is a method and is async
            if not any([
                inspect.iscoroutinefunction(execute_method),  # For async methods
                inspect.iscoroutinefunction(getattr(execute_method, '__func__', None)),  # For bound async methods
                hasattr(execute_method, '__await__')  # For coroutine objects
            ]):
                logger.debug(f"❌ {obj.__name__}.execute is not an async method")
                return False
                
            logger.debug(f"✓ {obj.__name__} is a valid module")
            return True
        
        for tool_path in tool_paths:
            if not tool_path.exists():
                logger.warning(f"Tool path {tool_path} does not exist")
                continue
                
            logger.debug(f"\nSearching in: {tool_path}")
            for file_path in tool_path.glob("*.py"):
                if file_path.name == "__init__.py":
                    continue
                    
                logger.debug(f"\nProcessing file: {file_path}")
                try:
                    # Get the relative path from workspace root
                    rel_path = file_path.relative_to(workspace_root)
                    # Convert to module path format
                    module_path = str(rel_path).replace(".py", "").replace("/", ".")
                    
                    logger.debug(f"  Module path: {module_path}")
                    
                    # Import the module
                    logger.debug(f"  Importing module...")
                    module = importlib.import_module(module_path)
                    logger.debug(f"  Module imported successfully")
                    
                    # Look for tool class in module
                    logger.debug(f"  Searching for tool class...")
                    found_tool = False
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and obj.__module__ == module.__name__:
                            logger.debug(f"    Checking class: {name}")
                            if validate_module(obj):
                                # Use file name as tool name
                                tool_name = file_path.stem.lower()
                                self.tools[tool_name] = obj
                                found_tool = True
                                logger.info(f"✓ Loaded tool: {tool_name} from {module_path}")
                                break
                    
                    if not found_tool:
                        logger.debug(f"  No valid tool class found in {module_path}")
                            
                except Exception as e:
                    logger.error(f"Error loading tool {file_path.name}: {str(e)}")
                    logger.debug(f"Module path attempted: {module_path}")
                    logger.debug("Full error details:", exc_info=True)
        
        logger.debug("\n=== Tool Loading Summary ===")
        logger.debug(f"Total tools loaded: {len(self.tools)}")
        logger.debug("Available tools:")
        for tool_name, tool_class in self.tools.items():
            logger.debug(f"  - {tool_name}: {tool_class.__name__}")
            
        # Log to flow logger
        if self.flow_logger:
            await self.flow_logger.log_event(
                "Agent",
                "tools_loaded",
                {
                    "total_tools": len(self.tools),
                    "available_tools": list(self.tools.keys())
                }
            )
    
    async def execute_service(self, ticket: Ticket) -> Dict[str, Any]:
        """Execute a service with the given ticket."""
        logger.debug(f"\n{'='*50}\nStarting service execution for ticket {ticket.ticket_id}")
        
        if self.is_busy:
            logger.warning("⚠️ Agent is busy with another service")
            ticket.update_status(TicketStatus.ERROR)
            ticket.add_error("Agent is busy with another service", "execution_error")
            return {'status': 'error', 'error': 'Agent is busy with another service'}
        
        try:
            self.is_busy = True
            
            # Load service definitions
            services = await self._load_service_definitions()
            
            # Initialize execution state
            results = []
            
            # Execute steps sequentially
            while True:
                next_step = ticket.get_next_step()
                if not next_step:
                    break  # All steps completed
                
                # Execute step with retry from service definition
                result = await self._execute_step_with_retry(next_step, ticket, services)
                
                # Store result
                ticket.store_step_result(next_step['step_number'], result)
                
                if result['status'] == 'error':
                    return {
                        'status': 'error',
                        'error': result['error'],
                        'partial_results': results
                    }
                
                results.append(result)
            
            # All steps completed successfully
            ticket.update_status(TicketStatus.COMPLETED)
            ticket.execution_results = results
            
            return {
                'status': 'success',
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error executing service: {str(e)}", exc_info=True)
            ticket.update_status(TicketStatus.ERROR)
            ticket.add_error(str(e), "execution_error")
            return {'status': 'error', 'error': str(e)}
            
        finally:
            self.is_busy = False
    
    async def _execute_step_with_retry(self, step: Dict[str, Any], ticket: Ticket, services: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single step with retry logic from service definition."""
        service_def = services.get(step['service_id'], {})
        max_attempts = service_def.get('error_handling', {}).get('retry_count', 3)
        
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                result = await self._execute_step(step, ticket.entities)
                
                if result['status'] == 'success':
                    return result
                
                if attempt < max_attempts:
                    logger.warning(f"Step {step['step_number']} failed, attempt {attempt}/{max_attempts}")
                    await asyncio.sleep(5)  # Simple delay between retries
                    continue
                
                return result
                
            except Exception as e:
                if attempt < max_attempts:
                    logger.error(f"Step {step['step_number']} failed with error: {str(e)}")
                    await asyncio.sleep(5)
                    continue
                return {
                    'status': 'error',
                    'error': str(e),
                    'tool': step.get('tool', ''),
                    'action': step.get('action', '')
                }
        
        return {
            'status': 'error',
            'error': f'Step {step["step_number"]} failed after {max_attempts} attempts',
            'tool': step.get('tool', ''),
            'action': step.get('action', '')
        }
    
    def _categorize_error(self, error: str) -> str:
        """Categorize an error message into a known error type."""
        error = error.lower()
        if 'network' in error or 'connection' in error:
            return 'network_error'
        elif 'rate' in error and 'limit' in error:
            return 'rate_limit'
        elif 'auth' in error or 'unauthorized' in error:
            return 'auth_error'
        elif 'not found' in error:
            return 'not_found'
        else:
            return 'unknown_error'
    
    def _get_fallback_strategy(self, error: str, ticket: Ticket) -> Optional[Dict[str, Any]]:
        """Get appropriate fallback strategy for an error."""
        error_type = self._categorize_error(error)
        for strategy in ticket.fallback_strategies:
            if strategy['condition'] == error_type:
                return strategy
        return None
    
    def _create_alternative_step(self, failed_step: Dict[str, Any], alternative_service: str) -> Dict[str, Any]:
        """Create an alternative step to replace a failed step."""
        return {
            'step_number': failed_step['step_number'],
            'service_id': alternative_service,
            'description': f"Alternative for failed step {failed_step['step_number']}",
            'depends_on': failed_step['depends_on'],
            'required_params': failed_step['required_params'],
            'optional_params': failed_step['optional_params'],
            'retry_config': {
                'max_attempts': 2,
                'delay_seconds': 5,
                'conditions': {'network_error': True, 'rate_limit': True}
            }
        }

    async def _execute_step(self, step: Dict[str, Any], entities: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single step of a service."""
        try:
            tool_name = step.get('tool', '').lower()
            action = step.get('action', '')
            params = step.get('params', {})
            
            # Get tool class and instantiate it
            tool_class = self.tools.get(tool_name)
            if not tool_class:
                return {
                    'status': 'error',
                    'error': f'Tool {tool_name} not found',
                    'tool': tool_name,
                    'action': action
                }
                
            # Create instance of the tool
            try:
                tool_instance = tool_class()
                
                # Process parameters with entity values
                processed_params = self._process_params(params, entities)
                
                # Execute the action
                result = await tool_instance.execute(processed_params)
                return {
                    'status': 'success',
                    'result': result,
                    'tool': tool_name,
                    'action': action
                }
            except TypeError as e:
                logger.error(f"Error instantiating tool {tool_name}: {str(e)}")
                return {
                    'status': 'error',
                    'error': f'Error instantiating tool {tool_name}: {str(e)}',
                    'tool': tool_name,
                    'action': action
                }
            except Exception as e:
                logger.error(f"Error executing step: {str(e)}")
                return {
                    'status': 'error',
                    'error': str(e),
                    'tool': tool_name,
                    'action': action
                }
                
        except Exception as e:
            logger.error(f"Error in _execute_step: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'tool': tool_name if 'tool_name' in locals() else '',
                'action': action if 'action' in locals() else ''
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

    def _format_response(self, execution_plan: Dict[str, Any], results: List[Dict[str, Any]], context: Dict[str, Any]) -> str:
        """Format the execution result into a standardized response.

        Args:
            execution_plan: The execution plan for the service.
            results: The list of results from executing the service.
            context: The context information for the service.

        Returns:
            A formatted string representing the execution result.
        """
        response = []
        
        for step in execution_plan.get('steps', []):
            step_result = next((result for result in results if result['tool'] == step.get('tool', '') and result['action'] == step.get('action', '')), None)
            if step_result:
                response.append(f"{step.get('name', '')}: {step_result['result']}")
        
        return "\n".join(response)

    def _evaluate_condition(self, condition: str, result: Dict[str, Any]) -> bool:
        """Evaluate a condition string against a result."""
        try:
            # Create a namespace with the result
            namespace = {'response': result}
            return eval(condition, {"__builtins__": {}}, namespace)
        except Exception as e:
            logger.error(f"Error evaluating condition: {str(e)}")
            return False

    async def _save_new_service(self, service: Dict[str, Any]) -> None:
        """Save a new service to the services file."""
        try:
            # Ensure parent directory exists
            self.services_path.parent.mkdir(parents=True, exist_ok=True)

            # Update services file
            services = {}
            if self.services_path.exists():
                with open(self.services_path, 'r') as f:
                    services = yaml.safe_load(f) or {}

            services[service['name']] = service

            with open(self.services_path, 'w') as f:
                yaml.safe_dump(services, f, default_flow_style=False)

            logger.info(f"Successfully saved service {service['name']} to file")

        except Exception as e:
            logger.error(f"Error saving new service: {str(e)}")
            raise

    def _process_params(self, params: Dict[str, Any], entities: Dict[str, Any]) -> Dict[str, Any]:
        """Process parameters by replacing template values with entity values."""
        processed_params = {}
        for key, value in params.items():
            if isinstance(value, str):
                logger.debug(f"Processing parameter {key}: {value}")
                try:
                    # Create a context with entities
                    context = {**entities}
                    # Add any helper functions or variables needed
                    context.update({
                        'str': str,
                        'int': int,
                        'float': float,
                        'bool': bool,
                        'len': len,
                        'list': list,
                        'dict': dict,
                        'set': set,
                        'tuple': tuple
                    })
                    
                    # Special handling for date/time parameters
                    if key in ['start_time', 'end_time']:
                        date = entities.get('date', datetime.now().strftime('%Y-%m-%d'))
                        time = entities.get('time', '00:00')
                        
                        # Ensure time is in HH:MM format
                        if ':' not in time:
                            time = f"{time}:00"
                        
                        # If time is in 12-hour format, convert to 24-hour
                        if 'pm' in time.lower() or 'am' in time.lower():
                            try:
                                dt = datetime.strptime(time.strip().upper(), '%I %p')
                                time = dt.strftime('%H:%M')
                            except ValueError:
                                try:
                                    dt = datetime.strptime(time.strip().upper(), '%I:%M %p')
                                    time = dt.strftime('%H:%M')
                                except ValueError:
                                    logger.error(f"Failed to parse time: {time}")
                                    raise ValueError(f"Invalid time format: {time}")
                        
                        # For end_time, add duration if specified
                        if key == 'end_time':
                            try:
                                hours, minutes = time.split(':')
                                # Add 60 minutes for duration
                                new_minutes = int(minutes) + 60
                                if new_minutes >= 60:
                                    hours = str(int(hours) + new_minutes // 60)
                                    minutes = str(new_minutes % 60).zfill(2)
                                else:
                                    minutes = str(new_minutes).zfill(2)
                                time = f"{hours.zfill(2)}:{minutes}"
                            except Exception as e:
                                logger.error(f"Failed to calculate end time: {str(e)}")
                                # Default to 1 hour later if calculation fails
                                hours = str(int(time.split(':')[0]) + 1).zfill(2)
                                time = f"{hours}:{time.split(':')[1]}"
                        
                        # Format as ISO 8601
                        processed_params[key] = f"{date}T{time}:00"
                        logger.debug(f"Processed {key} to: {processed_params[key]}")
                        continue
                    
                    # For other template strings, evaluate each expression separately
                    if '{' in value and '}' in value:
                        result = value
                        # Find all template expressions
                        import re
                        template_vars = re.finditer(r'\{([^}]+)\}', value)
                        for match in template_vars:
                            expr = match.group(1)
                            try:
                                # Evaluate the expression
                                eval_result = eval(expr, {"__builtins__": {}}, context)
                                # Replace in the template
                                result = result.replace(f"{{{expr}}}", str(eval_result))
                            except NameError:
                                if 'location' in expr:
                                    result = result.replace(f"{{{expr}}}", 'Virtual Meeting')
                                elif 'participants' in expr:
                                    result = result.replace(f"{{{expr}}}", '[]')
                                else:
                                    raise ValueError(f"Missing or invalid entity value: {expr}")
                        processed_params[key] = result
                    else:
                        processed_params[key] = value
                    
                except Exception as e:
                    logger.error(f"Failed to process parameter {key}: {str(e)}")
                    raise ValueError(f"Error processing parameter {key}: {str(e)}")
            else:
                processed_params[key] = value
                
        logger.debug(f"Processed parameters: {processed_params}")
        return processed_params
