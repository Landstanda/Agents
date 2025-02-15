import logging
from typing import Optional

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get a logger with consistent formatting.
    
    Args:
        name: Name for the logger (usually __name__)
        level: Optional logging level (defaults to INFO if not set)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:  # Only add handler if none exists
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    if level is not None:
        logger.setLevel(level)
    elif not logger.level:  # Only set default level if not already set
        logger.setLevel(logging.INFO)
        
    return logger 