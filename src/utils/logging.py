import logging
from typing import Optional

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get a logger with consistent formatting.
    
    Args:
        name: Name for the logger (usually __name__)
        level: Optional logging level (defaults to DEBUG if not set)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if level is not None:
        logger.setLevel(level)
    elif not logger.level:
        logger.setLevel(logging.DEBUG)
    
    # Add handler if none exists
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger 