from typing import Dict, Any, Optional, List
import logging
import os
import yaml
from pathlib import Path
from openai import AsyncOpenAI
import json
<<<<<<< HEAD
=======
import asyncio
from src.utils.flow_logger import FlowLogger
>>>>>>> main

logger = logging.getLogger(__name__)

class ServiceMaker:
    """
<<<<<<< HEAD
    Creates new services using GPT-4 and available tools.
    Analyzes requests and creates step-by-step instructions
    using available tools to accomplish new tasks.
    """
    
    def __init__(self, services_path: str = "src/services/services.yaml", tools_path: str = "src/tools"):
=======
    Creates and manages services.
    Handles service definition, validation, and storage.
    """
    
    def __init__(self, services_path: str = "src/services/services.yaml", tools_path: str = "src/tools", flow_logger: Optional[FlowLogger] = None):
>>>>>>> main
        """Initialize the service maker."""
        self.services_path = Path(services_path)
        self.tools_path = Path(tools_path)
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
<<<<<<< HEAD
        self.tools = self._load_tools()
=======
        self.flow_logger = flow_logger or FlowLogger()
        self.tools = {}
>>>>>>> main
        
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
<<<<<<< HEAD
    
    def _load_tools(self) -> Dict[str, Any]:
=======
        
    @classmethod
    async def create(cls, services_path: str = "src/services/services.yaml", tools_path: str = "src/tools") -> 'ServiceMaker':
        """Create and initialize a ServiceMaker instance."""
        service_maker = cls(services_path, tools_path)
        service_maker.tools = await service_maker._load_tools()
        return service_maker
    
    async def _load_tools(self) -> Dict[str, Any]:
>>>>>>> main
        """Load available tools and their capabilities."""
        tools = {}
        
        try:
            # Get all Python files in tools directory
            tool_files = list(self.tools_path.glob("*.py"))
            
<<<<<<< HEAD
=======
            loaded_tools = []
>>>>>>> main
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
<<<<<<< HEAD
=======
                        loaded_tools.append(file.stem)
>>>>>>> main
                        
                except Exception as e:
                    logger.error(f"Error loading tool {file.name}: {str(e)}")
                    
<<<<<<< HEAD
        except Exception as e:
            logger.error(f"Error loading tools: {str(e)}")
            
        return tools
    
    async def create_service(self, request: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new service to handle a request.
        
        Args:
            request: The user's request
            context: Additional context about the request
            
        Returns:
            Dict containing:
                - status: "success" or "error"
                - service: The created service if successful
                - error: Error message if failed
        """
        try:
            # Create prompt for GPT-4
            tools_desc = json.dumps(self.tools, indent=2)
            user_prompt = f"""
            Create a service to handle this request: {request}
            
            Available tools and their capabilities:
            {tools_desc}
            
            Additional context:
            {json.dumps(context, indent=2)}
            
            Create a service that uses these tools to accomplish the request.
            Follow the format and rules exactly.
            """
            
            # Get GPT-4 response
            response = await self.openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            if not response.choices:
                raise ValueError("No response from GPT-4")
                
            # Get the service YAML
            service_yaml = response.choices[0].message.content.strip()
            
            # Parse and validate the service
            try:
                service = yaml.safe_load(service_yaml)
                
                # Validate required fields
                required_fields = {
                    'name', 'description', 'intent', 'triggers',
                    'required_entities', 'steps', 'success_criteria'
                }
                
                missing_fields = required_fields - set(service.keys())
                if missing_fields:
                    raise ValueError(f"Service missing required fields: {missing_fields}")
                    
                # Validate steps
                for step in service['steps']:
                    if not all(k in step for k in ['tool', 'action', 'params']):
                        raise ValueError("Step missing required fields")
                        
                    if step['tool'] not in self.tools:
                        raise ValueError(f"Unknown tool: {step['tool']}")
                
                # Save the service
                await self._save_service(service)
                
                return {
                    'status': 'success',
                    'service': service
                }
                
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML format: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error creating service: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def _save_service(self, service: Dict[str, Any]) -> None:
        """Save a new service to the services file."""
        try:
            # Create services directory if it doesn't exist
            self.services_path.parent.mkdir(parents=True, exist_ok=True)
=======
            await self.flow_logger.log_event(
                "ServiceMaker",
                "tools_loaded",
                {"loaded_tools": loaded_tools}
            )
                    
        except Exception as e:
            logger.error(f"Error loading tools: {str(e)}")
            await self.flow_logger.log_event(
                "ServiceMaker",
                "tools_load_error",
                {"error": str(e)}
            )
            
        return tools
    
    async def create_service(self, service_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new service from a service definition.
        
        Args:
            service_def: Service definition including:
                - name: Service name
                - description: Service description
                - intent: Intent identifier
                - triggers: List of trigger phrases
                - required_entities: List of required entities
                - steps: List of execution steps
                - success_criteria: List of success criteria
                
        Returns:
            Dict containing the created service
        """
        try:
            # Validate service definition
            self._validate_service_def(service_def)
>>>>>>> main
            
            # Load existing services
            services = {}
            if self.services_path.exists():
                with open(self.services_path, 'r') as f:
                    services = yaml.safe_load(f) or {}
                    
            # Add new service
<<<<<<< HEAD
            services[service['name']] = service
            
            # Save updated services
            with open(self.services_path, 'w') as f:
                yaml.safe_dump(services, f, default_flow_style=False)
                
        except Exception as e:
            logger.error(f"Error saving service: {str(e)}")
            raise
=======
            service_name = service_def['name'].lower().replace(' ', '_')
            services[service_name] = service_def
            
            # Save services file
            self.services_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.services_path, 'w') as f:
                yaml.safe_dump(services, f, default_flow_style=False)
                
            await self.flow_logger.log_event(
                "ServiceMaker",
                "service_created",
                {
                    "service_name": service_name,
                    "intent": service_def.get('intent'),
                    "triggers_count": len(service_def.get('triggers', []))
                }
            )
            
            return service_def
            
        except Exception as e:
            logger.error(f"Error creating service: {str(e)}")
            await self.flow_logger.log_event(
                "ServiceMaker",
                "service_creation_error",
                {
                    "error": str(e),
                    "service_def": service_def
                }
            )
            raise
            
    async def update_service(self, service_name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing service.
        
        Args:
            service_name: Name of the service to update
            updates: Dict of fields to update
            
        Returns:
            Dict containing the updated service
        """
        try:
            if not self.services_path.exists():
                raise ValueError(f"Services file not found at {self.services_path}")
                
            with open(self.services_path, 'r') as f:
                services = yaml.safe_load(f) or {}
                
            if service_name not in services:
                raise ValueError(f"Service {service_name} not found")
                
            # Update service fields
            service = services[service_name]
            for key, value in updates.items():
                service[key] = value
                
            # Validate updated service
            self._validate_service_def(service)
            
            # Save services file
            with open(self.services_path, 'w') as f:
                yaml.safe_dump(services, f, default_flow_style=False)
                
            await self.flow_logger.log_event(
                "ServiceMaker",
                "service_updated",
                {
                    "service_name": service_name,
                    "updated_fields": list(updates.keys())
                }
            )
            
            return service
            
        except Exception as e:
            logger.error(f"Error updating service: {str(e)}")
            await self.flow_logger.log_event(
                "ServiceMaker",
                "service_update_error",
                {
                    "service_name": service_name,
                    "error": str(e)
                }
            )
            raise
            
    async def delete_service(self, service_name: str) -> None:
        """
        Delete a service.
        
        Args:
            service_name: Name of the service to delete
        """
        try:
            if not self.services_path.exists():
                raise ValueError(f"Services file not found at {self.services_path}")
                
            with open(self.services_path, 'r') as f:
                services = yaml.safe_load(f) or {}
                
            if service_name not in services:
                raise ValueError(f"Service {service_name} not found")
                
            # Remove service
            del services[service_name]
            
            # Save services file
            with open(self.services_path, 'w') as f:
                yaml.safe_dump(services, f, default_flow_style=False)
                
            await self.flow_logger.log_event(
                "ServiceMaker",
                "service_deleted",
                {"service_name": service_name}
            )
            
        except Exception as e:
            logger.error(f"Error deleting service: {str(e)}")
            await self.flow_logger.log_event(
                "ServiceMaker",
                "service_deletion_error",
                {
                    "service_name": service_name,
                    "error": str(e)
                }
            )
            raise
            
    def _validate_service_def(self, service_def: Dict[str, Any]) -> None:
        """
        Validate a service definition.
        
        Args:
            service_def: Service definition to validate
            
        Raises:
            ValueError: If service definition is invalid
        """
        required_fields = ['name', 'description', 'intent', 'triggers', 'steps']
        
        # Check required fields
        for field in required_fields:
            if field not in service_def:
                raise ValueError(f"Missing required field: {field}")
                
        # Validate name
        if not isinstance(service_def['name'], str) or not service_def['name'].strip():
            raise ValueError("Invalid service name")
            
        # Validate description
        if not isinstance(service_def['description'], str) or not service_def['description'].strip():
            raise ValueError("Invalid service description")
            
        # Validate intent
        if not isinstance(service_def['intent'], str) or not service_def['intent'].strip():
            raise ValueError("Invalid intent")
            
        # Validate triggers
        if not isinstance(service_def['triggers'], list) or not service_def['triggers']:
            raise ValueError("Invalid triggers")
            
        for trigger in service_def['triggers']:
            if not isinstance(trigger, str) or not trigger.strip():
                raise ValueError("Invalid trigger phrase")
                
        # Validate steps
        if not isinstance(service_def['steps'], list) or not service_def['steps']:
            raise ValueError("Invalid steps")
            
        for step in service_def['steps']:
            if not isinstance(step, dict):
                raise ValueError("Invalid step format")
                
            if 'tool' not in step or 'action' not in step:
                raise ValueError("Step missing tool or action")
                
            if not isinstance(step['tool'], str) or not step['tool'].strip():
                raise ValueError("Invalid step tool")
                
            if not isinstance(step['action'], str) or not step['action'].strip():
                raise ValueError("Invalid step action")
                
        # Validate required entities (optional)
        if 'required_entities' in service_def:
            if not isinstance(service_def['required_entities'], list):
                raise ValueError("Invalid required entities")
                
            for entity in service_def['required_entities']:
                if not isinstance(entity, str) or not entity.strip():
                    raise ValueError("Invalid entity name")
                    
        # Validate success criteria (optional)
        if 'success_criteria' in service_def:
            if not isinstance(service_def['success_criteria'], list):
                raise ValueError("Invalid success criteria")
                
            for criterion in service_def['success_criteria']:
                if not isinstance(criterion, str) or not criterion.strip():
                    raise ValueError("Invalid success criterion")
>>>>>>> main
    
    def get_available_tools(self) -> Dict[str, Any]:
        """Get information about available tools."""
        return self.tools 