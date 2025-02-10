#!/usr/bin/env python3

import asyncio
import logging
from src.office.utils.logging_config import setup_logging
from src.office.reception.front_desk import FrontDesk

async def main():
    """Run the Front Desk service."""
    # Set up logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Start the Front Desk
        logger.info("Starting Front Desk service...")
        front_desk = FrontDesk()
        front_desk.start()
        
        # Keep the service running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down Front Desk service...")
    except Exception as e:
        logger.error(f"Error in Front Desk service: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 