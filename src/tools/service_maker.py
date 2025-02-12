from typing import Dict, Any, Optional, List
import logging
import os
import yaml
from pathlib import Path
from openai import AsyncOpenAI
import json

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
    
    def get_available_tools(self) -> Dict[str, Any]:
        """Get information about available tools."""
        return self.tools 