import os
import logging
import asyncio
from typing import Dict, Any, Optional, Set
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from src.models import Ticket, TicketStatus
from src.tools.agent import Agent
from src.tools.message_maker import MessageMaker
from src.tools.service_analyzer import ServiceAnalyzer
from src.utils.flow_logger import FlowLogger
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from datetime import datetime
import traceback
from dotenv import load_dotenv
import signal
from contextlib import AsyncExitStack

# Configure logging at the start of the program
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

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
        self.service_analyzer = None
        self.message_maker = None
        self.flow_logger = None
        self.bot_user_id = None
        self._exit_stack = AsyncExitStack()
        self._pending_tasks: Set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()
        
    def _track_task(self, task: asyncio.Task) -> None:
        """Track a pending task and remove it when done."""
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)
        
    async def setup(self):
        """Initialize components and authenticate with Slack."""
        try:
            # Initialize flow logger first
            self.flow_logger = FlowLogger()
            await self.flow_logger.setup()
            
            # Initialize service analyzer with flow logger
            self.service_analyzer = ServiceAnalyzer(flow_logger=self.flow_logger)
            
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
            
            # Register event handler
            self.socket_client.socket_mode_request_listeners.append(self.handle_socket_mode_request)
            logger.info("Event handlers registered")
            
        except Exception as e:
            logger.error(f"Error during setup: {str(e)}")
            await self.stop()  # Ensure cleanup on setup failure
            raise
            
    async def handle_socket_mode_request(self, client: SocketModeClient, req: SocketModeRequest) -> None:
        """Handle Socket Mode requests."""
        try:
            # Acknowledge the request first
            await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
            
            # Process the event if it exists
            if req.payload and "event" in req.payload:
                await self.process_event(req.payload["event"])
                
        except Exception as e:
            logger.error(f"Error handling socket mode request: {str(e)}", exc_info=True)
            
    async def process_event(self, event: dict) -> None:
        """Process a Slack event with task tracking."""
        # Create a task for event processing
        task = asyncio.create_task(self._process_event_internal(event))
        self._track_task(task)
        await task

    async def _process_event_internal(self, event: dict) -> None:
        """Internal event processing with timeout."""
        try:
            # Set a timeout for the entire event processing
            async with asyncio.timeout(30):  # 30 second timeout for event processing
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
                    event.get("bot_id") is not None or
                    event.get("user") == self.bot_user_id
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

                # Only process app_mention events
                if event.get("type") != "app_mention":
                    return

                message = event["text"]
                channel_id = event["channel"]
                user_info = {
                    "user_id": event["user"],
                    "channel_id": channel_id,
                    "thread_ts": event.get("thread_ts"),
                    "ts": event["ts"]
                }
                
                # Remove bot mention if present
                bot_mention = f"<@{self.bot_user_id}>"
                if bot_mention in message:
                    message = message.replace(bot_mention, "").strip()
                
                logger.info(f"Processing message: {message}")
                logger.info(f"Channel ID: {channel_id}")
                
                # Create ticket
                ticket = Ticket(
                    user_info=user_info,
                    original_message=message,
                    channel_id=channel_id,
                    thread_ts=event.get("thread_ts")
                )
                
                # Analyze the request using service analyzer
                ticket = await self.service_analyzer.analyze_request(ticket)
                
                # Execute the service if one was matched and all inputs are available
                if ticket.status == TicketStatus.EXECUTING:
                    logger.debug(f"Executing service plan: {ticket.execution_plan}")
                    agent = Agent(flow_logger=self.flow_logger)
                    await agent.initialize()
                    
                    # Send initial acknowledgment
                    initial_message = "I'm working on scheduling your dinner with Gabi. Let me take care of that for you."
                    ticket.add_message(initial_message, "assistant")
                    await self.web_client.chat_postMessage(
                        channel=ticket.channel_id,
                        text=initial_message,
                        thread_ts=ticket.thread_ts
                    )
                    
                    # Execute the service
                    result = await agent.execute_service(ticket)
                    if result.get('status') == 'error':
                        logger.error(f"Service execution failed: {result.get('error')}")
                        ticket.update_status(TicketStatus.ERROR)
                        ticket.add_error(result.get('error'), "execution_error")
                    else:
                        ticket.execution_results.append(result)
                        if result.get('status') == 'success':
                            ticket.update_status(TicketStatus.COMPLETED)
                    
                    # Send final response
                    await self.message_maker.send_message(ticket)
                else:
                    # For non-execution statuses (WAITING_INPUT, ERROR, etc.), send message immediately
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
                
        except asyncio.TimeoutError:
            logger.error("Event processing timed out")
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "OfficeAssistant",
                    "event_timeout",
                    {"event": event}
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
            
            # Process with service analyzer
            ticket = await self.service_analyzer.analyze_message(message, {"user_id": bot_user_id})
            
            # Log service analyzer processing result
            await self.flow_logger.log_event(
                "OfficeAssistant",
                "message_analysis",
                {"ticket": ticket}
            )
            
            response = None
            
            # Handle different ticket statuses
            if ticket.status == TicketStatus.EXECUTING:
                # Get the service
                service_name = ticket.service
                if service_name == "help":
                    response = {
                        "text": "Show me what commands and capabilities are available",
                        "params": {},
                        "use_gpt": True
                    }
                else:
                    # Initialize and set up agent
                    agent = Agent(flow_logger=self.flow_logger)
                    await agent.initialize()
                    service_response = await agent.execute_service(ticket)
                    response = {
                        "text": service_response.get("text", "Process the request and generate a friendly response"),
                        "params": service_response.get("params", {}),
                        "use_gpt": True
                    }
            elif ticket.status == TicketStatus.INCOMPLETE:
                # Format missing entities into a friendly request
                missing = ticket.missing_entities
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
            else:
                response = {
                    "text": "I'm not sure how to help with that request. Could you please rephrase it?",
                    "params": {},
                    "use_gpt": True
                }
            
            # Log response generation
            await self.flow_logger.log_event(
                "OfficeAssistant",
                "response_generation",
                {
                    "original_message": message,
                    "response_type": ticket.status,
                    "response": response
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            logger.error("Full exception details:", exc_info=True)
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "OfficeAssistant",
                    "message_processing_error",
                    {"error": str(e)}
                )
            return {
                "text": "I encountered an error while processing your request. Please try again.",
                "params": {},
                "use_gpt": True
            }
            
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
            
    async def stop(self, timeout: float = 5.0):
        """Graceful shutdown with timeout."""
        logger.info("Starting graceful shutdown...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel all pending tasks
        if self._pending_tasks:
            logger.info(f"Cancelling {len(self._pending_tasks)} pending tasks")
            for task in self._pending_tasks:
                task.cancel()
            
            # Wait for tasks with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._pending_tasks, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Some tasks did not complete within {timeout} seconds")
        
        # Close clients explicitly
        try:
            if self.socket_client:
                logger.info("Closing socket client...")
                await self.socket_client.disconnect()
                if hasattr(self.socket_client, 'client'):
                    await self.socket_client.client.close()
                self.socket_client = None
                
            if self.web_client:
                logger.info("Closing web client...")
                # AsyncWebClient doesn't need explicit cleanup
                self.web_client = None
                
            # Close OpenAI clients and their http clients
            if hasattr(self.service_analyzer, 'openai'):
                logger.info("Closing service analyzer OpenAI client...")
                if hasattr(self.service_analyzer.openai._client, 'aclose'):
                    await self.service_analyzer.openai._client.aclose()
                
            if hasattr(self.message_maker, 'openai'):
                logger.info("Closing message maker OpenAI client...")
                if hasattr(self.message_maker.openai._client, 'aclose'):
                    await self.message_maker.openai._client.aclose()
                
        except Exception as e:
            logger.error(f"Error closing clients: {e}")
            
        logger.info("Shutdown complete")

async def main():
    """Main entry point for the application."""
    assistant = None
    try:
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Get environment variables
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        app_token = os.getenv("SLACK_APP_TOKEN")
        
        if not slack_token or not app_token:
            raise ValueError("Missing required environment variables")
            
        # Initialize the assistant
        assistant = OfficeAssistant(slack_token, app_token)
        await assistant.setup()
        
        # Start the socket mode client
        await assistant.socket_client.connect()
        logger.info("Socket Mode client connected")
        
        # Create an event to handle shutdown
        shutdown_event = asyncio.Event()
        
        def signal_handler():
            logger.info("Received shutdown signal")
            shutdown_event.set()
            
        # Register signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().add_signal_handler(sig, signal_handler)
            
        # Keep the program running until shutdown event
        try:
            await shutdown_event.wait()
        except asyncio.CancelledError:
            pass
            
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        logger.error("Full exception details:", exc_info=True)
    finally:
        # Clean up signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().remove_signal_handler(sig)
            
        if assistant:
            logger.info("Cleaning up resources...")
            await assistant.stop()
            logger.info("Cleanup complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise 