import logging
import json
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
from pathlib import Path
import aiofiles
import asyncio

logger = logging.getLogger(__name__)

class FlowLogger:
    """Logs events and their details for tracking system flow."""
    
    def __init__(self, log_dir: str = "logs"):
        """Initialize the flow logger with a log directory."""
        self.log_dir = log_dir
        self.history = []  # Store events as a list
        self.events = self.history  # For backward compatibility
        self.errors = []  # Store errors as a list
        self._initialized = False
        self.max_history_size = 1000
        self.current_log_file = None
        
    async def setup(self):
        """Initialize the logger."""
        if not self._initialized:
            os.makedirs(self.log_dir, exist_ok=True)
            await self._setup_log_file()
            self._initialized = True

    async def _setup_log_file(self):
        """Set up the log file with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_log_file = os.path.join(self.log_dir, f"flow_{timestamp}.log")
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)s %(name)s:%(filename)s:%(lineno)d %(message)s',
            handlers=[logging.FileHandler(self.current_log_file), logging.StreamHandler()]
        )

    async def log_event(self, component: str, event_type: str, data: Dict[str, Any] = None) -> None:
        """Log an event with its details."""
        if not self._initialized:
            await self.setup()

        timestamp = datetime.now().isoformat()
        
        # Make event type unique for concurrent logging
        task = asyncio.current_task()
        task_id = id(task) if task else 0
        unique_event_type = f"{event_type}_{task_id}"
        
        event = {
            "timestamp": timestamp,
            "component": component,
            "type": unique_event_type,  # Use unique event type
            "data": data or {}
        }
        
        # Store event in memory
        if len(self.history) >= self.max_history_size:
            # Remove oldest events when limit is reached
            self.history = self.history[-(self.max_history_size - 1):]
        
        self.history.append(event)
        
        # Log to file
        logging.info(json.dumps(event))

    async def log_error(self, component: str, message: str, error_type: str, exc_info: Optional[Exception] = None) -> None:
        """Log an error event."""
        timestamp = datetime.now().isoformat()
        
        error_details = {
            "timestamp": timestamp,
            "component": component,
            "type": error_type,
            "message": message
        }
        
        if exc_info:
            error_details["stack_trace"] = "".join(traceback.format_exception(type(exc_info), exc_info, exc_info.__traceback__))
            
        self.errors.append(error_details)
        
        # Log error as event
        await self.log_event(
            component=component,
            event_type=error_type,
            data={"message": message, "error_type": error_type, "stack_trace": error_details.get("stack_trace", "")}
        )

    def get_recent_events(self, count: int = 100) -> List[Dict[str, Any]]:
        """Get the most recent events."""
        events = sorted(self.history, key=lambda x: x["timestamp"], reverse=True)
        return events[:count]

    def get_component_history(self, component: str) -> List[Dict[str, Any]]:
        """Get history for a specific component."""
        events = [event for event in self.history if event["component"] == component]
        return sorted(events, key=lambda x: x["timestamp"], reverse=True)

    def get_error_history(self) -> List[Dict[str, Any]]:
        """Get the error history."""
        return sorted(self.errors, key=lambda x: x["timestamp"], reverse=True)

    def clear_history(self) -> None:
        """Clear all stored events and errors."""
        self.history = []
        self.events = self.history  # Keep events in sync
        self.errors = [] 