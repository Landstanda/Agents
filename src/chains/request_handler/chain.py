#!/usr/bin/env python3

from typing import Dict, Any, List
import os
import json
from openai import OpenAI
from ...modules.base_chain import Chain
from ...utils.logging import get_logger

logger = get_logger(__name__)

class RequestHandlerChain(Chain):
    """Chain for handling all incoming requests and routing them appropriately"""
    
    def __init__(self):
        # First initialize the BaseChain
        super().__init__("request_handler_chain")
        
        # Set version
        self.version = "1.0"
        
        # Initialize OpenAI client
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Required modules
        from ...modules.slack_integration import SlackModule
        
        # Initialize modules
        self.modules = {
            'slack': SlackModule()
        }
        
        # Define required variables
        self.required_variables = ['text']
        self.optional_variables = ['user', 'channel_id']
        
        # Define success criteria
        self.success_criteria = [
            "Request is properly analyzed",
            "Appropriate response type is determined",
            "Request is routed to correct chain or handled directly"
        ]
        
        # Initialize keywords for general matching
        self.keywords = self._initialize_keywords()
    
    def _initialize_keywords(self) -> List[str]:
        """Initialize keywords for request matching"""
        return ['help', 'hi', 'hello', 'thanks', 'please', 'can', 'could', 'would']
    
    async def execute(self, chain_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the request handler chain"""
        try:
            request = chain_vars.get('text', '')
            if not request:
                return {
                    'status': 'error',
                    'message': 'No text provided in request',
                    'data': None
                }
            
            # Analyze request using OpenAI
            analysis = await self._analyze_request(request)
            
            if analysis['type'] == 'conversation':
                # Handle simple conversation
                return {
                    'status': 'success',
                    'message': analysis['response'],
                    'data': {
                        'type': 'conversation',
                        'intent': analysis['intent']
                    }
                }
            elif analysis['type'] == 'task':
                # Return routing information for task
                return {
                    'status': 'success',
                    'message': f"I'll help you with that. Let me {analysis['intent']}.",
                    'data': {
                        'type': 'task',
                        'chain': analysis['chain'],
                        'intent': analysis['intent'],
                        'variables': analysis['variables']
                    }
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Could not determine how to handle the request',
                    'data': None
                }
                
        except Exception as e:
            logger.error(f"Error executing request handler chain: {str(e)}")
            return {
                'status': 'error',
                'message': "I encountered an error processing your request. Please try again.",
                'data': None
            }
    
    async def _analyze_request(self, request: str) -> Dict[str, Any]:
        """Analyze request using OpenAI to determine intent and action"""
        try:
            # Handle simple greetings directly without API call
            request_lower = request.lower().strip()
            if request_lower in ['hi', 'hello', 'hey']:
                return {
                    "type": "conversation",
                    "intent": "greeting",
                    "response": "Hello! How can I help you today?",
                    "chain": None,
                    "variables": {}
                }
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": """You are an AI assistant that analyzes user requests and determines:
1. Whether this is a simple conversation (greeting, thanks, etc.) or a task request
2. The intent of the request
3. For tasks, which chain should handle it (email_processing_chain, web_research_chain, etc.)
4. Any relevant variables from the request

Available chains:
- email_processing_chain (for email related tasks)
- web_research_chain (for research and information gathering)
- business_communication_chain (for team communication)
- document_management_chain (for document handling)
- project_management_chain (for project and task management)

Respond in JSON format with:
{
    "type": "conversation" or "task",
    "intent": "the identified intent",
    "response": "for conversations, the response to send",
    "chain": "for tasks, the chain name to use",
    "variables": {} // for tasks, extracted variables
}"""},
                    {"role": "user", "content": request}
                ]
            )
            
            # Parse the response safely using json.loads()
            try:
                result = json.loads(response.choices[0].message.content)
                # Validate response structure
                required_keys = ['type', 'intent', 'response']
                if not all(key in result for key in required_keys):
                    raise ValueError("Invalid response structure from OpenAI")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI response: {str(e)}")
                raise
            
        except Exception as e:
            logger.error(f"Error analyzing request: {str(e)}")
            return {
                "type": "conversation",
                "intent": "error",
                "response": "I'm having trouble understanding your request. Could you please rephrase it?",
                "chain": None,
                "variables": {}
            } 