#!/usr/bin/env python3

import asyncio
import logging
import os
from pathlib import Path
from datetime import datetime
import signal
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from openai import AsyncOpenAI
from src.utils.flow_logger import FlowLogger

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create logs directory
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logger.info(f"Log directory created/verified at: {log_dir.absolute()}")

# Add file handlers for different log levels
debug_log = log_dir / f"front_desk_debug_{datetime.now().strftime('%Y%m%d')}.log"
error_log = log_dir / f"front_desk_error_{datetime.now().strftime('%Y%m%d')}.log"

debug_handler = logging.FileHandler(debug_log)
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

error_handler = logging.FileHandler(error_log)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logger.addHandler(debug_handler)
logger.addHandler(error_handler)

logger.info("Logging system initialized")
logger.info(f"Debug log: {debug_log}")
logger.info(f"Error log: {error_log}")

# Import our modules after logging is set up
from src.office.reception.front_desk import FrontDesk
from src.office.reception.nlp_processor import NLPProcessor
from src.office.cookbook.cookbook_manager import CookbookManager
from src.office.task.task_manager import TaskManager
from src.office.executive.ceo import CEO

class FlowEventLogger:
    def __init__(self):
        self.subscribers = []
        self.log_dir = Path("logs/flow_logs")
        
        # Create logs directory if it doesn't exist
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Flow logs directory initialized at {self.log_dir.absolute()}")
            
            # Create the session log file with initialization time
            init_time = datetime.now()
            self.log_file = self.log_dir / f"log_{init_time.strftime('%I%M%p').lower()}_{init_time.strftime('%b%d')}.txt"
            
            # Write session start header
            with open(self.log_file, "w", encoding='utf-8') as f:
                f.write(f"{'='*80}\n")
                f.write(f"Session Started: {init_time.strftime('%I:%M:%S %p %b %d, %Y')}\n")
                f.write(f"{'='*80}\n\n")
            
            logger.info(f"Session log file created at {self.log_file.absolute()}")
            
        except Exception as e:
            logger.error(f"Error creating logs directory: {str(e)}")
            raise
        
    def subscribe(self, component):
        """Subscribe a component to receive flow events."""
        self.subscribers.append(component)
        logger.info(f"Component subscribed to flow logger: {component.__class__.__name__}")
        
    async def log_event(self, component: str, event_type: str, details: dict):
        """Log a flow event to the session log file."""
        try:
            # Format the log entry
            timestamp = datetime.now().strftime('%I:%M:%S %p')
            log_entry = f"\n{'='*80}\n"
            log_entry += f"[{timestamp}] {component} - {event_type}\n"
            log_entry += f"{'-'*40}\n"
            
            # Add details with proper formatting
            for key, value in details.items():
                if isinstance(value, dict):
                    log_entry += f"{key}:\n"
                    for k, v in value.items():
                        log_entry += f"  - {k}: {v}\n"
                elif isinstance(value, list):
                    log_entry += f"{key}:\n"
                    for item in value:
                        log_entry += f"  - {item}\n"
                else:
                    log_entry += f"{key}: {value}\n"
            
            # Write to session log file with error handling
            try:
                with open(self.log_file, "a", encoding='utf-8') as f:
                    f.write(log_entry)
                logger.info(f"Successfully logged flow event: {component} - {event_type}")
            except Exception as e:
                logger.error(f"Error writing to flow log file: {str(e)}")
                # Try to create a backup log
                backup_file = self.log_dir / f"log_backup_{datetime.now().strftime('%I%M%p').lower()}_{datetime.now().strftime('%b%d')}.txt"
                with open(backup_file, "w", encoding='utf-8') as f:
                    f.write(log_entry)
                logger.error(f"Flow event written to backup file: {backup_file.absolute()}")
                
        except Exception as e:
            logger.error(f"Error in flow logger: {str(e)}")
            logger.exception(e)

# Global instances
front_desk = None
flow_logger = None

def handle_shutdown(signum, frame):
    """Handle graceful shutdown on signals."""
    global front_desk
    if front_desk:
        logger.info("Shutdown signal received, stopping Front Desk...")
        front_desk.running = False

async def main():
    """Run the Front Desk service."""
    global front_desk, flow_logger
    
    try:
        # Load environment variables
        load_dotenv()
        
        # Initialize components
        web_client = AsyncWebClient(token=os.getenv("SLACK_BOT_TOKEN"))
        socket_client = SocketModeClient(
            app_token=os.getenv("SLACK_APP_TOKEN"),
            web_client=web_client
        )
        openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Initialize flow logger
        flow_logger = FlowLogger()
        
        # Create core components
        nlp = NLPProcessor(flow_logger=flow_logger)
        cookbook = CookbookManager()
        task_manager = TaskManager()
        ceo = CEO(cookbook_manager=cookbook, task_manager=task_manager)
        
        # Create front desk
        front_desk = FrontDesk(
            web_client=web_client,
            socket_client=socket_client,
            openai_client=openai_client,
            nlp=nlp,
            cookbook=cookbook,
            task_manager=task_manager,
            ceo=ceo
        )
        front_desk.flow_logger = flow_logger
        
        # Set up socket mode handler
        socket_client.socket_mode_request_listeners.append(front_desk.process_event)
        
        # Start the client
        await socket_client.connect()
        logger.info("Front Desk is running!")
        
        # Keep the connection alive
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        logger.exception(e)
        raise

if __name__ == "__main__":
    asyncio.run(main()) 