import os
import logging
import asyncio
from typing import Dict, Any, Optional, Set
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from src.core.orchestrator import RequestOrchestrator
from src.utils.flow_logger import FlowLogger
from datetime import datetime
from dotenv import load_dotenv
import signal
from contextlib import AsyncExitStack

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class OfficeAssistant:
    """Main application class for Slack integration"""
    
    def __init__(self, slack_token: str, app_token: str):
        """Initialize the Office Assistant"""
        self.slack_token = slack_token
        self.app_token = app_token
        self.web_client = AsyncWebClient(token=slack_token)
        self.socket_client = None
        self.bot_user_id = None
        self._exit_stack = AsyncExitStack()
        self._pending_tasks: Set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()
        
        # Initialize components
        self.flow_logger = FlowLogger()
        self.orchestrator = RequestOrchestrator(flow_logger=self.flow_logger)
        
    def _track_task(self, task: asyncio.Task) -> None:
        """Track a pending task and remove it when done"""
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)
        
    async def setup(self):
        """Initialize components and authenticate with Slack"""
        try:
            # Initialize flow logger
            await self.flow_logger.setup()
            
            # Initialize orchestrator
            await self.orchestrator.initialize()
            
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
            await self.stop()
            raise
            
    async def handle_socket_mode_request(self, client: SocketModeClient, req: SocketModeRequest) -> None:
        """Handle Socket Mode requests"""
        try:
            # Acknowledge the request first
            await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
            
            # Process the event if it exists
            if req.payload and "event" in req.payload:
                await self.process_event(req.payload["event"])
                
        except Exception as e:
            logger.error(f"Error handling socket mode request: {str(e)}", exc_info=True)
            
    async def process_event(self, event: dict) -> None:
        """Process a Slack event with task tracking"""
        task = asyncio.create_task(self._process_event_internal(event))
        self._track_task(task)
        await task

    async def _process_event_internal(self, event: dict) -> None:
        """Internal event processing with timeout"""
        try:
            async with asyncio.timeout(30):  # 30 second timeout
                # Skip non-message or bot events
                if not self._should_process_event(event):
                    return

                # Extract message details
                message = self._clean_message(event.get("text", ""))
                user_info = {
                    "user_id": event["user"],
                    "channel_id": event["channel"],
                    "thread_ts": event.get("thread_ts"),
                    "ts": event["ts"]
                }
                
                # Process through orchestrator
                await self.orchestrator.process_request(
                    message=message,
                    user_info=user_info,
                    channel_id=event["channel"],
                    thread_ts=event.get("thread_ts")
                )
                
        except asyncio.TimeoutError:
            logger.error("Event processing timed out")
                await self.flow_logger.log_event(
                    "OfficeAssistant",
                    "event_timeout",
                    {"event": event}
                )
        except Exception as e:
            logger.error(f"Error processing event: {str(e)}", exc_info=True)
                await self.flow_logger.log_event(
                    "OfficeAssistant",
                    "event_processing_error",
                    {"error": str(e)}
                )
            
    def _should_process_event(self, event: dict) -> bool:
        """Determine if an event should be processed"""
        return (
            event.get("type") == "app_mention"
            and "text" in event
            and event.get("subtype") is None
            and event.get("bot_id") is None
            and event.get("user") != self.bot_user_id
        )
        
    def _clean_message(self, message: str) -> str:
        """Clean bot mention from message"""
        bot_mention = f"<@{self.bot_user_id}>"
        return message.replace(bot_mention, "").strip()
            
    async def start(self):
        """Start the Socket Mode client"""
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
        """Graceful shutdown with timeout"""
        logger.info("Starting graceful shutdown...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel pending tasks
        if self._pending_tasks:
            logger.info(f"Cancelling {len(self._pending_tasks)} pending tasks")
            for task in self._pending_tasks:
                task.cancel()
            
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._pending_tasks, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Some tasks did not complete within {timeout} seconds")
        
        # Close clients
        await self._close_clients()
            
    async def _close_clients(self):
        """Close all clients"""
        try:
            if self.socket_client:
                logger.info("Closing socket client...")
                await self.socket_client.disconnect()
                if hasattr(self.socket_client, 'client'):
                    await self.socket_client.client.close()
                self.socket_client = None
                
            if hasattr(self.orchestrator.service_analyzer, 'openai'):
                logger.info("Closing OpenAI clients...")
                if hasattr(self.orchestrator.service_analyzer.openai._client, 'aclose'):
                    await self.orchestrator.service_analyzer.openai._client.aclose()
                
        except Exception as e:
            logger.error(f"Error closing clients: {e}")

async def main():
    """Main entry point"""
    assistant = None
    try:
        # Get environment variables
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        app_token = os.getenv("SLACK_APP_TOKEN")
        
        if not slack_token or not app_token:
            raise ValueError("Missing required environment variables")
            
        # Initialize and run assistant
        assistant = OfficeAssistant(slack_token, app_token)
        await assistant.start()
        
        # Handle shutdown
        shutdown_event = asyncio.Event()
        
        def signal_handler():
            logger.info("Received shutdown signal")
            shutdown_event.set()
            
        # Register signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().add_signal_handler(sig, signal_handler)
            
        try:
            await shutdown_event.wait()
        except asyncio.CancelledError:
            pass
            
    except Exception as e:
        logger.error(f"Application error: {str(e)}", exc_info=True)
    finally:
        # Clean up
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().remove_signal_handler(sig)
            
        if assistant:
            await assistant.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise 