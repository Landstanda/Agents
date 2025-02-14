import os
import logging
import asyncio
from typing import Dict, Any, Optional
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from src.tools.nlp import NLPAnalyzer
from src.tools.agent import Agent
from src.tools.message_maker import MessageMaker
from src.tools.service_maker import ServiceMaker
from src.utils.flow_logger import FlowLogger
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from datetime import datetime
import traceback
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class OfficeAssistant:
    """
    Main application class that integrates all components
    for Slack interaction.
    """
    
    def __init__(self, slack_token: str, app_token: str):
        """Initialize the Office Assistant."""
        self.slack_token = slack_token
        self.app_token = app_token
        self.web_client = AsyncWebClient(token=slack_token)
        self.socket_client = None
        self.nlp = None
        self.message_maker = None
        self.flow_logger = None
        self.bot_user_id = None
        
    async def setup(self):
        """Initialize components and authenticate with Slack."""
        try:
            # Initialize flow logger first
            self.flow_logger = FlowLogger()
            
            # Initialize NLP analyzer with flow logger
            self.nlp = await NLPAnalyzer.create(flow_logger=self.flow_logger)
            
            # Initialize message maker with the slack token
            self.message_maker = MessageMaker(flow_logger=self.flow_logger, slack_token=self.slack_token)
            
            # Authenticate with Slack
            auth_test = await self.web_client.auth_test()
            self.bot_user_id = auth_test["user_id"]
            
            await self.flow_logger.log_event(
                "OfficeAssistant",
                "initialization_complete",
                {"bot_user_id": self.bot_user_id}
            )
            
            # Initialize Socket Mode client
            self.socket_client = SocketModeClient(
                app_token=self.app_token,
                web_client=self.web_client
            )
            
            # Register event handlers
            self.socket_client.socket_mode_request_listeners.append(self.process_event)
            logger.info("Event handlers registered")
            
        except Exception as e:
            logger.error(f"Error during setup: {str(e)}")
            raise
            
    async def process_event(self, client, req: SocketModeRequest):
        """Process a Socket Mode request."""
        try:
            # Extract event from request payload
            event = req.payload.get("event", {})
            
            # Acknowledge the request first
            await self.socket_client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
            
            # Log event details
            logger.info(f"Processing event: {event}")
            await self.flow_logger.log_event(
                "OfficeAssistant",
                "event_details",
                {
                    "event_type": event.get("type"),
                    "user": event.get("user"),
                    "text": event.get("text"),
                    "channel": event.get("channel"),
                    "ts": event.get("ts"),
                    "thread_ts": event.get("thread_ts"),
                    "full_event": event
                }
            )
            
            # Skip bot messages and message subtypes
            if (
                "text" not in event or
                event.get("subtype") is not None or
                event.get("bot_id") is not None or  # Skip bot messages
                event.get("user") == self.bot_user_id  # Skip own messages
            ):
                logger.info(f"Skipping event: has_text={'text' in event}, subtype={event.get('subtype')}, bot_id={event.get('bot_id')}")
                await self.flow_logger.log_event(
                    "OfficeAssistant",
                    "event_skipped",
                    {
                        "reason": "Not a valid user message",
                        "has_text": "text" in event,
                        "subtype": event.get("subtype"),
                        "bot_id": event.get("bot_id"),
                        "user": event.get("user")
                    }
                )
                return

            # Only process app_mentions or direct messages
            bot_mention = f"<@{self.bot_user_id}>"
            is_bot_mentioned = bot_mention in event.get("text", "")
            
            if event.get("type") == "message" and not is_bot_mentioned:
                # Skip regular messages that don't mention the bot
                return
            elif event.get("type") not in ["message", "app_mention"]:
                # Skip other event types
                return

            # Only process message events once (skip app_mention if we've seen the message)
            if event.get("type") == "app_mention" and event.get("ts") in getattr(self, "_processed_messages", set()):
                logger.info(f"Skipping duplicate app_mention event: {event.get('ts')}")
                return
                
            # Track processed messages
            if not hasattr(self, "_processed_messages"):
                self._processed_messages = set()
            self._processed_messages.add(event.get("ts"))
            
            # Keep set size manageable
            if len(self._processed_messages) > 1000:
                self._processed_messages = set(list(self._processed_messages)[-1000:])
            
            message = event["text"]
            channel_id = event["channel"]
            user_info = {
                "user_id": event["user"],
                "channel_id": channel_id,
                "thread_ts": event.get("thread_ts"),
                "ts": event["ts"]
            }
            
            # Remove bot mention if present
            if bot_mention in message:
                message = message.replace(bot_mention, "").strip()
            
            logger.info(f"Processing message: {message}")
            logger.info(f"Channel ID: {channel_id}")
            
            # Analyze the message
            ticket = await self.nlp.analyze_message(message, user_info)
            
            # Generate and send response
            await self.message_maker.send_message(ticket)
            
            # Log success
            await self.flow_logger.log_event(
                "OfficeAssistant",
                "message_processed",
                {
                    "message": message,
                    "channel_id": channel_id,
                    "user_id": user_info["user_id"],
                    "ticket_id": ticket.ticket_id
                }
            )
            
        except Exception as e:
            logger.error(f"Error processing event: {str(e)}")
            logger.error("Full exception details:", exc_info=True)
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "OfficeAssistant",
                    "event_processing_error",
                    {"error": str(e)}
                )
            
    async def process_message(self, message: str) -> Dict[str, Any]:
        """Process a message and return a response."""
        try:
            # Log incoming message
            await self.flow_logger.log_event(
                "OfficeAssistant",
                "incoming_message",
                {
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # Get bot info for user context
            auth_test = await self.web_client.auth_test()
            bot_user_id = auth_test["user_id"]
            
            # Remove bot mention if present
            bot_mention = f"<@{bot_user_id}>"
            if bot_mention in message:
                message = message.replace(bot_mention, "").strip()
            
            # Process with NLP
            nlp_result = await self.nlp.analyze_message(message, {"user_id": bot_user_id})
            
            # Log NLP processing result
            await self.flow_logger.log_event(
                "OfficeAssistant",
                "message_analysis",
                {"nlp_result": nlp_result}
            )
            
            response = None
            
            # Handle different NLP result statuses
            if nlp_result.get("status") == "matched":
                # Get the service
                service_name = nlp_result.get("service")
                if service_name == "help":
                    response = {
                        "text": "Show me what commands and capabilities are available",
                        "params": {},
                        "use_gpt": True
                    }
                else:
                    service_response = await self.agent.execute_service(nlp_result)
                    response = {
                        "text": service_response.get("text", "Process the request and generate a friendly response"),
                        "params": service_response.get("params", {}),
                        "use_gpt": True
                    }
            elif nlp_result.get("status") == "incomplete":
                # Format missing entities into a friendly request
                missing = nlp_result.get("missing_entities", [])
                if missing:
                    missing_str = ", ".join(missing)
                    response = {
                        "text": f"Ask the user to provide {missing_str} for their request",
                        "params": {},
                        "use_gpt": True
                    }
                else:
                    response = {
                        "text": "Ask the user for more details about their request",
                        "params": {},
                        "use_gpt": True
                    }
            elif nlp_result.get("status") == "unknown":
                response = {
                    "text": "Inform the user that I don't understand their request and suggest using the help command",
                    "params": {},
                    "use_gpt": True
                }
            
            # Log response generation
            await self.flow_logger.log_event(
                "OfficeAssistant",
                "response_generation",
                {
                    "original_message": message,
                    "nlp_status": nlp_result.get("status"),
                    "response_type": "direct" if nlp_result.get("status") == "matched" else "request_info",
                    "response": response
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            error_response = {
                "text": "Apologize to the user for encountering an error",
                "params": {},
                "use_gpt": True
            }
            
            # Log error
            await self.flow_logger.log_event(
                "OfficeAssistant",
                "processing_error",
                {
                    "error": str(e),
                    "original_message": message,
                    "response": error_response
                }
            )
            
            return error_response
            
    async def start(self):
        """Start the Socket Mode client."""
        try:
            await self.setup()
            await self.socket_client.connect()
            logger.info("Office Assistant is running!")
        except Exception as e:
            logger.error(f"Error running assistant: {str(e)}")
            if self.socket_client:
                await self.socket_client.close()
            raise
            
    async def stop(self):
        """Stop the Socket Mode client."""
        if self.socket_client:
            await self.socket_client.close()
            
async def main():
    """Main entry point."""
    try:
        # Get tokens from environment variables
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        app_token = os.getenv("SLACK_APP_TOKEN")
        
        if not slack_token or not app_token:
            raise ValueError("Missing required environment variables SLACK_BOT_TOKEN or SLACK_APP_TOKEN")
        
        assistant = OfficeAssistant(slack_token=slack_token, app_token=app_token)
        await assistant.start()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Error starting application: {str(e)}")
        raise
    finally:
        # Keep the event loop running
        while True:
            try:
                await asyncio.sleep(1)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the application
    asyncio.run(main()) 