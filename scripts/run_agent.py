#!/usr/bin/env python3

import argparse
import asyncio
import signal
import sys
from src.modules.slack_listener import SlackListener
from src.utils.logging import get_logger
from src.modules.brain import Brain

logger = get_logger(__name__)

async def start_agent():
    """Start the agent with brain initialization"""
    try:
        # Initialize brain first
        brain = Brain()
        
        # Validate brain initialization
        if not brain.modules:
            raise ValueError("Brain failed to load modules")
        if not brain.chains:
            raise ValueError("Brain failed to load chains")
        if not hasattr(brain, 'process_request'):
            raise ValueError("Brain missing process_request method")
            
        logger.info("🧠 Brain initialized successfully")
        logger.info(f"- Loaded {len(brain.modules)} modules")
        logger.info(f"- Loaded {len(brain.chains)} chain definitions")
        
        # Log loaded chains for debugging
        for chain_name, chain in brain.chains.items():
            logger.debug(f"Loaded chain: {chain_name} - {type(chain)}")
        
        # Initialize and start Slack listener with the brain instance
        listener = SlackListener(brain=brain)  # Pass the brain instance
        logger.info("🚀 Starting AphroAgent...")
        logger.info("💡 Use '@AphroAgent help' in Slack to see available commands")
        logger.info("💡 Press Ctrl+C to stop the agent")
        
        # Start the listener
        await listener.start()
        
    except Exception as e:
        logger.error(f"❌ Error starting agent: {str(e)}")
        sys.exit(1)

def stop_agent():
    """Stop the agent gracefully"""
    try:
        listener = SlackListener()
        logger.info("🛑 Stopping AphroAgent...")
        listener.stop()
        
    except Exception as e:
        logger.error(f"❌ Error stopping agent: {str(e)}")
        sys.exit(1)

def handle_shutdown(signum, frame):
    """Handle shutdown signals"""
    logger.info("\n🛑 Received shutdown signal. Stopping agent gracefully...")
    stop_agent()
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description='Control AphroAgent Slack interface')
    parser.add_argument('action', choices=['start', 'stop'], help='Action to perform')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    if args.debug:
        logger.setLevel('DEBUG')
    
    if args.action == 'start':
        # Run the async start function
        asyncio.run(start_agent())
    else:
        stop_agent()

if __name__ == "__main__":
    main() 