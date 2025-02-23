from typing import Dict, Any, Optional, List, Type
import logging
import yaml
from pathlib import Path
import importlib
import inspect
from src.utils.flow_logger import FlowLogger
import re
from src.models import Ticket, TicketStatus
from src.core.module_interface import BaseModule, ModuleResponse
from src.core.success_evaluator import SuccessEvaluator
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
        self.tools: Dict[str, Type[BaseModule]] = {}
        self._busy_lock = Lock()  # Add async lock
        self.is_busy = False
        self.current_service = None
        self.flow_logger = flow_logger or FlowLogger()
        self.success_evaluator = SuccessEvaluator()
        
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
            logger.debug(f"\n=== Loading Services ===")
            logger.debug(f"Services path: {self.services_path}")
            logger.debug(f"Path exists: {self.services_path.exists()}")
            
            if not self.services_path.exists():
                logger.warning(f"Services file not found at {self.services_path}")
                return
                
            with open(self.services_path, 'r') as f:
                # Read and log raw content
                content = f.read()
                logger.debug(f"Raw file content (first 500 chars):\n{content[:500]}...")
                
                # Reset file pointer and parse YAML
                f.seek(0)
                self.services = yaml.safe_load(f)
                
                if self.services is None:
                    logger.error("YAML file loaded as None")
                    raise ValueError("YAML file loaded as None")
                    
                logger.debug(f"Loaded services structure: {list(self.services.keys())}")
                logger.info(f"Loaded {len(self.services)} services")
                
                await self.flow_logger.log_event(
                    "Agent",
                    "services_loaded",
                    {"services_count": len(self.services)}
                )
                
        except yaml.YAMLError as e:
            error_msg = str(e)
            if hasattr(e, 'problem_mark'):
                mark = e.problem_mark
                lines = content.split('\n')
                start = max(0, mark.line - 2)
                end = min(len(lines), mark.line + 3)
                context = "\n".join(f"{'>>>' if i == mark.line else '   '} {i+1}: {lines[i]}" 
                                  for i in range(start, end))
                error_msg = f"{error_msg}\nContext:\n{context}"
            
            logger.error(f"YAML parsing error: {error_msg}")
            await self.flow_logger.log_event(
                "Agent",
                "services_load_error",
                {"error": error_msg}
            )
            raise
            
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
        if isinstance(obj, ModuleResponse):
            return obj.to_dict()
        elif hasattr(obj, '__dict__'):
            return str(obj)
        elif isinstance(obj, (list, tuple)):
            return [self._safe_json_serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._safe_json_serialize(v) for k, v in obj.items()}
        elif isinstance(obj, (int, float, bool, str)) or obj is None:
            return obj
        return str(obj)

    async def execute_service(self, ticket: Ticket) -> Dict[str, Any]:
        """Execute a service with the given ticket."""
        logger.info(f"\n=== Starting service execution for ticket {ticket.ticket_id} ===")
        logger.info(f"Service: {ticket.service}")
        
        start_time = datetime.now()
        
        # Use async lock to check and set busy state
        async with self._busy_lock:
            if self.is_busy:
                logger.warning("⚠️ Agent is busy with another service")
                ticket.update_status(TicketStatus.ERROR)
                ticket.add_error("Agent is busy with another service", "execution_error")
                return {'status': 'error', 'error': 'Agent is busy with another service'}
            self.is_busy = True
        
        try:
            # Load service definition
            service_def = self.services.get(ticket.service)
            if not service_def:
                error_msg = f"Service '{ticket.service}' not found in definitions"
                logger.error(f"❌ {error_msg}")
                ticket.add_error(error_msg, "service_not_found")
                return {'status': 'error', 'error': error_msg}
            
            logger.info(f"Found service definition for '{ticket.service}'")
            
            # Validate required entities
            missing_entities = self._validate_required_entities(service_def, ticket.entities)
            if missing_entities:
                error_msg = f"Missing required entities: {', '.join(missing_entities)}"
                logger.error(f"❌ {error_msg}")
                ticket.update_status(TicketStatus.WAITING_INPUT)
                ticket.missing_entities = missing_entities
                return {'status': 'error', 'error': error_msg, 'missing_entities': missing_entities}
            
            # Execute steps in sequence
            current_step = None
            for step in service_def['steps']:
                logger.info(f"\n=== Executing Step: {step['name']} ===")
                
                # Update ticket's current step
                ticket.current_step = step['name']
                
                # Execute step with retry logic if specified
                max_attempts = service_def.get('error_handling', {}).get('retry_count', 3)
                delay_seconds = service_def.get('error_handling', {}).get('delay_seconds', 5)
                
                for attempt in range(max_attempts):
                    try:
                        # Get and execute the tool
                        tool_name = step['tool']
                        tool_class = self.tools.get(tool_name)
                        if not tool_class:
                            error_msg = f"Tool {tool_name} not found"
                            logger.error(f"❌ {error_msg}")
                            ticket.add_error(error_msg, "tool_not_found")
                            return {'status': 'error', 'error': error_msg}
                        
                        # Process parameters
                        params = self._process_params(step.get('params', {}), ticket.entities)
                        
                        # Execute the tool
                        tool = tool_class()
                        result = await tool.execute(ticket, params)
                        
                        if result['success']:
                            # Check success conditions from service definition
                            on_success = step.get('on_success', {})
                            next_step = on_success.get('next_step')
                            
                            if next_step == 'complete':
                                logger.info("✓ Service execution completed successfully")
                                ticket.update_status(TicketStatus.COMPLETED)
                                return {'status': 'success', 'results': ticket.step_results}
                            
                            # Move to next step
                            current_step = next_step
                            break
                        else:
                            # Handle failure
                            on_failure = step.get('on_failure', {})
                            if attempt < max_attempts - 1 and on_failure.get('action') == 'retry':
                                logger.warning(f"Step failed, attempt {attempt + 1}/{max_attempts}")
                                await asyncio.sleep(delay_seconds)
                                continue
                            
                            # Step failed after all retries
                            error_msg = result.get('error', 'Step failed')
                            logger.error(f"❌ {error_msg}")
                            ticket.add_error(error_msg, "step_execution_error")
                            return {
                                'status': 'error',
                                'error': error_msg,
                                'step': step['name']
                            }
                            
                    except Exception as e:
                        if attempt < max_attempts - 1:
                            logger.error(f"Error in step execution: {str(e)}")
                            await asyncio.sleep(delay_seconds)
                            continue
                        error_msg = f"Step failed after {max_attempts} attempts: {str(e)}"
                        logger.error(f"❌ {error_msg}")
                        ticket.add_error(error_msg, "step_execution_error")
                        return {'status': 'error', 'error': error_msg}
            
            # All steps completed successfully
            logger.info("✓ Service execution completed successfully")
            ticket.update_status(TicketStatus.COMPLETED)
            return {
                'status': 'success',
                'results': ticket.step_results
            }
            
        except Exception as e:
            logger.error(f"❌ Error executing service: {str(e)}")
            logger.error("Full error details:", exc_info=True)
            ticket.update_status(TicketStatus.ERROR)
            ticket.add_error(str(e), "execution_error")
            return {'status': 'error', 'error': str(e)}
            
        finally:
            # Release busy state with lock protection
            async with self._busy_lock:
                self.is_busy = False
    
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
        """Evaluate success conditions for a step"""
        try:
            logger.debug("\nEvaluating success conditions for step: " + step['name'])
            logger.debug(f"Full result (safe): {json.dumps(self._safe_json_serialize(result), indent=2)}")
            
            # Get success criteria from step
            success_criteria = step.get('success_criteria', {})
            logger.debug(f"Success criteria: {json.dumps(success_criteria, indent=2)}")
            
            # Convert result to ModuleResponse if needed
            if not isinstance(result, ModuleResponse):
                if isinstance(result, dict):
                    result = ModuleResponse(
                        success=result.get('status') == 'success',
                        data=result.get('result', {}),
                        error=result.get('error'),
                        error_type=result.get('error_type')
                    )
                else:
                    logger.error(f"Invalid result type: {type(result)}")
                    return {
                        'action': 'error',
                        'error': 'Invalid result type'
                    }
                    
            # Evaluate using success evaluator
            evaluation = self.success_evaluator.evaluate(success_criteria, result)
            logger.debug(f"Success condition evaluation result: {evaluation}")
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Error evaluating success conditions: {str(e)}")
            return {
                'action': 'error',
                'error': str(e)
            }
            
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

    async def _execute_step(self, step: Dict[str, Any], entities: Dict[str, Any]) -> ModuleResponse:
        """Execute a single step using the appropriate tool"""
        try:
            tool_name = step.get('tool', '').lower()
            action = step.get('action', '')
            params = step.get('params', {})
            
            # Get tool class and instantiate it
            tool_class = self.tools.get(tool_name)
            if not tool_class:
                error_msg = f'Tool {tool_name} not found'
                logger.error(f"❌ {error_msg}")
                return ModuleResponse(
                    success=False,
                    data={},
                    error=error_msg,
                    error_type='tool_not_found'
                )
                
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
                
                # For authentication results, preserve the success status
                if tool_name == 'google_auth':
                    logger.debug("Processing Google auth result")
                    return ModuleResponse(
                        success=result.get('success'),
                        data=result,
                        error=result.get('error'),
                        error_type=result.get('error_type')
                    )
                
                return ModuleResponse(
                    success=result.get('success'),
                    data=result.get('result', {}),
                    error=result.get('error'),
                    error_type=result.get('error_type')
                )
                
            except TypeError as e:
                error_msg = f'Error instantiating tool {tool_name}: {str(e)}'
                logger.error(f"❌ {error_msg}")
                return ModuleResponse(
                    success=False,
                    data={},
                    error=error_msg,
                    error_type='instantiation_error'
                )
            except Exception as e:
                error_msg = f'Error executing step: {str(e)}'
                logger.error(f"❌ {error_msg}")
                return ModuleResponse(
                    success=False,
                    data={},
                    error=error_msg,
                    error_type='execution_error'
                )
                
        except Exception as e:
            error_msg = f'Error in _execute_step: {str(e)}'
            logger.error(f"❌ {error_msg}")
            return ModuleResponse(
                success=False,
                data={},
                error=error_msg,
                error_type='system_error'
            )
    
    def _check_success_criteria(self, service: Dict[str, Any], results: List[Dict[str, Any]]) -> bool:
        """Check if all service success criteria are met"""
        try:
            # Get overall success criteria
            success_criteria = service.get('success_criteria', {})
            if not success_criteria:
                # If no criteria specified, check if all steps succeeded
                return all(r.get('success', False) for r in results)
                
            # Create a combined result for evaluation
            combined_result = ModuleResponse(
                success=all(r.get('success', False) for r in results),
                data={
                    'results': results,
                    'all_steps_complete': True
                }
            )
            
            # Evaluate using success evaluator
            evaluation = self.success_evaluator.evaluate(success_criteria, combined_result)
            return evaluation.get('success', False)
            
        except Exception as e:
            logger.error(f"Error checking success criteria: {str(e)}")
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
                # Handle both direct and nested results
                if 'result' in result and isinstance(result['result'], dict):
                    inner_result = result['result']
                    safe_result = {
                        'success': bool(inner_result.get('success')),  # Get from inner result
                        'credentials': bool(inner_result.get('credentials')),
                        'scopes': self._safe_json_serialize(inner_result.get('scopes', []))
                    }
                    logger.debug("Using nested result structure")
                else:
                    # Handle direct result structure
                    safe_result = {
                        'success': bool(result.get('success')),
                        'credentials': bool(result.get('credentials')),
                        'scopes': self._safe_json_serialize(result.get('scopes', []))
                    }
                    logger.debug("Using direct result structure")
            
            # Create namespace and evaluate
            namespace = {'response': safe_result}
            eval_result = eval(condition, {"__builtins__": {}}, namespace)
            logger.debug(f"Condition evaluation result: {eval_result}")
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
