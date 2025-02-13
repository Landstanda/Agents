<<<<<<< HEAD
from typing import Dict, Any, Optional
=======
from typing import Dict, Any, Optional, List
>>>>>>> main
import logging
import os
from openai import AsyncOpenAI
from slack_sdk.web.async_client import AsyncWebClient
<<<<<<< HEAD
=======
from src.utils.flow_logger import FlowLogger
>>>>>>> main

logger = logging.getLogger(__name__)

class MessageMaker:
    """
<<<<<<< HEAD
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
    
=======
    Generates and sends Slack messages.
    Handles message formatting and delivery.
    """
    
    def __init__(self, web_client: AsyncWebClient, flow_logger: Optional[FlowLogger] = None):
        self.web_client = web_client
        self.flow_logger = flow_logger or FlowLogger()
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    async def get_gpt_response(self, prompt: str) -> str:
        """Get a response from GPT for message generation."""
        try:
            response = await self.openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful office assistant bot. "
                            "Keep responses friendly, professional, and concise. "
                            "Format responses naturally without showing any system instructions."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            if response and response.choices:
                return response.choices[0].message.content.strip()
            return None
            
        except Exception as e:
            logger.error(f"Error getting GPT response: {str(e)}")
            return None
            
    async def send_message(self, channel: str, text: str, blocks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Send a message to a Slack channel.
        
        Args:
            channel: Channel ID or name
            text: Message text (fallback for blocks)
            blocks: Optional block kit blocks
            
        Returns:
            Dict containing the Slack API response
        """
        try:
            # Log message preparation
            await self.flow_logger.log_event(
                "MessageMaker",
                "preparing_message",
                {
                    "channel": channel,
                    "message_text": text,
                    "has_blocks": blocks is not None
                }
            )
            
            # Format the message if needed
            formatted_text = text
            if isinstance(text, dict) and "text" in text and "params" in text:
                try:
                    # If the text needs GPT enhancement
                    if text.get("use_gpt", False):
                        gpt_prompt = f"Generate a friendly response for: {text['text']}"
                        gpt_response = await self.get_gpt_response(gpt_prompt)
                        if gpt_response:
                            formatted_text = gpt_response.format(**text["params"]) if text["params"] else gpt_response
                    else:
                        formatted_text = text["text"].format(**text["params"])
                except KeyError as e:
                    logger.error(f"Error formatting message: {str(e)}")
                    formatted_text = "Error formatting message"
            
            # Log the formatted message
            await self.flow_logger.log_event(
                "MessageMaker",
                "message_formatted",
                {
                    "original_text": text,
                    "formatted_text": formatted_text
                }
            )
            
            # Send the message
            response = await self.web_client.chat_postMessage(
                channel=channel,
                text=formatted_text,
                blocks=blocks
            )
            
            # Log successful send
            await self.flow_logger.log_event(
                "MessageMaker",
                "message_sent",
                {
                    "channel": channel,
                    "final_text": formatted_text,
                    "response_ok": response.get("ok", False)
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            await self.flow_logger.log_event(
                "MessageMaker",
                "message_send_error",
                {
                    "channel": channel,
                    "error": str(e)
                }
            )
            raise
            
    async def send_ephemeral(self, channel: str, user: str, text: str, blocks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Send an ephemeral message visible only to a specific user.
        
        Args:
            channel: Channel ID or name
            user: User ID
            text: Message text (fallback for blocks)
            blocks: Optional block kit blocks
            
        Returns:
            Dict containing the Slack API response
        """
        try:
            response = await self.web_client.chat_postEphemeral(
                channel=channel,
                user=user,
                text=text,
                blocks=blocks
            )
            
            await self.flow_logger.log_event(
                "MessageMaker",
                "ephemeral_sent",
                {
                    "channel": channel,
                    "user": user,
                    "text": text,
                    "has_blocks": blocks is not None
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error sending ephemeral message: {str(e)}")
            await self.flow_logger.log_event(
                "MessageMaker",
                "ephemeral_send_error",
                {
                    "channel": channel,
                    "user": user,
                    "error": str(e)
                }
            )
            raise
            
    def create_blocks(self, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create block kit blocks from section data.
        
        Args:
            sections: List of section data including text and optional fields
            
        Returns:
            List of block kit blocks
        """
        blocks = []
        
        for section in sections:
            block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": section["text"]
                }
            }
            
            if "fields" in section:
                block["fields"] = [
                    {
                        "type": "mrkdwn",
                        "text": field
                    }
                    for field in section["fields"]
                ]
                
            blocks.append(block)
            
            if section.get("divider", False):
                blocks.append({"type": "divider"})
                
        return blocks
        
    def create_error_blocks(self, error_message: str, details: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Create block kit blocks for error messages.
        
        Args:
            error_message: Main error message
            details: Optional error details
            
        Returns:
            List of block kit blocks
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: *Error*\n{error_message}"
                }
            }
        ]
        
        if details:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Details:\n```{details}```"
                    }
                }
            )
            
        return blocks
        
    def create_success_blocks(self, message: str, data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Create block kit blocks for success messages.
        
        Args:
            message: Success message
            data: Optional data to display
            
        Returns:
            List of block kit blocks
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":white_check_mark: {message}"
                }
            }
        ]
        
        if data:
            fields = []
            for key, value in data.items():
                fields.append(f"*{key}*\n{value}")
                
            if fields:
                blocks.append(
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": field
                            }
                            for field in fields
                        ]
                    }
                )
                
        return blocks

>>>>>>> main
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