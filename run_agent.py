#!/usr/bin/env python3

import argparse
from src.modules.slack_listener import SlackListener
from src.utils.logging import get_logger

logger = get_logger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Control AphroAgent Slack interface')
    parser.add_argument('action', choices=['start', 'stop'], help='Action to perform')
    
    args = parser.parse_args()
    
    listener = SlackListener()
    
    if args.action == 'start':
        logger.info("🚀 Starting AphroAgent...")
        logger.info("💡 Use '@AphroAgent help' in Slack to see available commands")
        logger.info("💡 Press Ctrl+C to stop the agent")
        listener.start()
    else:
        logger.info("🛑 Stopping AphroAgent...")
        listener.stop()

if __name__ == "__main__":
    main() 