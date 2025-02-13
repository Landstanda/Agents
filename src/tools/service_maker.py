from typing import Dict, Any, Optional, List
import logging
import os
import yaml
from pathlib import Path
from openai import AsyncOpenAI
import json
from src.tools.nlp import Ticket, TicketStatus

logger = logging.getLogger(__name__)

class ServiceMaker:
    """
    Creates new services using GPT-4 and available tools.
    Analyzes requests and creates step-by-step instructions
    using available tools to accomplish new tasks.
    """
    
    def __init__(self, 
                 capabilities_path: str = "src/services/capabilities_index.yaml",
                 module_capabilities_path: str = "src/services/module_capabilities.yaml",
                 modules_path: str = "src/modules"):
        """Initialize the service maker with capability information.
        
        Args:
            capabilities_path: Path to capabilities index YAML
            module_capabilities_path: Path to module capabilities YAML
            modules_path: Path to module implementations
        """
        self.capabilities_path = Path(capabilities_path)
        self.module_capabilities_path = Path(module_capabilities_path)
        self.modules_path = Path(modules_path)
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4"
        
        # Load capabilities and module information
        self.capabilities = self._load_capabilities()
        self.module_capabilities = self._load_module_capabilities()
        self.available_modules = self._scan_modules()
        
        # System prompt for GPT-4
        self.system_prompt = """You are an expert system designer.
        Your task is to create services (workflows) that use available tools to accomplish user requests.
        Each service must follow this exact YAML format:

        name: <clear name>
        description: <clear description>
        intent: <main intent>
        triggers:
          - <trigger phrase 1>
          - <trigger phrase 2>
        required_entities:
          - <required entity 1>
          - <required entity 2>
        steps:
          - tool: <tool name>
            action: <action name>
            params:
              param1: value1
              param2: {entity2}
        success_criteria:
          - <criterion 1>
          - <criterion 2>

        Rules:
        1. Use ONLY tools and actions that are available in the module capabilities
        2. Each step must specify tool, action, and params as defined in the module specs
        3. Use {entity} format for required entities in params
        4. All fields are required
        5. Keep it focused and efficient
        6. No markdown code block markers
        7. Valid YAML format
        8. Follow the best practices defined in the capabilities
        """
    
    def _load_capabilities(self) -> Dict[str, Any]:
        """Load and validate the capabilities index."""
        try:
            if not self.capabilities_path.exists():
                raise FileNotFoundError(f"Capabilities file not found: {self.capabilities_path}")
                
            with open(self.capabilities_path, 'r') as f:
                capabilities = yaml.safe_load(f)
                
            # Validate required sections
            required_sections = ['direct_capabilities', 'module_suites', 'task_chains']
            missing_sections = [section for section in required_sections if section not in capabilities]
            
            if missing_sections:
                raise ValueError(f"Missing required sections in capabilities: {missing_sections}")
                
            return capabilities
            
        except Exception as e:
            logger.error(f"Error loading capabilities: {str(e)}")
            raise
    
    def _load_module_capabilities(self) -> Dict[str, Any]:
        """Load and validate the module capabilities."""
        try:
            if not self.module_capabilities_path.exists():
                raise FileNotFoundError(f"Module capabilities file not found: {self.module_capabilities_path}")
                
            with open(self.module_capabilities_path, 'r') as f:
                module_capabilities = yaml.safe_load(f)
                
            # Validate required sections
            if 'modules' not in module_capabilities:
                raise ValueError("No modules section found in module capabilities")
                
            return module_capabilities
            
        except Exception as e:
            logger.error(f"Error loading module capabilities: {str(e)}")
            raise
    
    def _scan_modules(self) -> Dict[str, Any]:
        """Scan for available module implementations."""
        modules = {}
        
        try:
            # Get all Python files in modules directory
            module_files = list(self.modules_path.glob("*.py"))
            
            for file in module_files:
                if file.stem in ['__init__']:
                    continue
                    
                # Verify module is defined in capabilities
                if file.stem in self.module_capabilities.get('modules', {}):
                    modules[file.stem] = {
                        'name': file.stem,
                        'file': str(file),
                        'capabilities': self.module_capabilities['modules'][file.stem]
                    }
                else:
                    logger.warning(f"Module {file.stem} found but not defined in capabilities")
                    
        except Exception as e:
            logger.error(f"Error scanning modules: {str(e)}")
            
        return modules
    
    async def create_service(self, ticket: Ticket) -> Ticket:
        """Create a new service based on the ticket information.

        Args:
            ticket: The ticket containing the request information.

        Returns:
            The updated ticket with service creation results.
        """
        try:
            # Create prompt for GPT
            prompt = self._create_prompt(ticket)
            
            # Get response from GPT
            response = await self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )

            # Extract service YAML from response
            service_yaml = response.choices[0].message.content.strip()
            
            try:
                service = yaml.safe_load(service_yaml)
                if not isinstance(service, dict):
                    raise ValueError("Invalid service format: not a dictionary")
                
                # Validate required fields
                required_fields = ["name", "description", "intent", "triggers", "steps"]
                missing_fields = [field for field in required_fields if field not in service]
                if missing_fields:
                    raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
                
                # Validate steps against module capabilities
                self._validate_service_steps(service)
                
                # Add service to ticket
                ticket.created_services.append(service)
                ticket.status = TicketStatus.EXECUTING
                
                # Save the service
                await self._save_service(service)
                
            except yaml.YAMLError as e:
                error_msg = f"Invalid YAML format: {str(e)}"
                ticket.add_error(error_msg, "service_creation_error")
                ticket.status = TicketStatus.ERROR
                logger.error(error_msg)
            
        except Exception as e:
            error_msg = f"Error creating service: {str(e)}"
            ticket.add_error(error_msg, "service_creation_error")
            ticket.status = TicketStatus.ERROR
            logger.error(error_msg)
        
        return ticket
    
    def _create_prompt(self, ticket: Ticket) -> str:
        """Create a prompt for GPT to generate a new service.

        Args:
            ticket: The ticket containing request and context information.

        Returns:
            A formatted prompt string.
        """
        # Format capabilities context
        capabilities_context = {
            "direct_capabilities": self.capabilities["direct_capabilities"],
            "module_suites": self.capabilities["module_suites"],
            "task_chains": self.capabilities["task_chains"]
        }
        
        # Format module specifications
        module_specs = {
            name: info["capabilities"]
            for name, info in self.module_capabilities["modules"].items()
            if name in self.available_modules
        }
        
        return f"""Create a service to handle this request: {ticket.original_message}

Available capabilities and patterns:
{yaml.dump(capabilities_context, default_flow_style=False)}

Available module specifications:
{yaml.dump(module_specs, default_flow_style=False)}

Previous messages and context:
{self._format_history(ticket)}

Create a service that uses these capabilities to accomplish the request.
The service should follow the system prompt format and:
1. Use only available modules and their defined capabilities
2. Follow established patterns from task_chains where applicable
3. Include all required fields and proper parameter formats
4. Consider best practices and error handling
"""

    def _validate_service_steps(self, service: Dict[str, Any]) -> None:
        """Validate service steps against module capabilities.
        
        Args:
            service: The service definition to validate
            
        Raises:
            ValueError: If any step is invalid
        """
        for step in service.get('steps', []):
            tool_name = step.get('tool')
            action = step.get('action')
            
            if not tool_name or not action:
                raise ValueError(f"Invalid step: missing tool or action")
                
            # Check if tool exists and has the action
            if tool_name not in self.module_capabilities.get('modules', {}):
                raise ValueError(f"Unknown tool: {tool_name}")
                
            tool_ops = self.module_capabilities['modules'][tool_name].get('operations', {})
            if action not in tool_ops:
                raise ValueError(f"Unknown action {action} for tool {tool_name}")
                
            # Validate parameters
            required_params = tool_ops[action].get('required_params', {})
            provided_params = step.get('params', {})
            
            missing_params = [
                param for param in required_params
                if param not in provided_params and not any(
                    isinstance(v, str) and v.startswith('{') and v.endswith('}')
                    for v in provided_params.values()
                )
            ]
            
            if missing_params:
                raise ValueError(f"Missing required parameters for {tool_name}.{action}: {missing_params}")

    def _format_history(self, ticket: Ticket) -> str:
        """Format the ticket's message history for the prompt."""
        history = []
        for msg in ticket.messages:
            source = msg["source"]
            message = msg["message"]
            history.append(f"{source}: {message}")
        return "\n".join(history)
    
    async def _save_service(self, service: Dict[str, Any]) -> None:
        """Save a new service to the services file."""
        try:
            services_file = self.capabilities_path.parent / "services.yaml"
            
            # Create services directory if it doesn't exist
            services_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing services
            services = {}
            if services_file.exists():
                with open(services_file, 'r') as f:
                    services = yaml.safe_load(f) or {}
                    
            # Add new service
            services[service['name']] = service
            
            # Save updated services
            with open(services_file, 'w') as f:
                yaml.safe_dump(services, f, default_flow_style=False)
                
        except Exception as e:
            logger.error(f"Error saving service: {str(e)}")
            raise 