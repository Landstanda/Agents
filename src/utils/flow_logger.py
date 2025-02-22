import logging
import json
from typing import Dict, Any
from datetime import datetime
import os
from pathlib import Path
import aiofiles

logger = logging.getLogger(__name__)

class FlowLogger:
    """Logs events and their details for tracking system flow."""
    
    def __init__(self):
        """Initialize the flow logger."""
        # Set up log directory
        self.base_log_dir = Path("logs")
        self.flow_log_dir = self.base_log_dir / "flow_logs"
        
        # Create directories if they don't exist
        self.base_log_dir.mkdir(exist_ok=True)
        self.flow_log_dir.mkdir(exist_ok=True)
        
        # Set up current log file
        self.current_log_file = None
        
    async def setup(self):
        """Async setup of the logger."""
        await self._setup_log_file()
        
    async def _setup_log_file(self):
        """Set up the current log file with timestamp."""
        timestamp = datetime.now().strftime("%I%M%p_%b%d")
        self.current_log_file = self.flow_log_dir / f"log_{timestamp}.txt"
        
        # Write header if new file
        if not self.current_log_file.exists():
            async with aiofiles.open(self.current_log_file, 'w') as f:
                await f.write(f"================================================================================\n")
                await f.write(f"Session Started: {datetime.now().strftime('%I:%M:%S %p %b %d, %Y')}\n")
                await f.write(f"================================================================================\n\n")
    
    async def log_event(self, component: str, event_type: str, details: Dict[str, Any]) -> None:
        """
        Log an event with details.
        
        Args:
            component: Name of the component logging the event
            event_type: Type of event being logged
            details: Additional details about the event
        """
        try:
            # Ensure we have the correct log file for current time
            await self._setup_log_file()
            
            # Format the event
            event = {
                'timestamp': datetime.now().isoformat(),
                'component': component,
                'event_type': event_type,
                'details': details
            }
            
            # Write to console log
            logger.info(json.dumps(event))
            
            # Write to file with improved formatting
            async with aiofiles.open(self.current_log_file, 'a') as f:
                await f.write(f"\n{'='*80}\n")
                await f.write(f"[{datetime.now().strftime('%I:%M:%S %p')}] {component} - {event_type}\n")
                await f.write(f"{'-'*80}\n")
                
                # Format details based on event type
                if event_type == "incoming_message":
                    await f.write(f"Incoming Message: \"{details.get('message', '')}\"\n")
                
                elif event_type == "nlp_processing":
                    await f.write(f"Original Message: \"{details.get('original_message', '')}\"\n")
                    await f.write(f"Intent: {details.get('intent', 'None')}\n")
                    await f.write(f"Status: {details.get('status', 'unknown')}\n")
                    await f.write("Entities Found:\n")
                    for key, value in details.get('entities', {}).items():
                        await f.write(f"  - {key}: {value}\n")
                    if details.get('missing_entities'):
                        await f.write("Missing Entities:\n")
                        for entity in details.get('missing_entities', []):
                            await f.write(f"  - {entity}\n")
                
                elif event_type == "response_generation":
                    await f.write(f"Original Message: \"{details.get('original_message', '')}\"\n")
                    await f.write(f"Response Type: {details.get('response_type', 'unknown')}\n")
                    response = details.get('response', {})
                    if isinstance(response, dict):
                        await f.write(f"Response Text: \"{response.get('text', '')}\"")
                        if response.get('params'):
                            await f.write("\nParameters:\n")
                            for key, value in response['params'].items():
                                await f.write(f"  - {key}: {value}\n")
                    else:
                        await f.write(f"Response: {response}\n")
                
                elif event_type == "response_sent":
                    await f.write(f"Channel: {details.get('channel', '')}\n")
                    await f.write(f"Message Sent: \"{details.get('text', '')}\"\n")
                
                elif event_type == "preparing_message":
                    await f.write(f"Channel: {details.get('channel', '')}\n")
                    await f.write(f"Original Text: \"{details.get('message_text', '')}\"\n")
                    if details.get('has_blocks'):
                        await f.write("Message includes blocks\n")
                
                elif event_type == "message_formatted":
                    await f.write(f"Original Text: \"{details.get('original_text', '')}\"\n")
                    await f.write(f"Formatted Text: \"{details.get('formatted_text', '')}\"\n")
                
                elif event_type == "message_sent":
                    await f.write(f"Channel: {details.get('channel', '')}\n")
                    await f.write(f"Final Message: \"{details.get('final_text', '')}\"\n")
                    await f.write(f"Send Status: {'Success' if details.get('response_ok') else 'Failed'}\n")
                
                else:
                    # Default formatting for other event types
                    for key, value in details.items():
                        await f.write(f"{key}: {json.dumps(value, indent=2)}\n")
                
                await f.write("\n")
                
        except Exception as e:
            logger.error(f"Error logging event: {str(e)}") 