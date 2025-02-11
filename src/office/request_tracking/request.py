from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

class Request:
    """
    Represents a user request in the system with all its associated metadata and state.
    """
    
    def __init__(self, channel_id: str, user_id: str, text: str):
        self.request_id = str(uuid.uuid4())
        self.channel_id = channel_id
        self.user_id = user_id
        self.text = text
        self.created_at = datetime.utcnow()
        self.last_updated = self.created_at
        self.status = "new"  # new, processing, completed, error
        self.intent = None
        self.entities: Dict[str, Any] = {}
        self.missing_entities: List[str] = []
        self.recipe = None
        self.priority = 1
        self.error = None
        self.completion_data: Optional[Dict[str, Any]] = None
        
    def update(self, **kwargs):
        """Update request attributes and last_updated timestamp."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_updated = datetime.utcnow()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary for storage."""
        return {
            "request_id": self.request_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "text": self.text,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "status": self.status,
            "intent": self.intent,
            "entities": self.entities,
            "missing_entities": self.missing_entities,
            "recipe": self.recipe,
            "priority": self.priority,
            "error": self.error,
            "completion_data": self.completion_data
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Request':
        """Create a request instance from a dictionary."""
        request = cls(data["channel_id"], data["user_id"], data["text"])
        request.request_id = data["request_id"]
        request.created_at = datetime.fromisoformat(data["created_at"])
        request.last_updated = datetime.fromisoformat(data["last_updated"])
        request.status = data["status"]
        request.intent = data["intent"]
        request.entities = data["entities"]
        request.missing_entities = data["missing_entities"]
        request.recipe = data["recipe"]
        request.priority = data["priority"]
        request.error = data["error"]
        request.completion_data = data["completion_data"]
        return request 