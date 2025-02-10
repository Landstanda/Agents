from typing import Dict, Any, Optional
import logging
import json
import re
from .gpt_client import GPTClient
from ..cookbook.cookbook_manager import CookbookManager

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
        self.cookbook = CookbookManager()
        logger.info(f"{self.name} ({self.title}) is now online")
        
    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from a potentially markdown-formatted response."""
        # Try to find JSON block in markdown
        json_match = re.search(r"```(?:json)?\n(.*?)\n```", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find any JSON-like structure
        try:
            # Find the first { and last }
            start = response.find('{')
            end = response.rfind('}')
            if start != -1 and end != -1:
                json_str = response[start:end+1]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
            
        # If all else fails, create a basic structure from the raw text
        return {
            "plan": response,
            "confidence": 0.5,
            "requires_consultation": False,
            "notes": "Generated from raw response"
        }
        
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
            if not message:
                raise ValueError("Empty or invalid message received")
                
            # First, check the cookbook for matching recipes
            cookbook_analysis = self.cookbook.analyze_request(message)
            matched_recipes = cookbook_analysis.get("matched_recipes", [])
            
            # Prepare the system prompt with cookbook context
            system_prompt = self._prepare_system_prompt(cookbook_analysis)
            
            # Get GPT's analysis
            gpt_response = await self.gpt.get_completion(
                prompt=message,
                system_prompt=system_prompt,
                temperature=0.7
            )
            
            if gpt_response["status"] == "error":
                raise Exception(gpt_response["error"])
            
            # Parse GPT's response
            decision_data = self._extract_json_from_response(gpt_response["content"])
            
            # Apply decision-making rules
            if len(matched_recipes) == 0:
                # No matching recipes - enforce low confidence
                confidence = min(0.4, decision_data.get("confidence", 0.1))
                requires_consultation = True
            elif len(matched_recipes) > 1:
                # Multiple recipes - always require consultation
                confidence = decision_data.get("confidence", 0.5)
                requires_consultation = True
            else:
                # Single recipe - use GPT's confidence but ensure it's reasonable
                confidence = max(0.7, min(1.0, decision_data.get("confidence", 0.7)))
                requires_consultation = decision_data.get("requires_consultation", False)
            
            # Combine cookbook analysis with GPT's decision and our rules
            return {
                "status": "success",
                "decision": decision_data["plan"],
                "confidence": confidence,
                "requires_consultation": requires_consultation,
                "notes": decision_data.get("notes", cookbook_analysis["notes"]),
                "matched_recipes": matched_recipes,
                "required_ingredients": cookbook_analysis.get("required_ingredients", [])
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
    
    def _prepare_system_prompt(self, cookbook_analysis: Dict[str, Any]) -> str:
        """Prepare a system prompt with cookbook context."""
        matched_recipes = cookbook_analysis.get("matched_recipes", [])
        ingredients = cookbook_analysis.get("required_ingredients", [])
        
        prompt = f"""You are {self.name}, the CEO of an AI-powered office.
        
        Based on our cookbook analysis, the request matches these recipes:
        {json.dumps(matched_recipes, indent=2)}
        
        These recipes require the following ingredients (capabilities):
        {json.dumps(ingredients, indent=2)}
        
        Your role is to make high-level decisions about how to handle requests.
        
        Important guidelines:
        1. For requests matching multiple recipes (2 or more):
           - Always set requires_consultation to true
           - Consider interdependencies between recipes
           - Note potential conflicts or timing issues
        
        2. For requests with no matching recipes:
           - Set confidence to 0.1 if completely outside our capabilities
           - Set confidence to 0.3-0.4 if we might adapt existing recipes
           - Always explain limitations clearly
        
        3. For single recipe matches:
           - Set confidence based on how well the recipe fits (0.7-1.0)
           - Consider if customization is needed
        
        Respond with a JSON object containing:
        {{
            "plan": "Clear description of how to proceed",
            "confidence": 0.0-1.0,
            "requires_consultation": true/false,
            "notes": "Any additional thoughts or concerns"
        }}
        
        Remember: It's better to acknowledge limitations than to attempt tasks beyond our capabilities.
        """
        
        return prompt
    
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