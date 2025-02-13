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

logger = logging.getLogger(__name__)

class OfficeAssistant:
    """
    Main application class that integrates all components
    for Slack interaction.
    """
    
    def __init__(self, slack_token: Optional[str] = None, app_token: Optional[str] = None):
        """Initialize the Office Assistant."""
        self.slack_token = slack_token or os.getenv("SLACK_BOT_TOKEN")
        self.app_token = app_token or os.getenv("SLACK_APP_TOKEN")
        
        if not self.slack_token or not self.app_token:
            raise ValueError("Missing Slack tokens in environment variables")
            
        # Initialize components
        self.web_client = AsyncWebClient(token=self.slack_token)
        self.flow_logger = None
        self.nlp = None  # Will be initialized in setup()
        self.agent = None  # Will be initialized in setup()
        self.message_maker = None  # Will be initialized in setup()
        self.service_maker = None  # Will be initialized in setup()
        self.socket_client = None
        
    async def setup(self):
        """Set up components that require async initialization."""
        try:
            # Initialize flow logger first
            self.flow_logger = FlowLogger()
            await self.flow_logger.log_event(
                "OfficeAssistant",
                "initialization_start",
                {"timestamp": datetime.now().isoformat()}
            )
            
            # Initialize components with flow logger
            self.nlp = await NLPAnalyzer.create(flow_logger=self.flow_logger)
            
            self.agent = Agent(flow_logger=self.flow_logger)
            await self.agent.load_services()
            
            self.message_maker = MessageMaker(
                web_client=self.web_client,
                flow_logger=self.flow_logger
            )
            
            self.service_maker = ServiceMaker(flow_logger=self.flow_logger)
            
            # Initialize Socket Mode client
            self.socket_client = SocketModeClient(
                app_token=self.app_token,
                web_client=self.web_client
            )
            
            # Add event handler
            self.socket_client.socket_mode_request_listeners.append(self.process_event)
            
            # Test auth
            auth_test = await self.web_client.auth_test()
            logger.info(f"Connected as: {auth_test['user']} ({auth_test['user_id']})")
            
            await self.flow_logger.log_event(
                "OfficeAssistant",
                "initialization_complete",
                {
                    "bot_user": auth_test['user'],
                    "bot_user_id": auth_test['user_id']
                }
            )
            
        except Exception as e:
            logger.error(f"Error during setup: {str(e)}")
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "OfficeAssistant",
                    "initialization_error",
                    {"error": str(e)}
                )
            raise
            
    async def process_event(self, client: SocketModeClient, req: SocketModeRequest):
        """Process Socket Mode events."""
        try:
            # Acknowledge the request
            response = SocketModeResponse(envelope_id=req.envelope_id)
            await client.send_socket_mode_response(response)
            
            # Process the event
            event = req.payload["event"]
            
            # Skip bot messages and message subtypes
            if (
                event.get("type") != "message" or
                "text" not in event or
                event.get("subtype") is not None or
                event.get("bot_id") is not None or  # Skip bot messages
                event.get("user") == self.web_client.token.split('-')[1]  # Skip own messages
            ):
                return
                
            message = event["text"]
            channel_id = event["channel"]
            
            # Process the message and get response
            response = await self.process_message(message)
            
            # Log the response we're about to send
            await self.flow_logger.log_event(
                "OfficeAssistant",
                "sending_response",
                {"response": response}
            )
            
            # Format and send the response using MessageMaker
            if isinstance(response, dict):
                if "text" in response and "params" in response:
                    await self.message_maker.send_message(
                        channel=channel_id,
                        text=response
                    )
                else:
                    await self.message_maker.send_message(
                        channel=channel_id,
                        text=response.get("text", str(response))
                    )
            else:
                await self.message_maker.send_message(
                    channel=channel_id,
                    text=str(response)
                )
            
        except Exception as e:
            logger.error(f"Error processing event: {str(e)}")
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
            
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error running assistant: {str(e)}")
        finally:
            if self.socket_client:
                await self.socket_client.close()
                
    async def stop(self):
        """Stop the Socket Mode client."""
        if self.socket_client:
            await self.socket_client.close()
            
async def main():
    """Main entry point."""
    try:
        assistant = OfficeAssistant()
        await assistant.start()
    except Exception as e:
        logger.error(f"Error starting application: {str(e)}")
        raise

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the application
    asyncio.run(main()) 