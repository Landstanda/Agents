from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)

class Request:
    """Represents a single user request through its lifecycle."""
    
    def __init__(self, channel_id: str, user_id: str, initial_message: str):
        self.request_id = str(uuid.uuid4())
        self.channel_id = channel_id
        self.user_id = user_id
        self.initial_message = initial_message
        self.created_at = datetime.now()
        self.last_updated = datetime.now()
        self.status = "new"  # new, processing, waiting_for_info, completed, error
        self.intent = None
        self.entities = {}
        self.conversation_history = []
        self.recipe = None
        self.missing_entities = []
        # New attributes for office chain
        self.task_id = None  # ID from task manager
        self.ceo_consulted = False  # Whether CEO was consulted
        self.priority = 0.5  # Default priority
        self.delegated_to = None  # Which component is handling the request
        self.completion_data = {}  # Data from completed task
        
    def update(self, **kwargs):
        """Update request attributes."""
        for key, value in kwargs.items():
            if key == "entities" and value:
                # Merge entities instead of replacing
                current_entities = self.entities.copy()
                current_entities.update(value)
                self.entities = current_entities
            elif hasattr(self, key):
                setattr(self, key, value)
        
        self.last_updated = datetime.now()
        
        # If request is completed, notify the tracker
        if self.status == "completed":
            if hasattr(self, '_request_tracker'):
                self._request_tracker._archive_request(self)
        
    def add_message(self, message: str, is_user: bool = True, source: str = None):
        """Add a message to the conversation history."""
        self.conversation_history.append({
            "timestamp": datetime.now(),
            "message": message,
            "is_user": is_user,
            "source": source or ("user" if is_user else "system")
        })
        self.last_updated = datetime.now()
        
    def get_context_summary(self) -> Dict[str, Any]:
        """Get a summary of the request context for other components."""
        return {
            "request_id": self.request_id,
            "status": self.status,
            "intent": self.intent,
            "entities": self.entities,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "conversation_length": len(self.conversation_history)
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
        
    def create_request(self, channel_id: str, user_id: str, message: str) -> Request:
        """Create a new request or return existing active request."""
        # Check for existing request first
        existing = self.get_active_request(channel_id, user_id)
        if existing and existing.status not in ["completed", "error"]:
            existing.add_message(message)
            return existing
            
        # Clean up old requests only if we're creating a new one
        self._cleanup_old_requests()
        
        # Create new request
        request = Request(channel_id, user_id, message)
        request._request_tracker = self  # Link request to tracker
        request.add_message(message, is_user=True)  # Add initial message to history
        if channel_id not in self.active_requests:
            self.active_requests[channel_id] = {}
        self.active_requests[channel_id][user_id] = request
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
    
    def update_request(self, request: Request, **kwargs):
        """Update a request's attributes."""
        request.update(**kwargs)
        
        # If request is completed, move it to history
        if request.status == "completed":
            self._archive_request(request)
    
    def _archive_request(self, request: Request):
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
    
    def _cleanup_old_requests(self):
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
            
            for user_id in users_to_remove:
                del user_requests[user_id]
            
            if not user_requests:
                channels_to_remove.append(channel_id)
        
        for channel_id in channels_to_remove:
            del self.active_requests[channel_id] 