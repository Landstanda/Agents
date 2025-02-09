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
import json

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
            bot_info = self.client.auth_test()
            bot_id = f"<@{bot_info['user_id']}>"
            
            if bot_id not in text:
                return

            logger.info(f"Processing command from {user}: {text}")
            clean_text = text.replace(bot_id, '').strip().lower()

            # Handle basic commands
            if clean_text in ['help', 'hi', 'hello', '?']:
                self.send_help_message(channel_id)
                return
            elif clean_text == 'status':
                self.send_status(channel_id)
                return
            elif clean_text == 'stop':
                self.send_message(channel_id, "👋 Shutting down listener. Goodbye!")
                self.stop()
                return
            elif clean_text == 'clear':
                self.gpt.clear_history(user)
                self.send_message(channel_id, "🧹 Conversation history cleared!")
                return

            # Handle natural language commands
            if any(phrase in clean_text for phrase in ['remember this', 'save this', 'update context']):
                self._handle_context_update(channel_id, clean_text)
            elif any(phrase in clean_text for phrase in ['create board', 'make board', 'new board']):
                self._handle_create_board(channel_id, text)
            elif any(phrase in clean_text for phrase in ['add task', 'create task', 'new task']):
                self._handle_add_tasks(channel_id, text)
            elif 'what do you know about' in clean_text:
                self._handle_context_query(channel_id, clean_text)
            elif 'show progress' in clean_text or 'show accomplishments' in clean_text:
                self._handle_show_progress(channel_id)
            else:
                # Use GPT for general responses
                response = self.gpt.generate_response(user, clean_text)
                self.send_message(channel_id, response)
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            if channel_id:
                self.send_message(channel_id, f"❌ Error: {str(e)}")

    def _handle_context_update(self, channel_id: str, message: str):
        """Handle updating business context in a more natural way"""
        from .business_context import BusinessContextModule
        context_module = BusinessContextModule()
        
        # Extract the actual context (everything after the command words)
        for phrase in ['remember this:', 'save this:', 'update context:', 'remember this', 'save this', 'update context']:
            if phrase in message:
                context_text = message.split(phrase, 1)[1].strip()
                break
        else:
            context_text = message
        
        if not context_text:
            self.send_message(channel_id, "What would you like me to remember about the business?")
            return
            
        result = context_module.execute({
            'operation': 'import_context',
            'text': context_text
        })
        
        if 'error' in result:
            self.send_message(channel_id, f"❌ I had trouble understanding that. Could you rephrase it?")
        else:
            self.send_message(channel_id, "✅ I've updated my understanding of your business! I'll keep this in mind when helping you.")
            
    def _handle_context_query(self, channel_id: str, message: str):
        """Handle queries about stored business context"""
        from .business_context import BusinessContextModule
        context_module = BusinessContextModule()
        
        # Extract what they want to know about
        topic = message.replace('what do you know about', '').strip()
        
        result = context_module.execute({
            'operation': 'get_context',
            'section': topic if topic else None
        })
        
        if result and 'context' in result:
            context = result['context']
            response = self.gpt.generate_response('system', 
                f"Summarize this business information in a friendly, conversational way: {json.dumps(context)}")
            self.send_message(channel_id, response)
        else:
            self.send_message(channel_id, "I don't have any information about that yet. Feel free to tell me more!")
            
    def _handle_show_progress(self, channel_id: str):
        """Show business progress and accomplishments"""
        from .business_context import BusinessContextModule
        context_module = BusinessContextModule()
        
        result = context_module.execute({
            'operation': 'get_context',
            'section': None  # Get all context
        })
        
        if result and 'context' in result:
            context = result['context']
            prompt = """Create a progress report based on this business context. Include:
1. Recent accomplishments
2. Current phase/status
3. Next steps/goals
4. Any notable challenges or learnings

Make it encouraging and constructive!"""
            
            response = self.gpt.generate_response('system', 
                f"{prompt}\n\nContext: {json.dumps(context)}")
            self.send_message(channel_id, response)
        else:
            self.send_message(channel_id, "I don't have enough information yet. Tell me about your progress!")

    def send_help_message(self, channel_id):
        """Send help information"""
        bot_info = self.client.auth_test()
        bot_id = f"<@{bot_info['user_id']}>"
        help_text = f"""Hi! 👋 I'm your AI business assistant. Here's how I can help:

*Remembering Your Business Context:*
• "Remember this: [your business info]" - I'll remember details about your business
• "What do you know about [topic]?" - I'll tell you what I remember
• "Show progress" - I'll summarize your business progress

*Project Management:*
• "Create a board for [project name]" - I'll set up a Trello board
• "Add tasks about [topic]" - I'll create relevant tasks
• "Show my tasks" - I'll show your current tasks

*Basic Commands:*
• `{bot_id} help` - Show this message
• `{bot_id} status` - Check if I'm working
• `{bot_id} clear` - Clear our conversation history

You can also just chat with me naturally about your business! 💬
Examples:
• "Can you help me plan the next phase?"
• "What should I focus on next?"
• "How should I organize this project?"

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