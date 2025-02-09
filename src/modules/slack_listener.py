#!/usr/bin/env python3

import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import signal
import sys
from datetime import datetime
from ..utils.logging import get_logger
from dotenv import load_dotenv
import time

logger = get_logger(__name__)

class SlackListener:
    def __init__(self):
        load_dotenv()
        self.bot_token = os.getenv('SLACK_BOT_TOKEN')
        self.client = WebClient(token=self.bot_token)
        self.running = False
        self.start_time = None
        self.last_timestamp = None
        self.channel_id = None
        
        # Initialize GPT handler
        from .gpt_handler import GPTHandler
        self.gpt = GPTHandler()
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def get_channel_id(self, channel_name):
        """Get channel ID from channel name"""
        try:
            # List all channels
            result = self.client.conversations_list()
            if result['ok']:
                for channel in result['channels']:
                    if channel['name'] == channel_name:
                        return channel['id']
            return None
        except SlackApiError as e:
            logger.error(f"Error getting channel ID: {str(e)}")
            return None

    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown on signals"""
        signal_name = 'SIGINT' if signum == signal.SIGINT else 'SIGTERM'
        logger.info(f"\n🛑 Received {signal_name} signal. Stopping listener gracefully...")
        self.stop()
        sys.exit(0)

    def handle_message(self, event):
        """Process incoming messages"""
        try:
            # Debug logging
            logger.info(f"Processing message event: {event}")
            
            # Skip if not a user message or missing required fields
            if not event.get('user') or not event.get('text'):
                return

            # Skip bot messages (both our own and other bots)
            if event.get('bot_id') or event.get('bot_profile'):
                return

            text = event['text']
            user = event.get('user', 'Unknown')
            
            # Get channel ID from the event or use the main channel
            channel_id = event.get('channel', self.channel_id)
            if not channel_id:
                logger.error("No channel ID available")
                return
            
            # Check for bot mention (using Slack's mention format)
            bot_info = self.client.auth_test()
            bot_id = f"<@{bot_info['user_id']}>"
            
            if bot_id not in text:
                return

            logger.info(f"Processing command from {user}: {text}")

            # Remove bot mention and any extra whitespace from the message
            clean_text = text.replace(bot_id, '').strip()

            # Handle special commands
            if clean_text.lower() == 'help':
                logger.info("Sending help message...")
                self.send_help_message(channel_id)
            elif clean_text.lower() == 'status':
                logger.info("Sending status...")
                self.send_status(channel_id)
            elif clean_text.lower() == 'stop':
                logger.info("Stopping bot...")
                self.send_message(channel_id, "👋 Shutting down listener. Goodbye!")
                self.stop()
            elif clean_text.lower() == 'clear':
                logger.info("Clearing conversation history...")
                self.gpt.clear_history(user)
                self.send_message(channel_id, "🧹 Conversation history cleared!")
            else:
                # Generate response using GPT
                logger.info("Generating GPT response...")
                response = self.gpt.generate_response(user, clean_text)
                self.send_message(channel_id, response)
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            if channel_id:
                self.send_message(channel_id, f"❌ Error processing command: {str(e)}")

    def send_help_message(self, channel_id):
        """Send help information"""
        bot_info = self.client.auth_test()
        bot_id = f"<@{bot_info['user_id']}>"
        help_text = f"""*Available Commands:*
• `{bot_id} help` - Show this help message
• `{bot_id} status` - Check my current status
• `{bot_id} clear` - Clear conversation history
• `{bot_id} stop` - Stop the listener

You can also chat with me naturally! Just mention me and ask anything. 💬
Examples:
• `{bot_id} What can you help me with?`
• `{bot_id} How do I organize my tasks?`
• `{bot_id} Can you help me draft an email?`

I'll use AI to provide helpful responses! 🤖✨"""
        self.send_message(channel_id, help_text)

    def send_status(self, channel_id):
        """Send current status"""
        uptime = datetime.now() - self.start_time
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        status_text = f"""*Current Status:*
• 🟢 Active and listening
• ⏱️ Uptime: {hours}h {minutes}m
• 📍 Monitoring channel: #aphro-agent-chat"""
        self.send_message(channel_id, status_text)

    def send_message(self, channel_id, text):
        """Send a message to a channel"""
        try:
            self.client.chat_postMessage(
                channel=channel_id,
                text=text
            )
        except SlackApiError as e:
            logger.error(f"Error sending message: {str(e)}")

    def poll_messages(self):
        """Poll for new messages in the channel"""
        try:
            if not self.channel_id:
                return
                
            # Get messages from the aphro-agent-chat channel
            result = self.client.conversations_history(
                channel=self.channel_id,
                limit=5,  # Only get recent messages
                oldest=self.last_timestamp if self.last_timestamp else str(self.start_time.timestamp())
            )
            
            if result['ok'] and result['messages']:
                # Update last seen timestamp
                self.last_timestamp = result['messages'][0]['ts']
                
                # Process messages in reverse (oldest first)
                for message in reversed(result['messages']):
                    # Only process user messages (not bot messages)
                    if message.get('user') and not message.get('bot_id') and not message.get('bot_profile'):
                        self.handle_message(message)
                    
        except SlackApiError as e:
            logger.error(f"Error polling messages: {str(e)}")

    def start(self):
        """Start the listener"""
        if self.running:
            logger.warning("Listener is already running!")
            return

        try:
            # Get channel ID first
            self.channel_id = self.get_channel_id('aphro-agent-chat')
            if not self.channel_id:
                logger.error("Could not find #aphro-agent-chat channel!")
                return
                
            self.running = True
            self.start_time = datetime.now()
            logger.info("🎧 Starting Slack listener...")
            
            # Send startup message
            self.send_message(self.channel_id, "🟢 AphroAgent is now online and listening for commands!")
            
            # Main listening loop
            while self.running:
                try:
                    self.poll_messages()
                    time.sleep(1)  # Poll every second
                except SlackApiError as e:
                    logger.error(f"Slack API error in main loop: {str(e)}")
                    # Don't stop on API errors, just log and continue
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error in main loop: {str(e)}")
                    self.send_message(self.channel_id, "⚠️ Encountered an error, but trying to stay online!")
                    continue
                    
        except Exception as e:
            logger.error(f"Critical error in listener: {str(e)}")
            self.running = False
            if hasattr(self, 'channel_id') and self.channel_id:
                self.send_message(self.channel_id, "❌ Critical error occurred, shutting down. Check the logs for details.")

    def stop(self):
        """Stop the listener"""
        if not self.running:
            return

        try:
            logger.info("Stopping listener...")
            self.running = False
            if hasattr(self, 'channel_id') and self.channel_id:
                self.send_message(self.channel_id, "🛑 Shutting down by request. Goodbye!")
            logger.info("✨ Slack listener stopped successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")

def main():
    """Main entry point for running the listener"""
    listener = SlackListener()
    listener.start()

if __name__ == "__main__":
    main() 