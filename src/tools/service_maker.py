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
    
    def __init__(self, services_path: str = "src/services/services.yaml", tools_path: str = "src/tools"):
        """Initialize the service maker."""
        self.services_path = Path(services_path)
        self.tools_path = Path(tools_path)
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.tools = self._load_tools()
        self.model = "gpt-4"  # Default to GPT-4 for service creation
        
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
        1. Use ONLY tools and actions that are available
        2. Each step must specify tool, action, and params
        3. Use {entity} format for required entities in params
        4. All fields are required
        5. Keep it focused and efficient
        6. No markdown code block markers
        7. Valid YAML format
        """
    
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
                messages=[{"role": "system", "content": prompt}],
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
                required_fields = ["name", "description", "steps"]
                missing_fields = [field for field in required_fields if field not in service]
                if missing_fields:
                    raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
                
                # Add service to ticket
                ticket.created_services.append(service)
                ticket.status = TicketStatus.EXECUTING
                
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
        tools_desc = json.dumps(self.tools, indent=2)
        return f"""Create a service to handle this request: {ticket.original_message}

Available tools and their capabilities:
{tools_desc}

Previous messages and context:
{self._format_history(ticket)}

Create a service that uses these tools to accomplish the request.
The service should be in YAML format and include:
- name: A unique identifier for the service
- description: A clear description of what the service does
- steps: A list of steps to execute, each with:
  - tool: The tool to use
  - action: The action to perform
  - params: Parameters for the action

Example format:
name: example_service
description: Example service that does X
steps:
  - tool: tool_name
    action: action_name
    params:
      param1: value1
      param2: value2
"""

    def _format_history(self, ticket: Ticket) -> str:
        """Format the ticket's message history for the prompt.

        Args:
            ticket: The ticket containing the message history.

        Returns:
            A formatted string of the message history.
        """
        history = []
        for msg in ticket.messages:
            source = msg["source"]
            message = msg["message"]
            history.append(f"{source}: {message}")
        return "\n".join(history)
    
    async def _save_service(self, service: Dict[str, Any]) -> None:
        """Save a new service to the services file."""
        try:
            # Create services directory if it doesn't exist
            self.services_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing services
            services = {}
            if self.services_path.exists():
                with open(self.services_path, 'r') as f:
                    services = yaml.safe_load(f) or {}
                    
            # Add new service
            services[service['name']] = service
            
            # Save updated services
            with open(self.services_path, 'w') as f:
                yaml.safe_dump(services, f, default_flow_style=False)
                
        except Exception as e:
            logger.error(f"Error saving service: {str(e)}")
            raise
    
    def _load_tools(self) -> Dict[str, Any]:
        """Load available tools and their capabilities."""
        tools = {}
        
        try:
            # Get all Python files in tools directory
            tool_files = list(self.tools_path.glob("*.py"))
            
            for file in tool_files:
                if file.stem in ['__init__', 'service_maker']:
                    continue
                    
                try:
                    # Read the file and extract class docstring
                    with open(file, 'r') as f:
                        content = f.read()
                        
                    # Simple docstring extraction (could be improved)
                    class_doc = None
                    class_lines = []
                    in_class = False
                    
                    for line in content.split('\n'):
                        if line.startswith('class '):
                            in_class = True
                        elif in_class and line.strip().startswith('"""'):
                            class_doc = line.strip().strip('"""')
                            break
                            
                    if class_doc:
                        tools[file.stem] = {
                            'name': file.stem,
                            'description': class_doc,
                            'file': str(file)
                        }
                        
                except Exception as e:
                    logger.error(f"Error loading tool {file.name}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error loading tools: {str(e)}")
            
        return tools 