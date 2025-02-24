from typing import Dict, Any, Optional, List, Tuple
import logging
import os
import json
from pathlib import Path
from openai import AsyncOpenAI
from datetime import datetime
from src.models import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger
import httpx

logger = logging.getLogger(__name__)

class ServiceAnalyzer:
    """
    Analyzes user requests using GPT to identify required services and create execution plans.
    Replaces the trigger-word based system with a more flexible GPT-based analysis.
    """
    
    def __init__(self, 
                 services_path: str = "src/services/service_index.json",
                 flow_logger: Optional[FlowLogger] = None):
        """Initialize the service analyzer."""
        self.services_path = Path(services_path)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
            
        # Create httpx client with proper configuration
        http_client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True
        )
        
        # Initialize OpenAI client with http_client
        self.openai = AsyncOpenAI(
            api_key=api_key,
            http_client=http_client
        )
        
        self.flow_logger = flow_logger
        self.services_schema = self._load_services_schema()
        
        # System prompt for GPT
        self.system_prompt = """You are an expert system analyzer that breaks down user requests into executable steps.
        Your task is to analyze requests and create detailed execution plans using available services.
        
        You must:
        1. Understand the user's request and desired outcome
        2. Break down complex requests into discrete steps
        3. Match steps to available services
        4. Validate all required inputs are available
        
        Rules:
        1. Only use services defined in the schema
        2. Ensure all required parameters are specified
        3. If a request cannot be fulfilled, explain why
        4. Return results in exact JSON format
        """
        
        # Analysis prompt template
        self.analysis_prompt = """Analyze this request: {message}

Available services and their combinations:
{services_json}

Required output format:
{{
    "understood_request": string,  # Clear description of the understood request
    "confidence": float,  # 0.0-1.0 confidence in analysis
    "execution_steps": [  # Ordered list of steps to execute
        {{
            "step_number": int,
            "service_id": string,
            "description": string,
            "required_params": {{  # Parameters required for this step
                "param_name": string
            }},
            "optional_params": {{
                "param_name": string
            }}
        }}
    ],
    "missing_information": [  # List of missing required information
        {{
            "param": string,
            "service": string,
            "description": string,
            "step_number": int
        }}
    ]
}}

Return ONLY valid JSON matching this schema."""
    
    def _load_services_schema(self) -> Dict[str, Any]:
        """Load and validate the services schema."""
        try:
            if not self.services_path.exists():
                raise FileNotFoundError(f"Services file not found: {self.services_path}")
                
            with open(self.services_path, 'r') as f:
                services = json.load(f)
                
            # Convert to a more GPT-friendly format
            schema = {
                "version": "1.0",
                "services": services
            }
            
            return schema
            
        except Exception as e:
            logger.error(f"Error loading services schema: {str(e)}")
            raise
    
    async def analyze_request(self, ticket: Ticket) -> Ticket:
        """
        Analyze a user request using GPT to create an execution plan.
        
        Args:
            ticket: The ticket containing the request and context
            
        Returns:
            Updated ticket with execution plan
        """
        try:
            # Only update status if not already analyzing
            if ticket.status != TicketStatus.ANALYZING:
                ticket.update_status(TicketStatus.ANALYZING)
            
            # Format services for GPT
            services_json = json.dumps(self.services_schema, indent=2)
            
            # Create analysis prompt
            prompt = self.analysis_prompt.format(
                message=ticket.original_message,
                services_json=services_json
            )
            
            # Get GPT analysis
            response = await self.openai.chat.completions.create(
                model="gpt-4",  # Using GPT-4 for better analysis
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1  # Low temperature for consistent results
            )
            
            if not response.choices:
                raise ValueError("No response from GPT")
                
            # Parse GPT response
            try:
                analysis = json.loads(response.choices[0].message.content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from GPT: {str(e)}")
                # Retry with a more explicit prompt
                return await self._retry_analysis(ticket)
            
            # Validate analysis
            if not self._validate_analysis(analysis):
                logger.error("Invalid analysis structure")
                return await self._retry_analysis(ticket)
            
            # Update ticket based on analysis
            ticket = self._update_ticket(ticket, analysis)
            
            # Log analysis results
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "ServiceAnalyzer",
                    "request_analyzed",
                    {
                        "ticket_id": ticket.ticket_id,
                        "confidence": analysis.get("confidence"),
                        "execution_plan": analysis.get("execution_steps"),
                        "missing_inputs": analysis.get("missing_information")
                    }
                )
            
            return ticket
            
        except Exception as e:
            logger.error(f"Error analyzing request: {str(e)}")
            ticket.update_status(TicketStatus.ERROR)
            ticket.add_error(str(e), "analysis_error")
            return ticket
    
    async def _retry_analysis(self, ticket: Ticket) -> Ticket:
        """Retry analysis with a more explicit prompt."""
        # TODO: Implement retry logic with different prompts
        ticket.update_status(TicketStatus.ERROR)
        ticket.add_error("Failed to analyze request", "analysis_error")
        return ticket
    
    def _validate_analysis(self, analysis: Dict[str, Any]) -> bool:
        """Validate the structure of GPT's analysis."""
        required_fields = {
            "understood_request": str,
            "confidence": float,
            "execution_steps": list,
            "missing_information": list
        }
        
        try:
            # Check required fields and types
            for field, field_type in required_fields.items():
                if field not in analysis:
                    logger.error(f"Missing required field: {field}")
                    return False
                if not isinstance(analysis[field], field_type):
                    logger.error(f"Invalid type for {field}: expected {field_type}")
                    return False
            
            # Validate confidence range
            if not 0 <= analysis["confidence"] <= 1:
                logger.error("Confidence must be between 0 and 1")
                return False
            
            # Validate execution plan
            for step in analysis["execution_steps"]:
                if not all(k in step for k in ["step_number", "service_id", "description", "required_params", "optional_params"]):
                    logger.error("Invalid step structure")
                    return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating analysis: {str(e)}")
            return False
    
    def _update_ticket(self, ticket: Ticket, analysis: Dict[str, Any]) -> Ticket:
        """Update ticket based on analysis results."""
        # Extract first service and its parameters from execution steps
        if analysis.get("execution_steps"):
            first_step = analysis["execution_steps"][0]
            ticket.service = first_step["service_id"]
            
            # Update entities with provided values
            ticket.entities = {}
            if "required_params" in first_step:
                ticket.entities.update(first_step["required_params"])
            if "optional_params" in first_step:
                ticket.entities.update(first_step["optional_params"])
            
            # Update execution plan and steps
            ticket.execution_plan = analysis["execution_steps"]
            ticket.execution_steps.clear()  # Clear existing steps
            for step in analysis["execution_steps"]:
                ticket.execution_steps.append(step)
            
            # Check for missing information
            missing_info = analysis.get("missing_information", [])
            if missing_info:
                ticket.missing_entities = [info["param"] for info in missing_info]
                ticket.update_status(TicketStatus.WAITING_INPUT)
            else:
                ticket.update_status(TicketStatus.EXECUTING)
        else:
            ticket.update_status(TicketStatus.ERROR)
            ticket.add_error("No execution steps found", "analysis_error")
            
        return ticket
        
    def _sort_execution_plan(self, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort execution plan based on step numbers and dependencies."""
        # First sort by step number
        sorted_plan = sorted(plan, key=lambda x: x["step_number"])
        
        # Then ensure dependency order is maintained
        final_plan = []
        processed_steps = set()
        
        while len(final_plan) < len(sorted_plan):
            for step in sorted_plan:
                if step in final_plan:
                    continue
                    
                # Check if all dependencies are met
                dependencies = set(step.get("depends_on", []))
                if dependencies.issubset(processed_steps):
                    final_plan.append(step)
                    processed_steps.add(step["step_number"])
                    
        return final_plan 