import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

class FlowLogger:
    """Simple logger for tracking flow of events through the system."""
    
    def __init__(self):
        """Initialize the flow logger."""
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        self.flow_log_path = self.log_dir / "flow.log"
        
        # Set up file handler
        self.file_handler = logging.FileHandler(self.flow_log_path)
        self.file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(self.file_handler)
    
    async def log_event(self, component: str, event_type: str, details: Dict[str, Any]) -> None:
        """Log an event with details."""
        try:
            event = {
                "timestamp": datetime.now().isoformat(),
                "component": component,
                "event_type": event_type,
                "details": details
            }
            
            logger.info(json.dumps(event))
            
        except Exception as e:
            logger.error(f"Error logging event: {str(e)}")
            logger.exception(e) 