from typing import Dict, Any, Optional, List, Tuple
import logging
import os
import yaml
from pathlib import Path
from openai import AsyncOpenAI
import json
from src.tools.nlp import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger

logger = logging.getLogger(__name__)

class ServiceMaker:
    """
    Creates and manages services using GPT-4 and available tools.
    Handles both new service creation and service failure recovery.
    """
    
    def __init__(self, 
                 capacity_path: str = "src/services/capacity.yaml",
                 flow_logger: Optional[FlowLogger] = None):
        """Initialize the service maker with capacity file path."""
        self.capacity_path = Path(capacity_path)
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4"
        self.flow_logger = flow_logger
        
        # Load capacity file
        self.capacity = self._load_capacity()
        
        # System prompts for different scenarios
        self.service_creation_prompt = """You are an expert system designer.
        Your task is to create a new service using available capabilities to fulfill a user request.
        
        Follow these steps:
        1. First, consider the manual steps a human would take to accomplish this task on a computer
        2. For each step, search the capabilities descriptions to find matching capabilities
        3. Verify the input/output chain:
           - Each capability's required inputs must be available
           - Each capability's outputs must match the next capability's required inputs
           - Consider where to get initial inputs (user provided or system generated)
        4. Create a service definition that chains these capabilities together
        
        Rules:
        1. Use ONLY capabilities defined in the capacity.yaml file
        2. Each step must have all required inputs from either:
           - Previous step outputs
           - Required entities
           - System-provided values
        3. Keep it focused and efficient
        4. Valid YAML format only
        5. Follow the best practices defined in the capacity metadata
        """
        
        self.service_recovery_prompt = """You are an expert system troubleshooter.
        Your task is to analyze a failed service execution and create an alternative service.
        
        Follow these steps:
        1. Analyze why the original service failed
        2. List the manual steps a human would take to accomplish this task
        3. Search for alternative capabilities that could achieve each step
        4. Verify the input/output chain works with the new capabilities
        5. Create a new service that avoids the previous failures
        
        Return ONLY the raw YAML content, without any markdown formatting or code blocks.
        Use the same YAML format as service creation.
        """

    def _load_capacity(self) -> Dict[str, Any]:
        """Load and validate the capacity file."""
        try:
            if not self.capacity_path.exists():
                raise FileNotFoundError(f"Capacity file not found: {self.capacity_path}")
                
            with open(self.capacity_path, 'r') as f:
                capacity = yaml.safe_load(f)
                
            # Validate required sections
            if 'capabilities' not in capacity:
                raise ValueError("No capabilities section found in capacity file")
                
            # Validate metadata
            if 'metadata' not in capacity:
                logger.warning("No metadata section found in capacity file")
                
            return capacity
            
        except Exception as e:
            logger.error(f"Error loading capacity: {str(e)}")
            raise

    async def handle_new_request(self, ticket: Ticket) -> Ticket:
        """Handle a new request by creating a service."""
        try:
            # Create new service
            logger.info("Attempting to create new service")
            return await self._create_new_service(ticket)
            
        except Exception as e:
            error_msg = f"Error handling request: {str(e)}"
            ticket.add_error(error_msg, "service_creation_error")
            ticket.status = TicketStatus.ERROR
            logger.error(error_msg)
            return ticket

    async def handle_service_failure(self, ticket: Ticket, failure_info: Dict[str, Any]) -> Ticket:
        """Handle a failed service execution by attempting to create a recovery service."""
        try:
            logger.info(f"Attempting to recover failed service for ticket {ticket.ticket_id}")
            # Create recovery prompt
            prompt = self._create_recovery_prompt(ticket, failure_info)
            
            # Get response from GPT
            response = await self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.service_recovery_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Process the response
            service_yaml = response.choices[0].message.content.strip()
            
            try:
                service = yaml.safe_load(service_yaml)
                if self._validate_service(service):
                    # Add recovery service to ticket
                    ticket.created_services.append(service)
                    ticket.status = TicketStatus.EXECUTING
                    logger.info(f"Created recovery service for ticket {ticket.ticket_id}")
                else:
                    ticket.status = TicketStatus.ERROR
                    ticket.add_error("Could not create valid recovery service", "recovery_error")
                    logger.error(f"Failed to create valid recovery service for ticket {ticket.ticket_id}")
                    
            except yaml.YAMLError as e:
                ticket.status = TicketStatus.ERROR
                ticket.add_error(f"Invalid recovery service format: {str(e)}", "recovery_error")
                logger.error(f"Invalid recovery service format for ticket {ticket.ticket_id}: {str(e)}")
                
        except Exception as e:
            error_msg = f"Error creating recovery service: {str(e)}"
            ticket.add_error(error_msg, "recovery_error")
            ticket.status = TicketStatus.ERROR
            logger.error(error_msg)
            
        return ticket

    async def _create_new_service(self, ticket: Ticket) -> Ticket:
        """Create a new service based on capabilities."""
        prompt = self._create_service_prompt(ticket)
        logger.info(f"Service creation prompt:\n{prompt}")
        
        response = await self.openai.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.service_creation_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        service_yaml = response.choices[0].message.content.strip()
        logger.info(f"GPT response for service creation:\n{service_yaml}")
        
        try:
            service = yaml.safe_load(service_yaml)
            logger.info(f"Parsed service definition:\n{json.dumps(service, indent=2)}")
            
            if self._validate_service(service):
                ticket.created_services.append(service)
                ticket.status = TicketStatus.EXECUTING
                logger.info(f"Created new service for ticket {ticket.ticket_id}")
            else:
                ticket.status = TicketStatus.ERROR
                ticket.add_error("Could not create valid service", "creation_error")
                logger.error(f"Failed to create valid service for ticket {ticket.ticket_id}")
                
        except yaml.YAMLError as e:
            ticket.status = TicketStatus.ERROR
            ticket.add_error(f"Invalid service format: {str(e)}", "creation_error")
            logger.error(f"Invalid service format for ticket {ticket.ticket_id}: {str(e)}")
            
        return ticket

    def _create_service_prompt(self, ticket: Ticket) -> str:
        """Create prompt for new service creation."""
        return f"""Create a service for this request: {ticket.original_message}

Available capabilities:
{yaml.dump(self.capacity, default_flow_style=False)}

Previous messages and context:
{self._format_history(ticket)}

First, list the manual steps a human would take to accomplish this task.
Then, create a service that uses the available capabilities to automate these steps.
Remember to:
1. Match each manual step to appropriate capabilities
2. Verify input/output compatibility between steps
3. Identify required user inputs
4. Follow best practices from the capacity metadata
"""

    def _create_recovery_prompt(self, ticket: Ticket, failure_info: Dict[str, Any]) -> str:
        """Create prompt for service recovery."""
        return f"""Original request: {ticket.original_message}

Failed service execution:
{yaml.dump(failure_info, default_flow_style=False)}

Available capabilities:
{yaml.dump(self.capacity, default_flow_style=False)}

First, analyze why the original service failed.
Then, list alternative manual steps to accomplish the task.
Finally, create a new service using different capabilities that avoids the previous failures.
Consider:
1. What steps failed and why
2. Alternative capabilities that could achieve the same goal
3. Input/output compatibility
4. Error handling strategies
"""

    def _validate_service(self, service: Dict[str, Any]) -> bool:
        """Validate a service definition."""
        try:
            # Validate required fields
            required_fields = ["name", "description", "intent", "triggers", "steps"]
            if not all(field in service for field in required_fields):
                missing = [f for f in required_fields if f not in service]
                logger.error(f"Missing required fields in service: {missing}")
                return False
                
            # Validate steps against capabilities
            self._validate_service_steps(service)
            return True
            
        except Exception as e:
            logger.error(f"Service validation error: {str(e)}")
            return False

    def _validate_service_steps(self, service: Dict[str, Any]) -> None:
        """Validate service steps against capabilities."""
        for step in service.get('steps', []):
            tool = step.get('tool')
            action = step.get('action')
            
            if not tool or not action:
                raise ValueError(f"Invalid step: missing tool or action")
                
            # Create capability name from tool and action
            capability_name = f"{tool}_{action}"
            
            # Check if capability exists
            if capability_name not in self.capacity.get('capabilities', {}):
                raise ValueError(f"Unknown capability: {capability_name}")
                
            capability = self.capacity['capabilities'][capability_name]
            
            # Validate parameters against inputs
            required_inputs = capability.get('inputs', {})
            provided_params = step.get('params', {})
            
            missing_params = [
                param for param in required_inputs
                if param not in provided_params and not any(
                    isinstance(v, str) and v.startswith('{') and v.endswith('}')
                    for v in provided_params.values()
                )
            ]
            
            if missing_params:
                raise ValueError(f"Missing required parameters for {capability_name}: {missing_params}")

    def _format_history(self, ticket: Ticket) -> str:
        """Format the ticket's message history for the prompt."""
        history = []
        for msg in ticket.messages:
            source = msg["source"]
            message = msg["message"]
            history.append(f"{source}: {message}")
        return "\n".join(history) 