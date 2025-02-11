#!/usr/bin/env python3

import asyncio
import logging
from pathlib import Path
from datetime import datetime
import signal
import os
import sys
from src.office.utils.logging_config import setup_logging
from src.office.reception.front_desk import FrontDesk

# Initialize logging first
logger = setup_logging()

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
        logger.info("Starting Front Desk service...")
        
        # Initialize flow logger with error handling
        try:
            flow_logger = FlowEventLogger()
            logger.info("Flow logger initialized successfully")
            
            # Print the location of log files for easy access
            logger.info(f"Flow logs will be written to: {flow_logger.log_dir.absolute()}")
            logger.info(f"General logs will be written to: {Path('logs').absolute()}")
            
        except Exception as e:
            logger.error(f"Failed to initialize flow logger: {str(e)}")
            logger.exception(e)  # Add full stack trace
            logger.error("Continuing without flow logging...")
            flow_logger = None
        
        # Register signal handlers
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
        
        # Start the Front Desk with flow logger
        front_desk = FrontDesk()
        if flow_logger:
            logger.info("Attaching flow logger to components...")
            # Attach flow logger to all components
            front_desk.flow_logger = flow_logger
            front_desk.nlp.flow_logger = flow_logger
            front_desk.cookbook.flow_logger = flow_logger
            front_desk.task_manager.flow_logger = flow_logger
            front_desk.ceo.flow_logger = flow_logger
            front_desk.request_tracker.flow_logger = flow_logger
            logger.info("Flow logger attached to all components successfully")
            
            # Verify flow logger attachment with a test event
            try:
                await flow_logger.log_event(
                    "System",
                    "Initialization",
                    {
                        "status": "initialized",
                        "components": [
                            "FrontDesk",
                            "NLPProcessor",
                            "CookbookManager",
                            "TaskManager",
                            "CEO",
                            "RequestTracker"
                        ],
                        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "log_directory": str(flow_logger.log_dir.absolute())
                    }
                )
                logger.info("Successfully wrote test event to flow log")
            except Exception as e:
                logger.error(f"Failed to write test event: {str(e)}")
                logger.exception(e)
        
        await front_desk.start()
            
    except KeyboardInterrupt:
        logger.info("Shutting down Front Desk service...")
    except Exception as e:
        logger.error(f"Error in Front Desk service: {str(e)}")
        logger.exception(e)
        raise
    finally:
        if front_desk:
            if flow_logger:
                try:
                    await flow_logger.log_event(
                        "System",
                        "Shutdown",
                        {
                            "status": "shutting_down",
                            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            "reason": "user_requested" if isinstance(sys.exc_info()[0], KeyboardInterrupt) else "error"
                        }
                    )
                except Exception as log_error:
                    logger.error(f"Error logging shutdown event: {str(log_error)}")
            await front_desk.stop()

if __name__ == "__main__":
    asyncio.run(main()) 