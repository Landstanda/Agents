from typing import Dict, Any, Optional, List
import logging
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class RequestMetadata:
    """Metadata for a request including routing and priority information."""
    channel_id: str
    user_id: str
    priority: float = 0.5
    deadline: Optional[datetime] = None
    source: str = "slack"
    tags: List[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class Request:
    """Enhanced request object with full tracking capabilities."""
    
    def __init__(self, request_id: str, initial_message: str, metadata: RequestMetadata):
        self.request_id = request_id
        self.initial_message = initial_message
        self.metadata = metadata
        self.created_at = datetime.now()
        self.last_updated = datetime.now()
        self.status = "new"
        self.intent = None
        self.entities = {}
        self.conversation_chain = []
        self.processing_history = []
        self.recipe = None
        self.missing_entities = []
        self.completion_data = {}
        
    def add_to_chain(self, component: str, action: str, details: Dict[str, Any]) -> None:
        """Add an entry to the conversation chain."""
        self.conversation_chain.append({
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "action": action,
            "details": details
        })
        self.last_updated = datetime.now()
    
    def add_processing_step(self, component: str, result: Dict[str, Any]) -> None:
        """Record a processing step."""
        self.processing_history.append({
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "result": result
        })
        self.last_updated = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary for storage."""
        return {
            "request_id": self.request_id,
            "initial_message": self.initial_message,
            "metadata": self.metadata.to_dict(),
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "status": self.status,
            "intent": self.intent,
            "entities": self.entities,
            "conversation_chain": self.conversation_chain,
            "processing_history": self.processing_history,
            "recipe": self.recipe,
            "missing_entities": self.missing_entities,
            "completion_data": self.completion_data
        }

class RequestPersistence:
    """Handles request persistence using SQLite."""
    
    def __init__(self, db_path: str = "data/requests.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    request_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    status TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    user_id TEXT NOT NULL
                )
            """)
    
    async def save_request(self, request: Request) -> None:
        """Save request to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO requests VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    request.request_id,
                    json.dumps(request.to_dict()),
                    request.created_at.isoformat(),
                    request.last_updated.isoformat(),
                    request.status,
                    request.metadata.channel_id,
                    request.metadata.user_id
                )
            )
    
    async def load_request(self, request_id: str) -> Optional[Request]:
        """Load request from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM requests WHERE request_id = ?",
                (request_id,)
            )
            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                metadata = RequestMetadata(**data["metadata"])
                request = Request(data["request_id"], data["initial_message"], metadata)
                request.status = data["status"]
                request.intent = data["intent"]
                request.entities = data["entities"]
                request.conversation_chain = data["conversation_chain"]
                request.processing_history = data["processing_history"]
                request.recipe = data["recipe"]
                request.missing_entities = data["missing_entities"]
                request.completion_data = data["completion_data"]
                request.created_at = datetime.fromisoformat(data["created_at"])
                request.last_updated = datetime.fromisoformat(data["last_updated"])
                return request
        return None

class RequestQueueManager:
    """Manages prioritized request queues."""
    
    def __init__(self):
        self.queues = {
            "high": asyncio.PriorityQueue(),
            "normal": asyncio.PriorityQueue(),
            "low": asyncio.PriorityQueue()
        }
        self.active_requests = {}
    
    def _get_priority_queue(self, priority: float) -> str:
        """Determine which queue to use based on priority."""
        if priority >= 0.7:
            return "high"
        elif priority >= 0.3:
            return "normal"
        return "low"
    
    async def enqueue_request(self, request: Request) -> None:
        """Add request to appropriate priority queue."""
        queue_name = self._get_priority_queue(request.metadata.priority)
        # Use created_at timestamp for FIFO ordering of equal priorities
        await self.queues[queue_name].put(
            (-request.metadata.priority, request.created_at.timestamp(), request.request_id)
        )
        self.active_requests[request.request_id] = request
    
    async def get_next_request(self) -> Optional[Request]:
        """Get next request respecting priorities."""
        for queue_name in ["high", "normal", "low"]:
            if not self.queues[queue_name].empty():
                _, _, request_id = await self.queues[queue_name].get()
                return self.active_requests.get(request_id)
        return None

class EnhancedRequestTracker:
    """Main request tracking coordinator."""
    
    def __init__(self, storage_path: str = "data/requests.db"):
        self.persistence = RequestPersistence(storage_path)
        self.queue_manager = RequestQueueManager()
        self.request_timeout = timedelta(minutes=30)
    
    async def create_request(
        self,
        channel_id: str,
        user_id: str,
        initial_message: str,
        priority: float = 0.5,
        source: str = "slack"
    ) -> Request:
        """Create and store a new request."""
        metadata = RequestMetadata(
            channel_id=channel_id,
            user_id=user_id,
            priority=priority,
            source=source
        )
        
        request = Request(
            request_id=str(uuid.uuid4()),
            initial_message=initial_message,
            metadata=metadata
        )
        
        # Save to persistence and queue
        await self.persistence.save_request(request)
        await self.queue_manager.enqueue_request(request)
        
        return request
    
    async def get_request(self, request_id: str) -> Optional[Request]:
        """Get request by ID."""
        return await self.persistence.load_request(request_id)
    
    async def update_request(self, request: Request) -> None:
        """Update request in persistence."""
        await self.persistence.save_request(request)
    
    async def get_next_request(self) -> Optional[Request]:
        """Get next request from queue."""
        return await self.queue_manager.get_next_request()
    
    async def search_requests(
        self,
        criteria: Dict[str, Any],
        limit: int = 100
    ) -> List[Request]:
        """Search for requests matching criteria."""
        with sqlite3.connect(self.persistence.db_path) as conn:
            query = "SELECT data FROM requests WHERE 1=1"
            params = []
            
            if "user_id" in criteria:
                query += " AND user_id = ?"
                params.append(criteria["user_id"])
            
            if "status" in criteria:
                query += " AND status = ?"
                params.append(criteria["status"])
            
            if "channel_id" in criteria:
                query += " AND channel_id = ?"
                params.append(criteria["channel_id"])
            
            if "after" in criteria:
                query += " AND created_at >= ?"
                params.append(criteria["after"].isoformat())
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            requests = []
            
            for row in cursor:
                data = json.loads(row[0])
                metadata = RequestMetadata(**data["metadata"])
                request = Request(data["request_id"], data["initial_message"], metadata)
                request.status = data["status"]
                request.intent = data["intent"]
                request.entities = data["entities"]
                request.conversation_chain = data["conversation_chain"]
                request.processing_history = data["processing_history"]
                request.recipe = data["recipe"]
                request.missing_entities = data["missing_entities"]
                request.completion_data = data["completion_data"]
                request.created_at = datetime.fromisoformat(data["created_at"])
                request.last_updated = datetime.fromisoformat(data["last_updated"])
                requests.append(request)
            
            return requests
    
    async def get_user_requests(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 100
    ) -> List[Request]:
        """Get recent requests for a user."""
        return await self.search_requests({
            "user_id": user_id,
            "after": datetime.now() - timedelta(days=days),
            "limit": limit
        })
    
    async def get_failed_requests(
        self,
        limit: int = 100
    ) -> List[Request]:
        """Get recent failed requests."""
        return await self.search_requests({
            "status": "error",
            "limit": limit
        })
        
    async def cleanup_stale_requests(self) -> None:
        """Move stale requests to error state."""
        cutoff = datetime.now() - self.request_timeout
        with sqlite3.connect(self.persistence.db_path) as conn:
            # Find stale requests
            cursor = conn.execute("""
                SELECT data FROM requests 
                WHERE status NOT IN ('completed', 'error')
                AND last_updated < ?
            """, (cutoff.isoformat(),))
            
            for row in cursor:
                data = json.loads(row[0])
                metadata = RequestMetadata(**data["metadata"])
                request = Request(data["request_id"], data["initial_message"], metadata)
                request.status = "error"
                request.add_processing_step("cleanup", {
                    "error": "Request timed out",
                    "timeout_after": str(self.request_timeout)
                })
                await self.update_request(request)
                
    async def mark_request_complete(
        self,
        request: Request,
        completion_data: Dict[str, Any]
    ) -> None:
        """Mark a request as complete with final data."""
        request.status = "completed"
        request.completion_data = completion_data
        request.add_processing_step("completion", completion_data)
        await self.update_request(request)
        
    async def mark_request_error(
        self,
        request: Request,
        error: str,
        details: Dict[str, Any] = None
    ) -> None:
        """Mark a request as failed with error details."""
        request.status = "error"
        error_data = {"error": error}
        if details:
            error_data.update(details)
        request.add_processing_step("error", error_data)
        await self.update_request(request)
        
    async def start_request_processing(
        self,
        request: Request,
        processor: str
    ) -> None:
        """Mark a request as being processed."""
        request.status = "processing"
        request.add_processing_step(processor, {
            "action": "start_processing",
            "timestamp": datetime.now().isoformat()
        })
        await self.update_request(request) 