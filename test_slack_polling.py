#!/usr/bin/env python3

import os
import time
from slack_sdk.web import WebClient
from dotenv import load_dotenv
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG level
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_slack_polling():
    """Test basic Slack message polling."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Initialize Slack client
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        if not bot_token:
            raise ValueError("SLACK_BOT_TOKEN not found in environment")
        
        web_client = WebClient(token=bot_token)
        
        # Get bot info
        auth_test = web_client.auth_test()
        bot_id = auth_test["user_id"]
        bot_mention = f"<@{bot_id}>"
        
        logger.info(f"Bot connected as: {auth_test['user_id']} ({auth_test['user']})")
        logger.info(f"Bot mention string: {bot_mention}")
        
        # Track last seen message
        last_ts = str(time.time() - 30)  # Start with messages from last 30 seconds
        logger.info(f"Starting timestamp: {last_ts} ({datetime.fromtimestamp(float(last_ts))})")
        
        while True:
            try:
                current_time = time.time()
                # List channels
                channels = web_client.conversations_list()["channels"]
                logger.debug(f"Found {len(channels)} channels")
                
                for channel in channels:
                    if not channel["is_member"]:
                        logger.debug(f"Skipping channel {channel['name']} (not a member)")
                        continue
                        
                    logger.info(f"Checking channel: {channel['name']} ({channel['id']})")
                    
                    try:
                        # Get messages
                        result = web_client.conversations_history(
                            channel=channel["id"],
                            oldest=last_ts,
                            limit=10  # Increased limit
                        )
                        
                        if result["ok"]:
                            messages = result.get("messages", [])
                            logger.debug(f"Found {len(messages)} messages in {channel['name']}")
                            
                            if messages:
                                # Update timestamp to the newest message
                                newest_ts = float(messages[0]["ts"])
                                if newest_ts > float(last_ts):
                                    last_ts = str(newest_ts)
                                    logger.debug(f"Updated last_ts to {last_ts} ({datetime.fromtimestamp(float(last_ts))})")
                                
                                # Check messages
                                for msg in messages:
                                    logger.debug(f"Checking message: {msg.get('text', '')}")
                                    if "text" in msg and bot_mention in msg["text"]:
                                        logger.info(f"Found mention in {channel['name']}: {msg['text']}")
                                        
                                        # Send test response
                                        response = web_client.chat_postMessage(
                                            channel=channel["id"],
                                            text=f"I saw your message at {datetime.now().strftime('%H:%M:%S')}! (Test response)\nMessage was: {msg['text']}",
                                            thread_ts=msg.get("thread_ts", msg["ts"])
                                        )
                                        logger.info(f"Sent response: {response['ts']}")
                        else:
                            logger.error(f"Error getting messages for {channel['name']}: {result.get('error', 'Unknown error')}")
                            
                    except Exception as e:
                        logger.error(f"Error processing channel {channel['name']}: {str(e)}")
                        continue
                
                # Wait before next poll
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in polling loop: {str(e)}")
                time.sleep(5)
                
    except Exception as e:
        logger.error(f"Error in test script: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        test_slack_polling()
    except KeyboardInterrupt:
        logger.info("Test script stopped by user") 