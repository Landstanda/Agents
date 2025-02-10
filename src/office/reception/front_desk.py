from typing import Dict, Any, Optional
import logging
from slack_sdk.web import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
import json
import os
from dotenv import load_dotenv
from ..executive.ceo import CEO
from .nlp_processor import NLPProcessor

logger = logging.getLogger(__name__)

class FrontDesk:
    """
    The Front Desk handles all Slack communication, acting as the office's voice.
    It maintains a professional and helpful tone while facilitating communication
    between users and the CEO.
    """
    
    def __init__(self):
        """Initialize the Front Desk with Slack credentials and CEO connection."""
        load_dotenv()
        
        # Initialize Slack clients
        self.slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.slack_app_token = os.getenv("SLACK_APP_TOKEN")
        
        if not self.slack_bot_token or not self.slack_app_token:
            raise ValueError("Missing Slack tokens in environment variables")
            
        self.web_client = WebClient(token=self.slack_bot_token)
        self.socket_client = SocketModeClient(
            app_token=self.slack_app_token,
            web_client=self.web_client
        )
        
        # Initialize CEO connection and NLP processor
        self.ceo = CEO()
        self.nlp = NLPProcessor()
        
        # Set up personality
        self.name = "Sarah"
        self.title = "Front Desk Manager"
        logger.info(f"{self.name} ({self.title}) is now online")
        
    async def handle_message(self, message: Dict[str, Any]) -> None:
        """
        Handle incoming Slack messages.
        
        Args:
            message: The Slack message event
        """
        try:
            # Extract relevant message information
            user_id = message.get("user")
            channel_id = message.get("channel")
            text = message.get("text", "").strip()
            
            if not text or not user_id or not channel_id:
                return
                
            # Get user info for personalization
            user_info = self.web_client.users_info(user=user_id)["user"]
            
            # Process message with NLP
            nlp_result = self.nlp.process_message(text, user_info)
            
            if nlp_result["status"] == "error":
                logger.error(f"NLP processing error: {nlp_result.get('error')}")
                self._send_error_message(channel_id, message.get("ts"))
                return
            
            # Forward processed request to CEO
            logger.info(f"Forwarding processed request from {user_info['real_name']} to CEO")
            response = await self.ceo.consider_request(
                message=text,
                context={
                    "nlp_analysis": nlp_result,
                    "channel_id": channel_id,
                    "thread_ts": message.get("thread_ts", message["ts"])
                }
            )
            
            # Format and send response
            slack_response = self._format_response(response, nlp_result, user_info["real_name"])
            self.web_client.chat_postMessage(
                channel=channel_id,
                text=slack_response,
                thread_ts=message.get("thread_ts", message["ts"])
            )
            
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            self._send_error_message(channel_id, message.get("ts"))
    
    def _format_response(
        self,
        ceo_response: Dict[str, Any],
        nlp_result: Dict[str, Any],
        user_name: str
    ) -> str:
        """Format CEO's response for Slack, incorporating NLP insights."""
        if ceo_response["status"] == "error":
            return (
                f"I apologize, {user_name}, but I encountered an error while processing "
                f"your request. {ceo_response['notes']}"
            )
        
        # Start with a greeting that reflects urgency
        if nlp_result["urgency"] > 0.7:
            response_parts = [f"Hi {user_name}! I'll help you with this urgent matter right away."]
        else:
            response_parts = [f"Hi {user_name}!"]
        
        # Add main response
        response_parts.append(ceo_response["decision"])
        
        # Add timing information if present
        temporal = nlp_result["temporal_context"]
        if temporal["has_deadline"]:
            if temporal["specific_day"]:
                response_parts.append(f"\n_I've noted that this needs to be done by {temporal['specific_day']}._")
            elif temporal["timeframe"]:
                timeframe_text = {
                    "urgent": "as soon as possible",
                    "today": "today",
                    "tomorrow": "tomorrow",
                    "next_week": "next week"
                }.get(temporal["timeframe"], "")
                if timeframe_text:
                    response_parts.append(f"\n_I've noted that this needs to be done {timeframe_text}._")
        
        # If consultation is needed, add a note
        if ceo_response["requires_consultation"]:
            response_parts.append(
                "\n_Note: This request may require additional consultation. "
                "I'll coordinate with the relevant departments and keep you updated._"
            )
        
        # If we have matched recipes, add what we're using
        if ceo_response.get("matched_recipes"):
            recipes = [r["name"] for r in ceo_response["matched_recipes"]]
            response_parts.append(
                f"\n_I'll be using our {' and '.join(recipes)} procedures to help with this._"
            )
        
        # Add any additional notes
        if ceo_response.get("notes"):
            response_parts.append(f"\n_{ceo_response['notes']}_")
        
        return "\n\n".join(response_parts)
    
    def _send_error_message(self, channel_id: str, thread_ts: Optional[str] = None) -> None:
        """Send an error message to Slack."""
        message = (
            "I apologize, but I encountered an unexpected error. "
            "Please try your request again, or contact IT support if the problem persists."
        )
        try:
            self.web_client.chat_postMessage(
                channel=channel_id,
                text=message,
                thread_ts=thread_ts
            )
        except Exception as e:
            logger.error(f"Error sending error message: {str(e)}")
    
    async def process_socket_request(self, client: SocketModeClient, req: SocketModeRequest) -> None:
        """Process Socket Mode requests from Slack."""
        if req.type == "events_api":
            # Acknowledge the request
            response = SocketModeResponse(envelope_id=req.envelope_id)
            await client.send_socket_mode_response(response)
            
            # Process the event
            event = req.payload["event"]
            if event["type"] == "message" and "subtype" not in event:
                await self.handle_message(event)
    
    def start(self) -> None:
        """Start the Front Desk service."""
        try:
            # Register event handler
            self.socket_client.socket_mode_request_listeners.append(self.process_socket_request)
            
            # Start listening
            self.socket_client.connect()
            logger.info(f"{self.name} is now listening for Slack messages")
            
        except Exception as e:
            logger.error(f"Error starting Front Desk: {str(e)}")
            raise 