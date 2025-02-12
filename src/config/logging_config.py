import logging
import sys
from pathlib import Path
from datetime import datetime

def setup_logging():
    """Set up logging configuration."""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    try:
        log_dir.mkdir(exist_ok=True)
        print(f"Log directory created/verified at: {log_dir.absolute()}")
    except Exception as e:
        print(f"Error creating log directory: {str(e)}")
        raise
    
    # Create a detailed formatter for file logging
    file_formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create a simpler formatter for console output
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set up console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Set up main debug log file
    debug_log = log_dir / f"front_desk_debug_{datetime.now().strftime('%Y%m%d')}.log"
    debug_handler = logging.FileHandler(debug_log)
    debug_handler.setFormatter(file_formatter)
    debug_handler.setLevel(logging.DEBUG)
    
    # Set up error log file
    error_log = log_dir / f"front_desk_error_{datetime.now().strftime('%Y%m%d')}.log"
    error_handler = logging.FileHandler(error_log)
    error_handler.setFormatter(file_formatter)
    error_handler.setLevel(logging.ERROR)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add our handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(debug_handler)
    root_logger.addHandler(error_handler)
    
    # Create a logger for this module
    logger = logging.getLogger(__name__)
    
    # Log initial information about log files
    logger.info("Logging system initialized")
    logger.info(f"Debug log: {debug_log.absolute()}")
    logger.info(f"Error log: {error_log.absolute()}")
    
    return logger 