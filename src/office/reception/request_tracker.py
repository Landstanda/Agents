from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)

class Request:
    """Represents a user request being tracked."""
    
    def __init__(self, channel_id: str, user_id: str, text: str):
        """Initialize a new request."""
        self.id = str(uuid.uuid4())
        self.channel_id = channel_id
        self.user_id = user_id
        self.text = text
        self.status = "new"
        self.created_at = datetime.now().isoformat()
        self.last_updated = datetime.now()
        self.entities = {}
        self.intent = None
        self.messages = []
        self.add_message(text, is_user=True)
        
    def add_message(self, text: str, is_user: bool = True):
        """Add a message to the request history."""
        self.messages.append({
            "text": text,
            "is_user": is_user,
            "timestamp": datetime.now().isoformat()
        })
        self.last_updated = datetime.now()
        
    def update(self, **kwargs):
        """Update request attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        self.last_updated = datetime.now()
        
        # If request is completed, notify the tracker
        if self.status == "completed":
            if hasattr(self, '_request_tracker'):
                self._request_tracker._archive_request(self)
        
    def get_context_summary(self) -> Dict[str, Any]:
        """Get a summary of the request context for other components."""
        return {
            "request_id": self.id,
            "status": self.status,
            "intent": self.intent,
            "entities": self.entities,
            "priority": self.priority,
            "created_at": self.created_at,
            "last_updated": self.last_updated.isoformat(),
            "conversation_length": len(self.messages)
        }
        
    def mark_delegated(self, component: str):
        """Mark request as delegated to a specific component."""
        self.delegated_to = component
        self.add_message(f"Request delegated to {component}", is_user=False, source="system")
        
    def complete_with_data(self, data: Dict[str, Any]):
        """Complete the request with result data."""
        self.status = "completed"
        self.completion_data = data
        self.last_updated = datetime.now()
        
        # Archive the request if it has a tracker
        if hasattr(self, '_request_tracker'):
            self._request_tracker._archive_request(self)
            
class RequestTracker:
    """Manages and tracks user requests through their lifecycle."""
    
    def __init__(self):
        self.active_requests = {}  # channel_id -> {user_id -> Request}
        self.completed_requests = []
        self.request_timeout = timedelta(minutes=30)
        self.flow_logger = None  # Will be set by front_desk
    
    async def create_request(self, channel_id: str, user_id: str, text: str) -> Request:
        """Create a new request."""
        request = Request(channel_id, user_id, text)
        
        # Initialize channel dict if not exists
        if channel_id not in self.active_requests:
            self.active_requests[channel_id] = {}
            
        # Store request
        self.active_requests[channel_id][user_id] = request
        
        if self.flow_logger:
            await self.flow_logger.log_event(
                "Request Tracker",
                "Request Created",
                {
                    "request_id": request.id,
                    "channel_id": channel_id,
                    "user_id": user_id
                }
            )
            
        return request
    
    def get_active_request(self, channel_id: str, user_id: str) -> Optional[Request]:
        """Get the active request for a user in a channel."""
        if channel_id in self.active_requests and user_id in self.active_requests[channel_id]:
            request = self.active_requests[channel_id][user_id]
            # Only timeout requests that are not actively being processed
            if request.status not in ["processing", "waiting_for_info"] or \
               datetime.now() - request.last_updated <= self.request_timeout:
                return request
        return None
    
    async def update_request(self, request: Request, **updates) -> Request:
        """Update a request with new information"""
        if not request:
            return None
            
        # Track if any actual changes were made
        changes_made = False
        
        # Update fields if they're different from current values
        for key, value in updates.items():
            if hasattr(request, key):
                if key == "entities":
                    # Always merge entities, creating a new dict if needed
                    current_entities = request.entities or {}
                    merged = current_entities.copy()
                    if value:  # Only update if we have new entities
                        merged.update(value)
                        setattr(request, key, merged)
                        changes_made = True
                elif getattr(request, key) != value:
                    setattr(request, key, value)
                    changes_made = True
                
        # Check if we need to update status based on entities
        if "entities" in updates and request.intent:
            required_entities = self._get_required_entities(request.intent)
            missing_entities = [e for e in required_entities if e not in request.entities]
            
            if missing_entities:
                request.status = "waiting_for_info"
            else:
                request.status = "processing"
            changes_made = True
                
        if changes_made:
            # Only log if actual changes were made
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "Request Tracker",
                    "Request Updated",
                    {
                        "request_id": request.id,
                        "updates": updates
                    }
                )
            
            # Save changes to active requests
            if request.channel_id not in self.active_requests:
                self.active_requests[request.channel_id] = {}
            self.active_requests[request.channel_id][request.user_id] = request
            
        return request
    
    def _get_required_entities(self, intent: str) -> List[str]:
        """Get required entities for an intent."""
        if intent == "schedule_meeting":
            return ["time", "participants"]
        elif intent == "email_send":
            return ["recipients", "subject"]
        elif intent == "email_read":
            return []
        return []
    
    async def _archive_request(self, request: Request):
        """Move a request to completed history."""
        if request.channel_id in self.active_requests:
            if request.user_id in self.active_requests[request.channel_id]:
                del self.active_requests[request.channel_id][request.user_id]
                if not self.active_requests[request.channel_id]:
                    del self.active_requests[request.channel_id]
        
        self.completed_requests.append(request)
        # Keep only last 1000 completed requests
        if len(self.completed_requests) > 1000:
            self.completed_requests = self.completed_requests[-500:]
            
        if self.flow_logger:
            await self.flow_logger.log_event(
                "Request Tracker",
                "Request Archived",
                {
                    "request_id": request.id,
                    "final_status": request.status,
                    "completion_time": datetime.now().isoformat(),
                    "conversation_length": len(request.messages)
                }
            )
    
    async def _cleanup_old_requests(self):
        """Clean up requests that have timed out."""
        now = datetime.now()
        channels_to_remove = []
        
        for channel_id, user_requests in self.active_requests.items():
            users_to_remove = []
            for user_id, request in user_requests.items():
                if now - request.last_updated > self.request_timeout:
                    users_to_remove.append(user_id)
                    request.status = "timeout"
                    self.completed_requests.append(request)
                    
                    if self.flow_logger:
                        await self.flow_logger.log_event(
                            "Request Tracker",
                            "Request Timeout",
                            {
                                "request_id": request.id,
                                "channel": channel_id,
                                "user": user_id,
                                "last_updated": request.last_updated.isoformat()
                            }
                        )
            
            for user_id in users_to_remove:
                del user_requests[user_id]
            
            if not user_requests:
                channels_to_remove.append(channel_id)
        
        for channel_id in channels_to_remove:
            del self.active_requests[channel_id] 