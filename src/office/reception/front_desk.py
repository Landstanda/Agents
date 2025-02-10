from typing import Dict, Any, Optional
import logging
import asyncio
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv
from ..executive.ceo import CEO
from .nlp_processor import NLPProcessor
from openai import AsyncOpenAI

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
        
        # Initialize Slack credentials
        self.slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.slack_app_token = os.getenv("SLACK_APP_TOKEN")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.slack_bot_token or not self.slack_app_token:
            raise ValueError("Missing Slack tokens in environment variables")
        if not self.openai_api_key:
            raise ValueError("Missing OpenAI API key in environment variables")
            
        # Initialize components
        self.web_client = AsyncWebClient(token=self.slack_bot_token)
        self.socket_client = None  # Will be initialized in start()
        self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
        self.ceo = CEO()
        self.nlp = NLPProcessor()
        
        # Set up personality
        self.name = "Sarah"
        self.title = "Front Desk Manager"
        self.running = False
        self.start_time = None
        self.bot_id = None
        self.bot_mention = None
        
        # Initialize message deduplication set
        self._processed_messages = set()
        self._error_messages = set()  # Track error messages to prevent duplicates
        
        logger.info(f"{self.name} ({self.title}) initialization complete")
    
    async def process_event(self, client: SocketModeClient, req: SocketModeRequest) -> None:
        """Process incoming Socket Mode events."""
        try:
            # Always acknowledge the request first
            await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
            
            if req.type != "events_api":
                return
                
            event = req.payload["event"]
            event_type = event.get("type")
            
            # Only process messages and app_mentions
            if event_type not in ["message", "app_mention"]:
                return
                
            # Skip messages from the bot itself
            if event.get("user") == self.bot_id:
                return
                
            # Skip message subtypes (like message_changed, etc.)
            if event.get("subtype"):
                return
            
            # Get the message text and check if it mentions the bot
            text = event.get("text", "").strip()
            if not text:
                return
                
            # Only process if it's a mention or contains our mention
            if event_type != "app_mention" and self.bot_mention not in text:
                return
            
            # Check for message deduplication
            message_ts = event.get("ts")
            if message_ts in self._processed_messages:
                logger.debug(f"Skipping already processed message: {message_ts}")
                return
            
            # Add to processed messages before handling
            self._processed_messages.add(message_ts)
            if len(self._processed_messages) > 1000:
                self._processed_messages = set(list(self._processed_messages)[-500:])
            
            # Handle the message
            await self.handle_message(event)
    
        except Exception as e:
            logger.error(f"Error processing event: {str(e)}")
            logger.exception(e)
    
    async def get_gpt_response(self, prompt: str) -> str:
        """Get a quick response from GPT-3.5-turbo."""
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are Sarah, a helpful and professional front desk manager. Keep responses concise, friendly, and under 50 words. For simple greetings or casual conversation, respond naturally without overthinking."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error getting GPT response: {str(e)}")
            return None
    
    async def handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming Slack messages."""
        try:
            # Extract message info
            channel_id = message.get("channel")
            user_id = message.get("user")
            # Only use thread_ts if message is part of a thread
            thread_ts = message.get("thread_ts") if message.get("thread_ts") else None
            text = message.get("text", "").replace(self.bot_mention, "").strip()
            
            logger.info(f"Processing message: {text}")
            
            # Skip if missing required fields
            if not text or not user_id or not channel_id:
                logger.warning("Missing required fields in message")
                return
            
            # Get user info for personalization
            try:
                user_info = await self.web_client.users_info(user=user_id)
                user_name = user_info["user"]["real_name"]
            except Exception as e:
                logger.error(f"Error getting user info: {str(e)}")
                user_name = "there"
            
            # Handle special commands
            if text.lower() == "help":
                await self._send_help_message(channel_id, thread_ts)
                return
            elif text.lower() == "status":
                await self._send_status_message(channel_id, thread_ts)
                return
            
            # Process with NLP
            logger.info(f"Sending to NLP processor: {text}")
            nlp_result = self.nlp.process_message(text, user_info["user"])
            logger.info(f"NLP result: {json.dumps(nlp_result, indent=2)}")
            
            # Send to CEO
            logger.info("Sending to CEO for consideration")
            response = await self.ceo.consider_request(
                message=text,
                context={
                    "nlp_analysis": nlp_result,
                    "channel_id": channel_id,
                    "thread_ts": thread_ts
                }
            )
            logger.info(f"CEO response: {json.dumps(response, indent=2)}")
            
            # Format and send response
            slack_response = self._format_response(response, nlp_result, user_name)
            await self.web_client.chat_postMessage(
                channel=channel_id,
                text=slack_response,
                thread_ts=thread_ts
            )
            
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            error_key = f"{channel_id}:{thread_ts if thread_ts else message.get('ts')}"
            await self._send_error_message(channel_id, thread_ts, error_key)
    
    async def _send_help_message(self, channel_id: str, thread_ts: Optional[str] = None) -> None:
        """Send help information."""
        help_text = f"""*Available Commands:*
• `{self.bot_mention} help` - Show this help message
• `{self.bot_mention} status` - Check my current status

You can also chat with me naturally! Just mention me and ask anything. 💬
Examples:
• `{self.bot_mention} What can you help me with?`
• `{self.bot_mention} Can you help me schedule a meeting?`
• `{self.bot_mention} Could you research AI trends?`

I'll analyze your request and coordinate with our CEO to help you! 🤖✨"""
        
        await self.web_client.chat_postMessage(
            channel=channel_id,
            text=help_text,
            thread_ts=thread_ts
        )
    
    async def _send_status_message(self, channel_id: str, thread_ts: Optional[str] = None) -> None:
        """Send current status information."""
        if self.start_time:
            uptime = datetime.now() - self.start_time
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            status_text = f"""*Current Status:*
• 🟢 Active and listening
• ⏱️ Uptime: {hours}h {minutes}m
• 👥 Team: {self.name} (Front Desk) & Michael (CEO)
• 🔄 Processing: Socket Mode"""
        else:
            status_text = "⚠️ Status information not available"
            
        await self.web_client.chat_postMessage(
            channel=channel_id,
            text=status_text,
            thread_ts=thread_ts
        )
    
    async def _send_error_message(self, channel_id: str, thread_ts: Optional[str] = None, error_key: Optional[str] = None) -> None:
        """Send an error message to Slack, preventing duplicates."""
        if error_key and error_key in self._error_messages:
            logger.debug(f"Skipping duplicate error message for {error_key}")
            return
            
        message = (
            "I apologize, but I encountered an error while processing your request. "
            "I've logged the error and will work on improving my handling of this type of request. "
            "In the meantime, you could try:\n"
            "• Rephrasing your request\n"
            "• Using simpler language\n"
            "• Breaking it into smaller parts\n"
            "• Using the `help` command to see examples"
        )
        try:
            await self.web_client.chat_postMessage(
                channel=channel_id,
                text=message,
                thread_ts=thread_ts
            )
            if error_key:
                self._error_messages.add(error_key)
                # Keep set size manageable
                if len(self._error_messages) > 1000:
                    self._error_messages = set(list(self._error_messages)[-500:])
        except Exception as e:
            logger.error(f"Error sending error message: {str(e)}")
    
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
        temporal = nlp_result.get("temporal_context", {})
        if temporal.get("has_deadline"):
            if temporal.get("specific_day"):
                response_parts.append(f"\n_I've noted that this needs to be done by {temporal['specific_day']}._")
            elif temporal.get("timeframe"):
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
        
        response = "\n\n".join(response_parts)
        logger.info(f"Formatted response: {response}")
        return response
    
    async def start(self) -> None:
        """Start the Front Desk service."""
        try:
            self.running = True
            self.start_time = datetime.now()
            
            # Initialize bot info
            auth_test = await self.web_client.auth_test()
            self.bot_id = auth_test["user_id"]
            self.bot_mention = f"<@{self.bot_id}>"
            logger.info(f"Bot connected as: {self.bot_id} ({auth_test['user']})")
            
            # Initialize Socket Mode client
            self.socket_client = SocketModeClient(
                app_token=self.slack_app_token,
                web_client=self.web_client,
                auto_reconnect_enabled=True
            )
            
            # Register event handler
            self.socket_client.socket_mode_request_listeners.append(self.process_event)
            
            # List and join available channels
            channels = await self.web_client.conversations_list(types="public_channel,private_channel")
            for channel in channels["channels"]:
                logger.info(f"Found channel: {channel['name']} ({channel['id']})")
                try:
                    # Try to join each channel
                    await self.web_client.conversations_join(channel=channel["id"])
                    logger.info(f"Joined channel: {channel['name']}")
                except Exception as e:
                    logger.warning(f"Could not join channel {channel['name']}: {str(e)}")
            
            # Start Socket Mode client
            logger.info(f"{self.name} is now connecting via Socket Mode...")
            await self.socket_client.connect()
            logger.info(f"{self.name} is now online and listening for messages!")
            
            # Keep the connection alive
            while self.running:
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error starting Front Desk: {str(e)}")
            logger.exception(e)
            raise
        finally:
            if self.socket_client:
                await self.socket_client.close()
    
    async def stop(self) -> None:
        """Stop the Front Desk service."""
        self.running = False
        if self.socket_client:
            await self.socket_client.close()
        logger.info(f"{self.name} is now offline.") 