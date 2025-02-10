#!/usr/bin/env python3

import asyncio
import logging
from src.office.utils.logging_config import setup_logging
from slack_sdk.web import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
import os
from dotenv import load_dotenv

# Set up logging
logger = setup_logging()

async def test_slack_connection():
    """Test both sending and receiving messages via Slack."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Initialize Slack clients
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        app_token = os.getenv("SLACK_APP_TOKEN")
        
        if not bot_token or not app_token:
            raise ValueError("Missing Slack tokens in environment variables")
        
        web_client = WebClient(token=bot_token)
        socket_client = SocketModeClient(
            app_token=app_token,
            web_client=web_client
        )
        
        # Test sending a message
        logger.info("Testing message sending...")
        
        # First, get bot's user ID
        bot_info = web_client.auth_test()
        bot_user_id = bot_info["user_id"]
        logger.info(f"Bot user ID: {bot_user_id}")
        
        # List channels and join them if needed
        channel_response = web_client.conversations_list(types="public_channel,private_channel")
        if not channel_response["channels"]:
            raise ValueError("No channels found")
        
        test_channel = None
        for channel in channel_response["channels"]:
            try:
                # Try to join the channel
                web_client.conversations_join(channel=channel["id"])
                test_channel = channel["id"]
                logger.info(f"Joined channel: {channel['name']}")
                break
            except Exception as e:
                logger.warning(f"Could not join channel {channel['name']}: {str(e)}")
                continue
        
        if not test_channel:
            raise ValueError("Could not find or join any channels")
        
        # Send test message
        message_response = web_client.chat_postMessage(
            channel=test_channel,
            text="🔍 Testing Slack connection... If you see this message, sending works!"
        )
        
        logger.info(f"Test message sent to channel {test_channel}")
        
        # Test receiving messages
        logger.info("Testing message receiving (Socket Mode)...")
        
        async def process_message(client: SocketModeClient, req: SocketModeRequest):
            if req.type == "events_api":
                # Acknowledge the request
                response = SocketModeResponse(envelope_id=req.envelope_id)
                await client.send_socket_mode_response(response)
                
                # Process the event
                event = req.payload["event"]
                if event["type"] == "message" and "subtype" not in event:
                    logger.info(f"Received message: {event.get('text', '')}")
                    
                    # Don't reply to our own messages
                    if event.get("user") != bot_user_id:
                        # Reply to show we received it
                        web_client.chat_postMessage(
                            channel=event["channel"],
                            thread_ts=event["ts"],
                            text="👋 I received your message! (Test successful)"
                        )
        
        # Register event handler
        socket_client.socket_mode_request_listeners.append(process_message)
        
        # Connect and wait
        socket_client.connect()
        logger.info("Socket Mode client connected. Waiting for messages...")
        logger.info("Send a message in Slack to test the connection (waiting 30 seconds)...")
        
        # Keep the connection open for a while
        await asyncio.sleep(30)
        
    except Exception as e:
        logger.error(f"Error testing Slack connection: {str(e)}")
        raise
    finally:
        # Clean up
        if 'socket_client' in locals():
            socket_client.close()

if __name__ == "__main__":
    asyncio.run(test_slack_connection()) 