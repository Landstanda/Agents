from typing import Dict, Any, Optional
import logging
import os
from openai import AsyncOpenAI
from slack_sdk.web.async_client import AsyncWebClient

logger = logging.getLogger(__name__)

class MessageMaker:
    """
    Generates and sends user messages via Slack.
    Takes context, formats with GPT, and sends via Slack.
    """
    
    def __init__(self):
        """Initialize the message maker with Slack and OpenAI clients."""
        self.slack_token = os.getenv("SLACK_BOT_TOKEN")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        
        if not self.slack_token or not self.openai_key:
            raise ValueError("Missing required environment variables")
            
        self.slack = AsyncWebClient(token=self.slack_token)
        self.openai = AsyncOpenAI(api_key=self.openai_key)
        
        # System prompt for GPT
        self.system_prompt = """You are a helpful and professional AI assistant.
        Your messages should be:
        - Clear and concise
        - Professional but friendly
        - Focused on the current task
        - Free of technical jargon
        - Formatted for Slack (can use basic markdown)
        """
    
    async def send_message(
        self,
        channel_id: str,
        context: Dict[str, Any],
        thread_ts: Optional[str] = None
    ) -> None:
        """
        Generate and send a message based on provided context.
        
        Args:
            channel_id: Slack channel ID
            context: Dict containing:
                - type: Type of message (info_request, completion, error, etc.)
                - details: Relevant details for the message
            thread_ts: Thread timestamp for threaded replies
        """
        try:
            # Create prompt for GPT based on context
            user_prompt = self._create_prompt(context)
            
            # Get GPT response
            response = await self.openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            if response.choices:
                message = response.choices[0].message.content.strip()
                
                # Send to Slack
                await self.slack.chat_postMessage(
                    channel=channel_id,
                    text=message,
                    thread_ts=thread_ts
                )
            else:
                logger.error("No response from GPT")
                # Send fallback message
                await self.slack.chat_postMessage(
                    channel=channel_id,
                    text=self._get_fallback_message(context),
                    thread_ts=thread_ts
                )
                
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            # Send basic error message
            try:
                # If context has a message in details, use that, otherwise use fallback
                message = context.get("details", {}).get("message") or self._get_fallback_message(context)
                await self.slack.chat_postMessage(
                    channel=channel_id,
                    text=message,
                    thread_ts=thread_ts
                )
            except Exception as e2:
                logger.error(f"Failed to send fallback message: {str(e2)}")
    
    def _create_prompt(self, context: Dict[str, Any]) -> str:
        """Create GPT prompt based on message context."""
        msg_type = context.get('type', '')
        details = context.get('details', {})
        
        prompts = {
            'info_request': f"""
                I need to ask the user for some information.
                Missing information: {details.get('missing_info', [])}
                Service context: {details.get('service', '')}
                Generate a friendly message asking for this information.
            """,
            'completion': f"""
                I need to inform the user about their completed request.
                Service: {details.get('service', '')}
                Results: {details.get('results', {})}
                Generate a friendly message summarizing what was done.
            """,
            'error': f"""
                I need to inform the user about an error.
                Error: {details.get('error', '')}
                Generate a friendly message explaining the error.
            """,
            'service_creation': f"""
                I need to inform the user about a new service.
                Service: {details.get('service', '')}
                Generate a message about the new service being created.
            """,
            'default': f"""
                I need to send a message to the user.
                Context: {details}
                Generate an appropriate response.
            """
        }
        
        return prompts.get(msg_type, prompts['default'])
    
    def _get_fallback_message(self, context: Dict[str, Any]) -> str:
        """Get a basic fallback message if GPT fails."""
        msg_type = context.get('type', '')
        details = context.get('details', {})
        
        fallbacks = {
            'info_request': f"I need some additional information: {', '.join(details.get('missing_info', []))}",
            'completion': "I've completed your request successfully.",
            'error': f"I apologize, but I encountered an error: {details.get('error', 'Unknown error')}",
            'service_creation': f"I've created a new service to handle your request: {details.get('service', '')}",
            'default': "I'm processing your request."
        }
        
        return fallbacks.get(msg_type, fallbacks['default']) 