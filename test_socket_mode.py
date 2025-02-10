#!/usr/bin/env python3

import asyncio
import logging
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
import os
from dotenv import load_dotenv
import json

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Store bot ID globally
BOT_ID = None

async def process_event(client: SocketModeClient, req: SocketModeRequest):
    """Process incoming Socket Mode events."""
    try:
        # Always acknowledge the request first
        await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
        
        # Log ALL incoming events for debugging
        logger.info("----------------------------------------")
        logger.info(f"Received event type: {req.type}")
        logger.info(f"Full payload: {json.dumps(req.payload, indent=2)}")
        
        if req.type == "events_api":
            event = req.payload["event"]
            event_type = event.get("type")
            logger.info(f"Event type: {event_type}")
            
            # Skip messages from the bot itself
            if event.get("user") == BOT_ID:
                logger.info("Skipping message from myself")
                return
                
            # Handle message events
            if event_type == "message":
                text = event.get("text", "")
                logger.info(f"Received message: {text}")
                
                # Get channel info for logging
                channel_id = event.get("channel")
                if channel_id:
                    try:
                        channel_info = await client.web_client.conversations_info(channel=channel_id)
                        channel_name = channel_info["channel"]["name"]
                        logger.info(f"Message was in channel: {channel_name}")
                        
                        # Only respond if the bot was mentioned
                        if f"<@{BOT_ID}>" in text:
                            response = await client.web_client.chat_postMessage(
                                channel=channel_id,
                                text=f"👋 I saw you mention me! (Test response)\nYour message: {text}",
                                thread_ts=event.get("thread_ts", event.get("ts"))
                            )
                            logger.info("Sent response to mention")
                    except Exception as e:
                        logger.error(f"Error handling message: {str(e)}")
            
            # Handle explicit mentions
            elif event_type == "app_mention":
                logger.info(f"Received app_mention event: {event.get('text', '')}")
                channel_id = event.get("channel")
                if channel_id:
                    try:
                        response = await client.web_client.chat_postMessage(
                            channel=channel_id,
                            text="👋 I received your mention via Socket Mode! (Test response)",
                            thread_ts=event.get("thread_ts", event.get("ts"))
                        )
                        logger.info("Sent response to app_mention")
                    except Exception as e:
                        logger.error(f"Error responding to mention: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        logger.exception(e)

async def test_socket_mode():
    """Test Socket Mode connectivity."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Get tokens
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        app_token = os.getenv("SLACK_APP_TOKEN")
        
        if not bot_token or not app_token:
            raise ValueError("Missing required Slack tokens in .env file")
            
        logger.info("Tokens loaded successfully")
        logger.info(f"Bot token starts with: {bot_token[:10]}...")
        logger.info(f"App token starts with: {app_token[:10]}...")
        
        # Initialize clients
        web_client = AsyncWebClient(token=bot_token)
        socket_client = SocketModeClient(
            app_token=app_token,
            web_client=web_client,
            auto_reconnect_enabled=True
        )
        
        # Get and store bot info
        auth_test = await web_client.auth_test()
        global BOT_ID
        BOT_ID = auth_test["user_id"]
        
        logger.info("=== Bot Information ===")
        logger.info(f"Bot ID: {BOT_ID}")
        logger.info(f"Bot Name: {auth_test['user']}")
        logger.info(f"Bot Mention String: <@{BOT_ID}>")
        
        # List all channels the bot is in
        channels = await web_client.conversations_list()
        logger.info("\n=== Channels ===")
        for channel in channels["channels"]:
            if channel["is_member"]:
                logger.info(f"Bot is in channel: {channel['name']} ({channel['id']})")
        
        # Register event handler
        socket_client.socket_mode_request_listeners.append(process_event)
        
        # Start Socket Mode client
        logger.info("\n=== Starting Socket Mode ===")
        await socket_client.connect()
        logger.info("Socket Mode client connected! Waiting for events...")
        logger.info("Send a message mentioning the bot to test the connection")
        
        # Keep the connection alive
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Error in Socket Mode test: {str(e)}")
        logger.exception(e)
        raise
    finally:
        if 'socket_client' in locals():
            await socket_client.close()

if __name__ == "__main__":
    try:
        asyncio.run(test_socket_mode())
    except KeyboardInterrupt:
        logger.info("Test script stopped by user") 