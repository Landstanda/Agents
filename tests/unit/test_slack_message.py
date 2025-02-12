#!/usr/bin/env python3

from src.modules.slack_integration import SlackModule
from src.utils.logging import get_logger

logger = get_logger(__name__)

def setup_agent_interface():
    """Set up the main interface channel for AphroAgent"""
    try:
        logger.info("=== Setting up AphroAgent Interface ===")
        slack_module = SlackModule()
        
        # Create the main interface channel
        channel_name = "aphro-agent-chat"
        create_result = slack_module.execute({
            'operation': 'create_channel',
            'name': channel_name
        })
        
        if create_result and 'channel_id' in create_result:
            logger.info(f"✓ Successfully created channel #{channel_name}")
            
            # Send welcome message
            welcome_message = {
                'operation': 'send_message',
                'channel': f'#{channel_name}',
                'text': """🎉 *Welcome to AphroAgent's Command Center!*

You can interact with me here by typing commands or questions. For example:
• `@AphroAgent help` - Show available commands
• `@AphroAgent status` - Check system status
• `@AphroAgent task create` - Create a new task

I'll be monitoring this channel 24/7 and will respond to your requests promptly! 

💡 *Pro tip:* Star this channel for quick access from your Slack sidebar."""
            }
            
            result = slack_module.execute(welcome_message)
            if result and 'message_ts' in result:
                logger.info("✓ Welcome message sent successfully!")
                
            logger.info("\n✨ Agent interface setup completed successfully!")
            logger.info(f"👉 Please join #{channel_name} to start interacting with AphroAgent")
            
    except Exception as e:
        logger.error(f"Setup error: {str(e)}")
        
if __name__ == "__main__":
    setup_agent_interface() 