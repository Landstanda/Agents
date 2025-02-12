#!/usr/bin/env python3

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from examples.slack_to_drive_chain import SlackToDriveChain
from src.utils.logging import get_logger
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize logging
logger = get_logger(__name__)

# Initialize Slack app with Socket Mode
app = App(token=os.environ["SLACK_BOT_TOKEN"])
chain = SlackToDriveChain()

@app.event("message")
def handle_message_events(event, say):
    """Handle incoming message events"""
    try:
        # Check if message contains a file
        if "files" in event:
            logger.info(f"Received message with file: {event.get('text', '')}")
            
            # Process each file in the message
            for file in event["files"]:
                # Prepare message data for our chain
                message_data = {
                    'channel': event['channel'],
                    'text': event.get('text', ''),
                    'file': {
                        'id': file['id'],
                        'name': file['name']
                    }
                }
                
                # Process the file using our chain
                result = chain.process_message(message_data)
                
                if not result['success']:
                    logger.error(f"Failed to process file: {result.get('error')}")
                    say(f"Failed to process file: {result.get('error')}")
                else:
                    logger.info(f"Successfully processed file: {result['web_link']}")
    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        logger.error(error_msg)
        say(error_msg)

if __name__ == "__main__":
    try:
        # Start the app using Socket Mode
        handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
        logger.info("Starting Slack file handler...")
        handler.start()
    except Exception as e:
        logger.error(f"Failed to start app: {str(e)}") 