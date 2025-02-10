import logging
import sys
import os

def setup_logging():
    """Configure logging for the application."""
    # Create logs directory if it doesn't exist
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create console handler with a higher log level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Create file handler which logs even debug messages
    log_file = os.path.join(logs_dir, 'front_desk.log')
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)

    # Create formatters and add them to the handlers
    console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    console_handler.setFormatter(console_format)
    file_handler.setFormatter(file_format)

    # Remove any existing handlers to avoid duplicate logging
    logger.handlers.clear()

    # Add the handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger 