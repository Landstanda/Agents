from typing import Dict, Any, Optional
import logging
from ..utils.gpt_client import GPTClient

logger = logging.getLogger(__name__)

class CEO:
    """
    The CEO is responsible for high-level decision making and strategy.
    It receives input, analyzes it, and determines the appropriate course of action.
    """
    
    def __init__(self):
        """Initialize the CEO with basic configuration."""
        self.name = "Michael"
        self.title = "CEO"
        self.gpt = GPTClient()
        logger.info(f"{self.name} ({self.title}) is now online")
        
    async def consider_request(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Consider a request and provide initial thoughts/direction.
        
        Args:
            message (str): The incoming message/request
            context (Optional[Dict]): Any relevant context for decision making
            
        Returns:
            Dict containing:
                - decision: str - The high-level decision/direction
                - confidence: float - How confident the CEO is in this direction (0-1)
                - requires_consultation: bool - Whether other departments should be consulted
                - notes: str - Any additional thoughts/context
        """
        try:
            # Prepare the system prompt
            system_prompt = f"""You are {self.name}, the CEO of an AI-powered office.
            Your role is to make high-level decisions about how to handle requests.
            Analyze the request and determine:
            1. What is the core goal/need?
            2. What capabilities might be needed?
            3. Should other departments be consulted?
            4. How confident are you in this direction?
            
            Format your response as a JSON-like structure with these keys:
            - core_goal: A clear statement of what needs to be accomplished
            - capabilities_needed: List of required capabilities
            - requires_consultation: true/false
            - confidence: 0.0-1.0
            - notes: Any additional thoughts or context
            """
            
            # Get GPT's analysis
            gpt_response = await self.gpt.get_completion(
                prompt=message,
                system_prompt=system_prompt,
                temperature=0.7
            )
            
            if gpt_response["status"] == "error":
                raise Exception(gpt_response["error"])
                
            # Parse GPT's response into our format
            # Note: In a real implementation, we'd parse the JSON response
            # For now, we'll just use the raw response
            return {
                "status": "success",
                "decision": gpt_response["content"],
                "confidence": 0.9,  # We'll extract this from GPT's response in the full implementation
                "requires_consultation": False,  # We'll extract this from GPT's response
                "notes": "Processed by GPT"
            }
            
        except Exception as e:
            logger.error(f"Error in CEO consideration: {str(e)}")
            return {
                "status": "error",
                "decision": None,
                "confidence": 0.0,
                "requires_consultation": False,
                "notes": f"Error occurred: {str(e)}"
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the CEO.
        
        Returns:
            Dict containing basic status information
        """
        return {
            "name": self.name,
            "title": self.title,
            "status": "online",
            "ready": True
        } 