from typing import Dict, Any, Optional
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class CEO:
    """
    A simplified CEO that works directly with Front Desk to process requests.
    Focuses on making decisions about user requests and providing structured responses.
    """
    
    def __init__(self):
        """Initialize the CEO with basic configuration."""
        self.name = "Michael"
        self.title = "CEO"
        logger.info(f"{self.name} ({self.title}) is now online")
    
    async def consider_request(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Consider a request and provide a structured response.
        
        Args:
            message: The user's request message
            context: Additional context including NLP analysis
            
        Returns:
            Dict containing:
                - status: "success" or "error"
                - decision: What to do about the request
                - confidence: How confident we are (0-1)
                - requires_consultation: Whether we need more input
                - matched_recipes: List of relevant action types
                - notes: Additional information
        """
        try:
            if not message:
                raise ValueError("Empty message received")
            
            # Extract NLP analysis if available
            nlp_analysis = context.get("nlp_analysis", {}) if context else {}
            intents = nlp_analysis.get("intents", [])
            urgency = nlp_analysis.get("urgency", 0.5)
            
            # Map intents to recipes
            recipes = []
            if "email_read" in intents:
                recipes.append({
                    "name": "email_processing",
                    "type": "read",
                    "confidence": 0.8
                })
            if "email_send" in intents:
                recipes.append({
                    "name": "email_processing",
                    "type": "send",
                    "confidence": 0.8
                })
            if "scheduling" in intents or "meeting_scheduler" in intents:
                recipes.append({
                    "name": "meeting_scheduler",
                    "confidence": 0.9
                })
            if "research" in intents:
                recipes.append({
                    "name": "research_report",
                    "confidence": 0.7
                })
            if "document" in intents:
                recipes.append({
                    "name": "document_management",
                    "confidence": 0.7
                })
            
            # Determine confidence and consultation needs
            if not recipes:
                response = {
                    "status": "success",
                    "decision": (
                        "I apologize, but I'm not sure how to help with this request. "
                        "Could you please rephrase it or let me know more specifically what you need?"
                    ),
                    "confidence": 0.1,
                    "requires_consultation": True,
                    "matched_recipes": [],
                    "notes": "No matching capabilities found"
                }
                logger.info(f"CEO Response: {response['decision']}")
                return response
            
            # Handle multi-recipe scenarios
            if len(recipes) > 1:
                response = {
                    "status": "success",
                    "decision": (
                        "I understand your request involves multiple steps. "
                        "I'll help coordinate these activities to ensure everything is handled properly."
                    ),
                    "confidence": sum(r["confidence"] for r in recipes) / len(recipes),
                    "requires_consultation": True,
                    "matched_recipes": recipes,
                    "notes": "Multiple steps identified"
                }
                logger.info(f"CEO Response: {response['decision']}")
                return response
            
            # Handle single recipe scenarios
            recipe = recipes[0]
            if recipe["name"] == "email_processing":
                action_type = recipe.get("type", "read")
                decision = (
                    "I'll help you process your emails. "
                    f"I understand you want to {action_type} emails."
                )
            elif recipe["name"] == "meeting_scheduler":
                decision = (
                    "I'll help you schedule the meeting. "
                    "I'll make sure to coordinate with all participants."
                )
            elif recipe["name"] == "research_report":
                decision = (
                    "I'll help you research this topic and prepare a report. "
                    "I'll make sure to include relevant data and insights."
                )
            elif recipe["name"] == "document_management":
                decision = (
                    "I'll help you with the document. "
                    "I'll ensure it meets our quality standards."
                )
            else:
                decision = "I'll help you with this request."
            
            response = {
                "status": "success",
                "decision": decision,
                "confidence": recipe["confidence"],
                "requires_consultation": False,
                "matched_recipes": recipes,
                "notes": f"Using {recipe['name']} capability"
            }
            logger.info(f"CEO Response: {response['decision']}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            response = {
                "status": "error",
                "decision": None,
                "confidence": 0.0,
                "requires_consultation": True,
                "matched_recipes": [],
                "notes": str(e)
            }
            logger.error(f"CEO Error Response: {response['notes']}")
            return response
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the CEO."""
        return {
            "name": self.name,
            "title": self.title,
            "status": "online",
            "ready": True
        } 