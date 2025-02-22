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
from asyncio import Lock
import json
import os

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
        self._busy_lock = Lock()  # Add async lock
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
    
    def _safe_json_serialize(self, obj: Any) -> Any:
        """Safely serialize objects to JSON, handling non-serializable types."""
        if isinstance(obj, bool):
            return obj  # Preserve boolean values
        elif hasattr(obj, '__dict__'):
            return str(obj)
        elif isinstance(obj, (list, tuple)):
            return [self._safe_json_serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._safe_json_serialize(v) for k, v in obj.items()}
        elif isinstance(obj, (int, float, bool)):
            return obj  # Preserve numeric types too
        return str(obj)

    async def execute_service(self, ticket: Ticket) -> Dict[str, Any]:
        """Execute a service with the given ticket."""
        logger.debug(f"\n{'='*50}\nStarting service execution for ticket {ticket.ticket_id}")
        logger.debug(f"Service: {ticket.service}")
        logger.debug(f"Execution plan: {json.dumps(ticket.execution_plan, indent=2)}")
        
        start_time = datetime.now()
        
        # Use async lock to check and set busy state
        async with self._busy_lock:
            if self.is_busy:
                logger.warning("⚠️ Agent is busy with another service")
                ticket.update_status(TicketStatus.ERROR)
                ticket.add_error("Agent is busy with another service", "execution_error")
                return {'status': 'error', 'error': 'Agent is busy with another service'}
            self.is_busy = True
            logger.debug("Agent marked as busy")
        
        try:
            # Load service definitions
            logger.debug("Loading service definitions...")
            elapsed_time = (datetime.now() - start_time).total_seconds()
            logger.debug(f"Elapsed time before loading services: {elapsed_time:.2f} seconds")
            
            services = await self._load_service_definitions()
            if not services:
                error_msg = "No service definitions found"
                logger.error(f"❌ {error_msg}")
                ticket.add_error(error_msg, "service_definition_error")
                return {'status': 'error', 'error': error_msg}
            
            # Get service definition for the requested service
            service_def = services.get(ticket.service)
            if not service_def:
                error_msg = f"Service '{ticket.service}' not found in definitions"
                logger.error(f"❌ {error_msg}")
                ticket.add_error(error_msg, "service_not_found")
                return {'status': 'error', 'error': error_msg}
            
            logger.debug(f"Service '{ticket.service}' found in definitions")
            
            # Validate required entities
            missing_entities = self._validate_required_entities(service_def, ticket.entities)
            if missing_entities:
                error_msg = f"Missing required entities: {', '.join(missing_entities)}"
                logger.error(f"❌ {error_msg}")
                ticket.update_status(TicketStatus.WAITING_INPUT)
                ticket.missing_entities = missing_entities
                return {'status': 'error', 'error': error_msg, 'missing_entities': missing_entities}
            
            # Map execution plan steps to service definition steps
            execution_steps = self._map_execution_steps(ticket.execution_plan, service_def)
            if not execution_steps:
                error_msg = "Failed to map execution steps to service definition"
                logger.error(f"❌ {error_msg}")
                ticket.add_error(error_msg, "step_mapping_error")
                return {'status': 'error', 'error': error_msg}
            
            # Initialize execution state
            results = []
            current_step = None
            
            # Execute steps according to service definition flow
            while True:
                elapsed_time = (datetime.now() - start_time).total_seconds()
                logger.debug(f"Elapsed time: {elapsed_time:.2f} seconds")
                
                if elapsed_time > 25:  # Assuming 30 second timeout
                    logger.error("⚠️ Approaching timeout limit!")
                
                # Get next step based on current state and conditions
                next_step = self._get_next_step(current_step, execution_steps, results)
                if not next_step:
                    logger.debug("✓ All steps completed")
                    break
                
                logger.debug(f"\n--- Executing Step: {next_step['name']} ---")
                logger.debug(f"Tool: {next_step.get('tool')}")
                logger.debug(f"Action: {next_step.get('action')}")
                logger.debug(f"Params: {json.dumps(next_step.get('params', {}), indent=2)}")
                
                # Execute step with retry logic from service definition
                result = await self._execute_step_with_retry(next_step, ticket, service_def)
                
                # Process step result
                if result['status'] == 'success':
                    logger.debug(f"✓ Step completed successfully")
                    # Safely log the result
                    safe_result = self._safe_json_serialize(result.get('result', {}))
                    logger.debug(f"Result: {json.dumps(safe_result, indent=2)}")
                    results.append(result)
                    
                    # Store step result in ticket
                    ticket.store_step_result(next_step.get('step_number'), result)
                    
                    # Check success conditions and determine next step
                    next_action = self._evaluate_success_conditions(next_step, result, service_def)
                    if next_action.get('complete'):
                        break
                    current_step = next_action.get('next_step')
                    
                else:
                    # Handle error according to service definition
                    error_action = self._handle_step_error(next_step, result, service_def)
                    if error_action.get('retry'):
                        continue
                    if error_action.get('alternate_step'):
                        current_step = error_action['alternate_step']
                        continue
                        
                    # Unhandled error
                    error_msg = f"Step failed: {result['error']}"
                    logger.error(f"❌ {error_msg}")
                    ticket.add_error(error_msg, "step_execution_error")
                    return {
                        'status': 'error',
                        'error': error_msg,
                        'step': next_step.get('name'),
                        'partial_results': results
                    }
                
            # Verify all success criteria are met
            if not self._check_success_criteria(service_def, results):
                error_msg = "Not all success criteria were met"
                logger.error(f"❌ {error_msg}")
                ticket.add_error(error_msg, "success_criteria_error")
                return {'status': 'error', 'error': error_msg, 'partial_results': results}
            
            # All steps completed successfully
            logger.debug("✓ Service execution completed successfully")
            ticket.update_status(TicketStatus.COMPLETED)
            ticket.execution_results = results
            
            return {
                'status': 'success',
                'results': results
            }
            
        except Exception as e:
            logger.error(f"❌ Error executing service: {str(e)}")
            ticket.update_status(TicketStatus.ERROR)
            ticket.add_error(str(e), "execution_error")
            return {'status': 'error', 'error': str(e)}
            
        finally:
            # Release busy state with lock protection
            async with self._busy_lock:
                self.is_busy = False
                logger.debug("Agent released busy state")
    
    def _validate_required_entities(self, service_def: Dict[str, Any], entities: Dict[str, Any]) -> List[str]:
        """Validate that all required entities are present."""
        required = service_def.get('required_entities', [])
        missing = []
        for entity in required:
            if entity not in entities:
                missing.append(entity)
        return missing

    def _map_execution_steps(self, execution_plan: List[Dict[str, Any]], service_def: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Map execution plan steps to service definition steps."""
        service_steps = service_def.get('steps', [])
        mapped_steps = []
        
        # For schedule_meeting service, we know we need authentication first
        if service_def.get('name') == 'Schedule Meeting':
            # Map the steps in the order defined in service definition
            for service_step in service_steps:
                step = {
                    **service_step,
                    'step_number': len(mapped_steps) + 1,
                    'params': self._merge_parameters(
                        service_step.get('params', {}),
                        execution_plan[0].get('required_params', {}),
                        execution_plan[0].get('optional_params', {})
                    )
                }
                mapped_steps.append(step)
        else:
            # For other services, try to match by description/name
            for plan_step in execution_plan:
                # Find matching service step
                service_step = next(
                    (step for step in service_steps if self._steps_match(step['name'], plan_step['description'])),
                    None
                )
                
                if service_step:
                    # Merge plan parameters with service step definition
                    step = {
                        **service_step,
                        'step_number': plan_step['step_number'],
                        'params': self._merge_parameters(
                            service_step.get('params', {}),
                            plan_step.get('required_params', {}),
                            plan_step.get('optional_params', {})
                        )
                    }
                    mapped_steps.append(step)
                
        return mapped_steps

    def _steps_match(self, service_name: str, plan_description: str) -> bool:
        """Check if a service step name matches a plan step description."""
        # Convert both to lowercase and remove common words
        service_words = set(service_name.lower().split())
        plan_words = set(plan_description.lower().split())
        
        # Remove common words that don't help with matching
        common_words = {'a', 'an', 'the', 'with', 'to', 'for', 'in', 'on', 'at'}
        service_words = service_words - common_words
        plan_words = plan_words - common_words
        
        # Check if there's significant word overlap
        return bool(service_words & plan_words)

    def _merge_parameters(self, step_params: Dict[str, Any], required_params: Dict[str, Any], optional_params: Dict[str, Any]) -> Dict[str, Any]:
        """Merge parameters from execution plan with service step parameters."""
        merged = {}
        
        # Start with service step params as template
        for param_name, param_template in step_params.items():
            if isinstance(param_template, str) and '{' in param_template and '}' in param_template:
                # Extract variable name from template
                var_name = param_template.strip('{}')
                # Look for value in required or optional params
                if var_name in required_params:
                    merged[param_name] = required_params[var_name]
                elif var_name in optional_params:
                    merged[param_name] = optional_params[var_name]
                else:
                    # Keep template if no value found
                    merged[param_name] = param_template
            else:
                # Keep static values
                merged[param_name] = param_template
                
        return merged

    def _get_next_step(self, current_step: Optional[Dict[str, Any]], steps: List[Dict[str, Any]], results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Determine the next step to execute based on current state and conditions."""
        if not current_step:
            # First step
            return steps[0] if steps else None
            
        # Find current step in sequence
        current_idx = next(
            (i for i, step in enumerate(steps) if step.get('name') == current_step.get('name')),
            -1
        )
        
        if current_idx >= 0 and current_idx + 1 < len(steps):
            return steps[current_idx + 1]
            
        return None

    def _evaluate_success_conditions(self, step: Dict[str, Any], result: Dict[str, Any], service_def: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate success conditions and determine next action."""
        logger.debug(f"\nEvaluating success conditions for step: {step['name']}")
        
        # Create a safe copy of the result for logging
        safe_result = {
            'status': result.get('status'),
            'success': True if result.get('status') == 'success' else False
        }
        if 'result' in result:
            safe_result['result'] = self._safe_json_serialize(result['result'])
        logger.debug(f"Full result (safe): {json.dumps(safe_result, indent=2)}")
        
        on_success = step.get('on_success', [])
        logger.debug(f"Success conditions: {json.dumps(on_success, indent=2)}")
        
        for condition in on_success:
            logger.debug(f"\nChecking condition: {condition.get('condition')}")
            # Create response object that includes both top-level and nested results
            response = {
                'success': True if result.get('status') == 'success' else False
            }
            if 'result' in result:
                response.update(self._safe_json_serialize(result['result']))
            logger.debug(f"Response for condition: {json.dumps(response, indent=2)}")
            
            if self._evaluate_condition(condition.get('condition', 'True'), response):
                logger.debug(f"✓ Condition passed, next step: {condition.get('next_step')}")
                return {
                    'complete': condition.get('next_step') == 'complete',
                    'next_step': condition.get('next_step')
                }
            else:
                logger.debug("✗ Condition failed")
                
        # If no conditions matched
        logger.debug("No success conditions matched")
        return {'complete': False, 'next_step': None}

    def _handle_step_error(self, step: Dict[str, Any], error_result: Dict[str, Any], service_def: Dict[str, Any]) -> Dict[str, Any]:
        """Handle step error according to service definition."""
        on_error = step.get('on_error', [])
        error_type = self._categorize_error(error_result.get('error', ''))
        
        for error_handler in on_error:
            if error_handler.get('condition'):
                if self._evaluate_condition(error_handler['condition'], {'error': {'type': error_type}}):
                    return {
                        'retry': error_handler.get('action') == 'retry',
                        'alternate_step': error_handler.get('next_step')
                    }
            elif error_handler.get('action') == 'retry':
                return {'retry': True}
                
        # Default to no retry
        return {'retry': False}
    
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

    async def _execute_step_with_retry(self, step: Dict[str, Any], ticket: Ticket, service_def: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single step with retry logic from service definition."""
        max_attempts = service_def.get('error_handling', {}).get('retry_count', 3)
        delay_seconds = service_def.get('error_handling', {}).get('delay_seconds', 5)
        
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                result = await self._execute_step(step, ticket.entities)
                
                if result['status'] == 'success':
                    return result
                
                if attempt < max_attempts:
                    logger.warning(f"Step {step.get('name')} failed, attempt {attempt}/{max_attempts}")
                    await asyncio.sleep(delay_seconds)
                    continue
                
                return result
                
            except Exception as e:
                if attempt < max_attempts:
                    logger.error(f"Step {step.get('name')} failed with error: {str(e)}")
                    await asyncio.sleep(delay_seconds)
                    continue
                return {
                    'status': 'error',
                    'error': str(e),
                    'tool': step.get('tool', ''),
                    'action': step.get('action', '')
                }
        
        return {
            'status': 'error',
            'error': f'Step {step.get("name")} failed after {max_attempts} attempts',
            'tool': step.get('tool', ''),
            'action': step.get('action', '')
        }

    async def _execute_step(self, step: Dict[str, Any], entities: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single step using the appropriate tool."""
        try:
            tool_name = step.get('tool', '').lower()
            action = step.get('action', '')
            params = step.get('params', {})
            
            # Get tool class and instantiate it
            tool_class = self.tools.get(tool_name)
            if not tool_class:
                error_msg = f'Tool {tool_name} not found'
                logger.error(f"❌ {error_msg}")
                return {
                    'status': 'error',
                    'error': error_msg,
                    'tool': tool_name,
                    'action': action
                }
                
            # Create instance of the tool
            try:
                # Initialize tool with any required parameters
                if tool_name == 'google_auth':
                    # For GoogleAuthModule, we need to ensure the token directory exists
                    token_dir = os.path.expanduser('~/.auth_tokens')
                    if not os.path.exists(token_dir):
                        os.makedirs(token_dir, mode=0o700)  # Secure permissions
                
                tool_instance = tool_class()
                
                # Process parameters with entity values
                processed_params = self._process_params(params, entities)
                
                # Execute the action
                result = await tool_instance.execute(processed_params)
                
                # Log the result safely
                safe_result = self._safe_json_serialize(result)
                logger.debug(f"Step result: {json.dumps(safe_result, indent=2)}")
                
                return {
                    'status': 'success',
                    'result': result,
                    'tool': tool_name,
                    'action': action
                }
            except TypeError as e:
                error_msg = f'Error instantiating tool {tool_name}: {str(e)}'
                logger.error(f"❌ {error_msg}")
                return {
                    'status': 'error',
                    'error': error_msg,
                    'tool': tool_name,
                    'action': action
                }
            except Exception as e:
                error_msg = f'Error executing step: {str(e)}'
                logger.error(f"❌ {error_msg}")
                return {
                    'status': 'error',
                    'error': error_msg,
                    'tool': tool_name,
                    'action': action
                }
                
        except Exception as e:
            error_msg = f'Error in _execute_step: {str(e)}'
            logger.error(f"❌ {error_msg}")
            return {
                'status': 'error',
                'error': error_msg,
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
            logger.debug(f"Evaluating condition: {condition}")
            
            # Create a safe copy of the result for evaluation
            safe_result = {}
            if isinstance(result, dict):
                for key, value in result.items():
                    if key == 'success':
                        safe_result[key] = bool(value)  # Ensure success is a boolean
                    elif key == 'credentials':
                        safe_result[key] = bool(value)  # Just check if credentials exist
                    else:
                        safe_result[key] = self._safe_json_serialize(value)
            
            # Create a namespace with the safe result
            namespace = {'response': safe_result}
            logger.debug(f"Namespace for evaluation: {json.dumps(namespace, indent=2)}")
            
            eval_result = eval(condition, {"__builtins__": {}}, namespace)
            logger.debug(f"Evaluation result: {eval_result}")
            return bool(eval_result)
            
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

    async def _load_service_definitions(self) -> Dict[str, Any]:
        """Load and validate service definitions."""
        try:
            if not self.services_path.exists():
                raise FileNotFoundError(f"Services file not found: {self.services_path}")
                
            with open(self.services_path, 'r') as f:
                services = yaml.safe_load(f)
                
            # Validate service definitions
            for service_name, service_def in services.items():
                if not self._validate_service_definition(service_def):
                    raise ValueError(f"Invalid service definition: {service_name}")
                    
            return services
        except Exception as e:
            logger.error(f"Error loading service definitions: {str(e)}")
            raise
            
    def _validate_service_definition(self, service_def: Dict[str, Any]) -> bool:
        """Validate a service definition structure."""
        required_fields = {
            'name': str,
            'steps': list,
            'success_criteria': list
        }
        
        try:
            # Check required fields and types
            for field, field_type in required_fields.items():
                if field not in service_def:
                    logger.error(f"Missing required field: {field}")
                    return False
                if not isinstance(service_def[field], field_type):
                    logger.error(f"Invalid type for {field}: expected {field_type}")
                    return False
            
            # Validate steps
            for step in service_def['steps']:
                if not all(k in step for k in ['name', 'tool', 'action']):
                    logger.error("Invalid step structure")
                    return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating service definition: {str(e)}")
            return False
