#!/usr/bin/env python3

import asyncio
import logging
import signal
from src.office.utils.logging_config import setup_logging
from src.office.reception.front_desk import FrontDesk

# Global front desk instance for signal handling
front_desk = None
logger = None

def handle_shutdown(signum, frame):
    """Handle graceful shutdown on signals."""
    global front_desk, logger
    if front_desk:
        if logger:
            logger.info("Shutdown signal received, stopping Front Desk...")
        front_desk.running = False

async def main():
    """Run the Front Desk service."""
    global front_desk, logger
    
    # Set up logging
    logger = setup_logging()
    
    try:
        # Register signal handlers
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
        
        # Start the Front Desk
        logger.info("Starting Front Desk service...")
        front_desk = FrontDesk()
        await front_desk.start()
            
    except KeyboardInterrupt:
        logger.info("Shutting down Front Desk service...")
    except Exception as e:
        logger.error(f"Error in Front Desk service: {str(e)}")
        logger.exception(e)
        raise
    finally:
        if front_desk:
            await front_desk.stop()

if __name__ == "__main__":
    asyncio.run(main()) 