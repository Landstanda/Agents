#!/usr/bin/env python3

from src.modules.slack_integration import SlackModule
from src.utils.logging import get_logger

logger = get_logger(__name__)

def test_slack():
    """Test Slack integration"""
    try:
        logger.info("Initializing Slack Module...")
        slack_module = SlackModule()
        
        # Test listing channels
        logger.info("Testing channel listing...")
        result = slack_module.execute({'operation': 'list_channels'})
        
        if result and 'channels' in result:
            logger.info("✓ Successfully connected to Slack!")
            logger.info(f"✓ Found {len(result['channels'])} channels")
            for channel in result['channels']:
                logger.info(f"  - #{channel['name']}")
        else:
            logger.error("Failed to list channels")
            
    except Exception as e:
        logger.error(f"Slack test error: {str(e)}")
        
if __name__ == "__main__":
    test_slack() 