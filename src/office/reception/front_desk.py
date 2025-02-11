from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.office.request_tracking.request import Request

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
from ..request_tracking.request import Request
from .request_tracker import RequestTracker
from ..executive.ceo import CEO
from .nlp_processor import NLPProcessor
from ..cookbook.cookbook_manager import CookbookManager
from ..task.task_manager import TaskManager
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class FrontDesk:
    """
    The Front Desk handles all Slack communication, acting as the office's voice.
    It maintains a professional and helpful tone while facilitating communication
    between users and other components. For known tasks, it handles them directly
    through the task manager. For unknown tasks, it consults the CEO.
    """
    
    def __init__(
        self,
        web_client: AsyncWebClient = None,
        socket_client: SocketModeClient = None,
        openai_client: AsyncOpenAI = None,
        nlp: NLPProcessor = None,
        cookbook: CookbookManager = None,
        task_manager: TaskManager = None,
        ceo: CEO = None,
        bot_id: str = None
    ):
        """Initialize the Front Desk with all necessary components."""
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
        self.web_client = web_client or AsyncWebClient(token=self.slack_bot_token)
        self.socket_client = socket_client
        self.openai_client = openai_client or AsyncOpenAI(api_key=self.openai_api_key)
        self.ceo = ceo or CEO()
        self.nlp = nlp or NLPProcessor()
        self.cookbook = cookbook or CookbookManager()
        self.task_manager = task_manager or TaskManager()
        self.request_tracker = RequestTracker()
        self.bot_id = bot_id
        self.bot_mention = f"<@{self.bot_id}>" if self.bot_id else None
        
        # Set up personality
        self.name = "Sarah"
        self.title = "Front Desk Manager"
        self.running = False
        self.start_time = None
        
        # Initialize message deduplication set
        self._processed_messages = set()
        self._error_messages = set()
        
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
        """
        Get a response from GPT-3.5-turbo with error handling and fallbacks.
        
        Args:
            prompt: The prompt to send to GPT
            
        Returns:
            str: The generated response or a fallback message if GPT fails
        """
        if not prompt:
            return None
            
        try:
            # Add retry logic for transient errors
            max_retries = 2
            retry_count = 0
            last_error = None
            
            while retry_count <= max_retries:
                try:
                    response = await self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are Sarah, a helpful and professional front desk manager. "
                                    "Respond directly in first person as Sarah. "
                                    "Keep responses concise, friendly, and under 50 words. "
                                    "Focus on being clear and helpful while maintaining a natural tone. "
                                    "Never use quotes or show instructions in the response. "
                                    "If asking for information, be specific about what you need."
                                )
                            },
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=100,
                        temperature=0.7,
                        presence_penalty=0.6,  # Encourage varied responses
                        n=1  # Ensure we only get one response
                    )
                    
                    if response and response.choices:
                        return response.choices[0].message.content.strip()
                    
                    logger.warning("Empty response from GPT")
                    break
                    
                except Exception as e:
                    last_error = str(e)
                    retry_count += 1
                    if retry_count <= max_retries:
                        logger.warning(f"GPT request failed, attempt {retry_count}/{max_retries}: {str(e)}")
                        await asyncio.sleep(1)  # Wait before retrying
                    else:
                        logger.error(f"All GPT retries failed: {str(e)}")
                        break
            
            # If we get here, we either got an empty response or used all retries
            return self._get_fallback_response(prompt)
            
        except Exception as e:
            logger.error(f"Error getting GPT response: {str(e)}")
            return self._get_fallback_response(prompt)
    
    def _get_fallback_response(self, prompt: str) -> str:
        """Generate a fallback response when GPT is unavailable."""
        # Extract key terms for basic response
        terms = prompt.lower()
        
        if "schedule" in terms and "meeting" in terms:
            return "I understand you want to schedule a meeting. Let me help you with that."
        elif "check" in terms and ("email" in terms or "emails" in terms):
            return "I understand you want to check your emails. I'll help you with that."
        elif "hi" in terms or "hello" in terms or "there" in terms:
            return "Hello! How can I help you today?"
        else:
            return "I understand your request and I'll help you with that. Let me process this for you."
    
    async def handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming Slack messages with intelligent routing."""
        request = None
        try:
            channel_id = message.get("channel")
            user_id = message.get("user")
            thread_ts = message.get("thread_ts") if message.get("thread_ts") else None
            text = message.get("text", "")
            if text and self.bot_mention:
                text = text.replace(self.bot_mention, "").strip()
            
            if not text or not user_id or not channel_id:
                return
            
            # Get user info
            try:
                user_info_response = await self.web_client.users_info(user=user_id)
                if user_info_response["ok"]:
                    user_info = user_info_response
                else:
                    user_info = {"user": {"real_name": "there", "id": user_id}}
            except Exception as e:
                logger.warning(f"Could not fetch user info: {str(e)}")
                user_info = {"user": {"real_name": "there", "id": user_id}}
            
            # Process with NLP
            nlp_result = await self.nlp.process_message(text, user_info["user"], channel_id)
            
            # For messages that don't need tracking (like greetings), handle directly
            if not nlp_result.get("needs_tracking", True):
                intent = nlp_result.get("intent")
                if intent == "help":
                    await self._send_help_message(channel_id, thread_ts)
                elif intent == "greeting":
                    greeting = await self.get_gpt_response(f"Generate a friendly greeting for {user_info['user']['real_name']}")
                    await self._send_message(channel_id, greeting, thread_ts)
                elif intent == "farewell":
                    farewell = await self.get_gpt_response(f"Generate a friendly goodbye for {user_info['user']['real_name']}")
                    await self._send_message(channel_id, farewell, thread_ts)
                elif intent == "gratitude":
                    response = await self.get_gpt_response(f"Generate a friendly response to {user_info['user']['real_name']}'s thanks")
                    await self._send_message(channel_id, response, thread_ts)
                elif intent == "pleasantry":
                    response = await self.get_gpt_response(f"Generate a friendly response to {user_info['user']['real_name']}'s pleasantry")
                    await self._send_message(channel_id, response, thread_ts)
                return
            
            # Create request for messages that need tracking
            request = self.request_tracker.create_request(channel_id, user_id, text)
            request.update(
                intent=nlp_result.get("intent"),
                entities={**request.entities, **nlp_result.get("entities", {})}
            )
            
            # Handle task-based requests
            if request.status == "new":
                # New request, try to find matching recipe
                cookbook_response = self.cookbook.get_recipe(request.intent)
                request.recipe = cookbook_response.get("recipe")
                request.missing_entities = cookbook_response.get("missing_requirements", [])
                
                if cookbook_response["status"] == "success":
                    request.status = "processing"
                    result = await self.task_manager.execute_recipe(request.recipe, {
                        "nlp_result": nlp_result,
                        "user_info": user_info,
                        "channel_id": channel_id,
                        "thread_ts": thread_ts,
                        **nlp_result.get("entities", {})  # Add entities directly to context
                    })
                    
                    if result["status"] == "error":
                        await self._handle_error(request, result["error"], channel_id, thread_ts)
                    else:
                        await self._handle_success(request, result, channel_id, thread_ts)
                    
                elif cookbook_response["status"] == "missing_info":
                    request.status = "waiting_for_info"
                    await self._request_missing_info(request, channel_id, thread_ts)
                
                else:  # not_found or error
                    await self._handle_unknown_request(request, channel_id, thread_ts)
            
            elif request.status == "waiting_for_info":
                # Check if missing info was provided
                still_missing = []
                for entity in request.missing_entities:
                    if not request.entities.get(entity):
                        still_missing.append(entity)
                
                if not still_missing:
                    # All required info provided, proceed with task
                    request.status = "processing"
                    result = await self.task_manager.execute_recipe(request.recipe, {
                        "nlp_result": {"intent": request.intent, "entities": request.entities},
                        "user_info": user_info,
                        "channel_id": channel_id,
                        "thread_ts": thread_ts,
                        **request.entities  # Add entities directly to context
                    })
                    
                    if result["status"] == "error":
                        await self._handle_error(request, result["error"], channel_id, thread_ts)
                    else:
                        await self._handle_success(request, result, channel_id, thread_ts)
                else:
                    # Still missing info, ask again
                    request.missing_entities = still_missing
                    await self._request_missing_info(request, channel_id, thread_ts)
        
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            logger.exception(e)
            if request:
                await self._handle_error(request, str(e), channel_id, thread_ts)

    async def _handle_error(self, request: 'Request', error: str, channel_id: str, thread_ts: Optional[str]):
        """Handle error in request processing."""
        request.status = "error"
        error_prompt = (
            f"I need to tell the user that I encountered an error while processing their "
            f"{request.intent} request. The error was: {error}. "
            f"Please format this as a friendly, professional message."
        )
        error_message = await self.get_gpt_response(error_prompt)
        request.add_message(error_message, is_user=False)
        await self._send_message(channel_id, error_message, thread_ts)
        self.request_tracker.update_request(request)

    async def _handle_success(self, request: 'Request', result: Dict[str, Any], channel_id: str, thread_ts: Optional[str]):
        """Handle successful request completion."""
        request.status = "completed"
        success_prompt = (
            f"I need to tell the user that I've completed their {request.intent} request. "
            f"Additional details: {result.get('details', '')}. "
            f"Please format this as a friendly, professional message."
        )
        success_message = await self.get_gpt_response(success_prompt)
        request.add_message(success_message, is_user=False)
        await self._send_message(channel_id, success_message, thread_ts)
        self.request_tracker.update_request(request)

    async def _request_missing_info(self, request: 'Request', channel_id: str, thread_ts: Optional[str]):
        """Request missing information from user."""
        missing_items = request.missing_entities
        info_prompt = (
            f"I need to ask the user for some additional information to help with their {request.intent} request. "
            f"I need the following details: {', '.join(missing_items)}. "
            f"Context from their previous messages: {[msg['message'] for msg in request.conversation_history if msg['is_user']]}. "
            f"Please format this as a friendly question, explaining why this information is needed."
        )
        info_request = await self.get_gpt_response(info_prompt)
        request.add_message(info_request, is_user=False)
        await self._send_message(channel_id, info_request, thread_ts)
        self.request_tracker.update_request(request)

    async def _handle_unknown_request(self, request: 'Request', channel_id: str, thread_ts: Optional[str]):
        """Handle unknown or invalid requests."""
        request.status = "error"
        help_prompt = (
            f"I need to tell the user that I couldn't understand their request "
            f"and suggest they try rephrasing it or use the help command to see what I can do."
        )
        help_message = await self.get_gpt_response(help_prompt)
        request.add_message(help_message, is_user=False)
        await self._send_message(channel_id, help_message, thread_ts)
        self.request_tracker.update_request(request)
    
    def _check_missing_entities(self, recipe: Dict[str, Any], entities: Dict[str, Any]) -> List[str]:
        """Check which required entities are missing from the user's message."""
        required = set(recipe.get("required_entities", []))
        provided = set(entities.keys())
        return list(required - provided)
    
    async def _send_help_message(self, channel_id: str, thread_ts: Optional[str] = None) -> None:
        """Send help information."""
        help_prompt = (
            "I need to provide a help message that explains what I can do. "
            "Please include that I can help with scheduling meetings, checking emails, and other tasks. "
            "Also mention that users can chat with me naturally by mentioning me. "
            "Format this as a friendly, professional message with emojis."
        )
        help_text = await self.get_gpt_response(help_prompt)
        if not help_text:
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
            status_prompt = (
                f"I need to provide a status message. Here are the details:\n"
                f"- I'm active and listening\n"
                f"- I've been running for {hours}h {minutes}m\n"
                f"- I'm part of a team with {self.name} (Front Desk) & Michael (CEO)\n"
                f"- I'm using Socket Mode for processing\n"
                f"Please format this as a friendly status update with emojis."
            )
            status_text = await self.get_gpt_response(status_prompt)
            if not status_text:
                status_text = f"""*Current Status:*
• 🟢 Active and listening
• ⏱️ Uptime: {hours}h {minutes}m
• 👥 Team: {self.name} (Front Desk) & Michael (CEO)
• 🔄 Processing: Socket Mode"""
        else:
            status_text = await self.get_gpt_response("I need to inform the user that status information is not available. Keep it brief.")
            if not status_text:
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
            
        error_prompt = (
            "I need to send an error message to the user. Please include:\n"
            "- An apology for the error\n"
            "- That I've logged it and will improve\n"
            "- Suggestions like:\n"
            "  • Rephrasing the request\n"
            "  • Using simpler language\n"
            "  • Breaking it into smaller parts\n"
            "  • Using the help command\n"
            "Format this as a friendly, professional message."
        )
        message = await self.get_gpt_response(error_prompt)
        if not message:
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
    
    def _format_task_response(self, execution_result: Dict[str, Any], recipe: Dict[str, Any], user_name: str) -> str:
        """Format response for tasks handled directly by the task manager."""
        response_parts = [f"Hi {user_name}!"]
        
        if execution_result["status"] == "success":
            response_parts.append(f"I've completed your request using our {recipe['name']} process.")
            if execution_result.get("details"):
                response_parts.append(execution_result["details"])
        else:
            response_parts.append(
                f"I encountered an issue while handling your request: {execution_result.get('error', 'Unknown error')}"
            )
        
        return "\n\n".join(response_parts)
    
    def _format_ceo_response(self, ceo_response: Dict[str, Any], nlp_result: Dict[str, Any], user_name: str) -> str:
        """Format response for tasks handled by the CEO."""
        response_parts = [f"Hi {user_name}!"]
        
        if ceo_response["status"] == "success":
            response_parts.append(ceo_response["decision"])
            
            if ceo_response.get("new_recipe"):
                response_parts.append(
                    "_I've created a new process for handling this type of request, "
                    "so I'll be able to help you even faster next time!_"
                )
        else:
            response_parts.append(
                f"I apologize, but I encountered an issue while processing your request: {ceo_response.get('notes', 'Unknown error')}"
            )
        
        return "\n\n".join(response_parts)
    
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
    
    async def _send_message(self, channel_id: str, text: str, thread_ts: Optional[str] = None) -> None:
        """Send a message to Slack."""
        try:
            # Create a unique key for this message
            message_key = f"{channel_id}:{thread_ts}:{text}"
            if message_key in self._processed_messages:
                logger.debug(f"Skipping duplicate message: {message_key}")
                return
                
            await self.web_client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_ts
            )
            
            # Add to processed messages
            self._processed_messages.add(message_key)
            if len(self._processed_messages) > 1000:
                self._processed_messages = set(list(self._processed_messages)[-500:])
                
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}") 