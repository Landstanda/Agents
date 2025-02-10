#!/usr/bin/env python3

import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import signal
import sys
import asyncio
from datetime import datetime
from ..utils.logging import get_logger
from dotenv import load_dotenv
import time
import json

logger = get_logger(__name__)

class SlackListener:
    def __init__(self, brain=None):
        load_dotenv()
        self.bot_token = os.getenv('SLACK_BOT_TOKEN')
        
        # Initialize SlackModule for basic operations
        try:
            from .slack_integration import SlackModule
            self.slack_module = SlackModule()
            self.slack_module.initialize_client()  # This uses the bot token
            logger.debug("SlackModule initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SlackModule: {str(e)}")
            raise
            
        # Initialize brain if provided
        self.brain = None
        if brain is not None:
            try:
                logger.debug("Attempting to initialize brain...")
                self.brain = brain
                logger.debug(f"Brain initialized with {len(self.brain.modules) if hasattr(self.brain, 'modules') else 0} modules")
                if not hasattr(self.brain, 'process_request'):
                    raise ValueError("Brain instance missing required process_request method")
                logger.debug("Brain validation successful")
            except Exception as e:
                logger.error(f"Failed to initialize brain: {str(e)}")
                raise
        
        self.running = False
        self.start_time = None
        self.last_timestamp = None
        self.channel_id = None
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def get_channel_id(self, channel_name):
        """Get channel ID from channel name"""
        try:
            result = self.slack_module.execute({'operation': 'list_channels'})
            if result and 'channels' in result:
                for channel in result['channels']:
                    if channel['name'] == channel_name:
                        return channel['id']
            return None
        except Exception as e:
            logger.error(f"Error getting channel ID: {str(e)}")
            return None

    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown on signals"""
        signal_name = 'SIGINT' if signum == signal.SIGINT else 'SIGTERM'
        logger.info(f"\n🛑 Received {signal_name} signal. Stopping listener gracefully...")
        self.stop()
        sys.exit(0)

    async def handle_message(self, event):
        """Process incoming messages"""
        try:
            # Debug logging
            logger.info(f"Processing message event: {event}")
            
            # Skip if not a user message or missing required fields
            if not event.get('user') or not event.get('text'):
                return

            # Skip bot messages
            if event.get('bot_id') or event.get('bot_profile'):
                return

            text = event['text']
            user = event.get('user', 'Unknown')
            channel_id = event.get('channel', self.channel_id)
            
            if not channel_id:
                logger.error("No channel ID available")
                return
            
            # Check for bot mention
            bot_info = self.slack_module.client.auth_test()
            bot_id = f"<@{bot_info['user_id']}>"
            
            if bot_id not in text:
                return

            logger.info(f"Processing command from {user}: {text}")
            clean_text = text.replace(bot_id, '').strip()

            # Send acknowledgment message
            self.send_message(channel_id, "🤔 Processing your request...")

            # Handle basic commands
            if clean_text.lower() in ['help', 'hi', 'hello', '?']:
                self.send_help_message(channel_id)
                return
            elif clean_text.lower() == 'status':
                self.send_status(channel_id)
                return
            elif clean_text.lower() == 'stop':
                self.send_message(channel_id, "👋 Shutting down listener. Goodbye!")
                self.stop()
                return
            elif clean_text.lower() == 'capabilities':
                if self.brain:
                    capabilities = self.brain.get_capability_description()
                    self.send_message(channel_id, capabilities)
                else:
                    self.send_message(channel_id, "❌ Brain not initialized, capabilities not available.")
                return

            # If brain is available, use it. Otherwise, use simple echo response
            if self.brain:
                try:
                    context = {
                        'user': user,
                        'channel_id': channel_id,
                        'timestamp': event.get('ts'),
                        'thread_ts': event.get('thread_ts'),
                        'files': event.get('files', []),
                        'attachments': event.get('attachments', [])
                    }
                    
                    # Process request through brain
                    result = await self.brain.process_request(clean_text, context)
                    
                    if not result:
                        self.send_message(channel_id, "❌ Brain returned no response")
                        return
                        
                    # Handle different response formats
                    if isinstance(result, str):
                        self.send_message(channel_id, result)
                    elif isinstance(result, dict):
                        if result.get('status') == 'error':
                            error_msg = result.get('message', 'An unknown error occurred')
                            self.send_message(channel_id, f"❌ {error_msg}")
                        else:
                            # Format success response
                            response_parts = []
                            if result.get('message'):
                                response_parts.append(result['message'])
                            if result.get('data'):
                                if isinstance(result['data'], dict):
                                    for key, value in result['data'].items():
                                        if key != 'actions':  # Skip actions array
                                            response_parts.append(f"*{key}*: {value}")
                                else:
                                    response_parts.append(str(result['data']))
                            
                            response = "\n".join(response_parts) if response_parts else "✅ Request processed successfully"
                            self.send_message(channel_id, response)
                            
                            # Handle any actions
                            actions = result.get('data', {}).get('actions', [])
                            for action in actions:
                                if isinstance(action, dict) and action.get('type') == 'send_message':
                                    self.send_message(channel_id, action.get('text', ''))
                    else:
                        self.send_message(channel_id, f"✅ {str(result)}")
                        
                except Exception as brain_error:
                    logger.error(f"Brain processing error: {str(brain_error)}")
                    self.send_message(channel_id, f"❌ Brain processing error: {str(brain_error)}")
            else:
                # Simple echo response when brain is not available
                self.send_message(channel_id, f"Echo (no brain): {clean_text}")
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            if channel_id:
                self.send_message(channel_id, f"❌ Error: {str(e)}")

    async def poll_messages(self):
        """Poll for new messages in the channel"""
        try:
            if not self.channel_id:
                return
                
            # Get messages from the channel
            result = self.slack_module.client.conversations_history(
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
                        await self.handle_message(message)
                    
        except SlackApiError as e:
            logger.error(f"Error polling messages: {str(e)}")

    async def start(self):
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
                    await self.poll_messages()
                    await asyncio.sleep(1)
                except SlackApiError as e:
                    logger.error(f"Slack API error in main loop: {str(e)}")
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

    def send_message(self, channel_id, text):
        """Send a message to a channel"""
        try:
            self.slack_module.execute({
                'operation': 'send_message',
                'channel': channel_id,
                'text': text
            })
        except SlackApiError as e:
            logger.error(f"Error sending message: {str(e)}")

    def send_help_message(self, channel_id):
        """Send help information"""
        bot_info = self.slack_module.client.auth_test()
        bot_id = f"<@{bot_info['user_id']}>"
        
        help_text = f"""Hi! 👋 I'm your AI business assistant. Here's how I can help:

*Basic Commands:*
• `{bot_id} help` - Show this message
• `{bot_id} status` - Check if I'm working
• `{bot_id} capabilities` - Show detailed capabilities
• `{bot_id} stop` - Stop the listener

You can also chat with me naturally about your business needs! 💬
Examples:
• Check emails: "Can you check my emails?"
• Research: "Research AI trends in business"
• Documents: "Create a document about project status"
• Communication: "Send an update to the team"

I'll understand your request and use the appropriate capabilities to help you! 🤖✨"""

        if self.brain:
            help_text += "\n\n*Available Capabilities:*\n" + self.brain.get_capability_description()
        
        self.send_message(channel_id, help_text)

    def send_status(self, channel_id):
        """Send current status"""
        uptime = datetime.now() - self.start_time
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        
        status_text = f"""*Current Status:*
• 🟢 Active and listening
• ⏱️ Uptime: {hours}h {minutes}m"""

        if self.brain:
            status_text += f"\n• 🧠 Brain Status:\n"
            status_text += f"  - {len(self.brain.modules)} modules loaded\n"
            status_text += f"  - {len(self.brain.chains)} chains available"
        else:
            status_text += "\n• 🧠 Brain: Not connected"

        status_text += "\n• 📍 Monitoring channel: #aphro-agent-chat"
        
        self.send_message(channel_id, status_text)

def main():
    """Main entry point for running the listener"""
    try:
        from .brain import Brain
        brain = Brain()  # Initialize the brain
        logger.info("Brain initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize brain: {str(e)}")
        brain = None
        
    listener = SlackListener(brain=brain)
    asyncio.run(listener.start())

if __name__ == "__main__":
    main() 