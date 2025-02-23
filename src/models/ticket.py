from typing import Dict, Any, Optional, List, Set, Deque
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import logging
from copy import deepcopy
from enum import Enum

logger = logging.getLogger(__name__)

class TicketStatus(Enum):
    """Status states for a ticket lifecycle"""
    CREATED = "created"
    ANALYZING = "analyzing"
    EXECUTING = "executing"
    WAITING_INPUT = "waiting_input"
    SERVICE_CREATION = "service_creation"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class TicketEvent:
    """Represents a single change to a ticket's state"""
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    component: str = ""  # Which component generated this event

class TicketView:
    """Read-only view of ticket state for a specific component"""
    def __init__(self, ticket: 'Ticket', component: str, allowed_fields: Set[str]):
        self._ticket = ticket
        self._component = component
        self._allowed = allowed_fields
    
    def __getattr__(self, name):
        if name not in self._allowed:
            raise AttributeError(f"Access to {name} not allowed for {self._component}")
        return getattr(self._ticket, name)
    
    def update(self, event_type: str, data: Dict[str, Any]):
        """Submit an update to the ticket"""
        return self._ticket.apply_event(TicketEvent(
            event_type=event_type,
            data=data,
            component=self._component
        ))

@dataclass
class Message:
    """Represents a message in the conversation"""
    content: str
    timestamp: datetime
    direction: str  # "incoming" or "outgoing"
    metadata: Dict[str, Any] = field(default_factory=dict)  # For additional context

# Constants for memory management
MAX_MESSAGES = 100  # Maximum number of messages to keep
MAX_HISTORY = 50   # Maximum number of historical items

@dataclass
class Ticket:
    """
    Represents the complete lifecycle of a user request.
    Tracks all interactions, steps, and context from initial message to completion.
    """
    # Core identification
    ticket_id: str = field(default_factory=lambda: f"ticket_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    created_at: datetime = field(default_factory=datetime.now)
    
    # User and channel info
    user_info: Dict[str, Any] = field(default_factory=dict)
    channel_id: str = ""
    thread_ts: Optional[str] = None
    
    # Request details
    original_message: str = ""
    intent: Optional[str] = None
    service: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    missing_entities: List[str] = field(default_factory=list)
    
    # Processing state
    status: TicketStatus = TicketStatus.CREATED
    current_step: Optional[str] = None
    execution_plan: List[Dict[str, Any]] = field(default_factory=list)
    
    # Conversation history with bounded deques
    incoming_messages: Deque[Message] = field(default_factory=lambda: deque(maxlen=MAX_MESSAGES))
    outgoing_messages: Deque[Message] = field(default_factory=lambda: deque(maxlen=MAX_MESSAGES))
    
    # Execution history with bounded deques
    steps_executed: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=MAX_HISTORY))
    errors: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=MAX_HISTORY))
    created_services: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=MAX_HISTORY))
    
    # Results
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    final_response: Optional[str] = None

    # Execution tracking with bounded deque
    execution_steps: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=MAX_HISTORY))
    step_results: Dict[int, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Called after dataclass initialization to set up initial state."""
        if self.original_message:
            self.add_incoming_message(self.original_message)
            
        # Set channel_id and thread_ts from user_info if available
        if self.user_info:
            self.channel_id = self.user_info.get("channel_id", "")
            self.thread_ts = self.user_info.get("thread_ts")

    def add_incoming_message(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add an incoming message (from user). Called by ServiceAnalyzer."""
        self.incoming_messages.append(Message(
            content=content,
            timestamp=datetime.now(),
            direction="incoming",
            metadata=metadata or {}
        ))

    def add_outgoing_message(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add an outgoing message (to user). Called by MessageMaker."""
        self.outgoing_messages.append(Message(
            content=content,
            timestamp=datetime.now(),
            direction="outgoing",
            metadata=metadata or {}
        ))

    def add_step(self, step_name: str, tool: str, action: str, params: Dict[str, Any], result: Any):
        """Record an executed step."""
        self.steps_executed.append({
            "step": step_name,
            "tool": tool,
            "action": action,
            "params": params,
            "result": result,
            "timestamp": datetime.now()
        })

    def add_error(self, error_message: str, error_type: str, step: Optional[str] = None):
        """Record an error."""
        self.errors.append({
            "message": error_message,
            "type": error_type,
            "step": step,
            "timestamp": datetime.now()
        })

    def add_created_service(self, service_name: str, service_def: Dict[str, Any]):
        """Record a newly created service."""
        self.created_services.append({
            "name": service_name,
            "definition": service_def,
            "timestamp": datetime.now()
        })

    def update_status(self, new_status: TicketStatus):
        """Update ticket status."""
        self.status = new_status

    def get_failed_services(self) -> List[str]:
        """Get list of services that failed execution."""
        return [
            step["service"]
            for step in self.steps_executed
            if step.get("result", {}).get("status") == "error"
        ]

    def get_conversation_history(self) -> List[Message]:
        """Get complete conversation history in chronological order."""
        all_messages = self.incoming_messages + self.outgoing_messages
        return sorted(all_messages, key=lambda m: m.timestamp)

    def to_dict(self) -> Dict[str, Any]:
        """Convert ticket to dictionary format."""
        return {
            "ticket_id": self.ticket_id,
            "status": self.status.value,
            "intent": self.intent,
            "service": self.service,
            "entities": self.entities,
            "missing_entities": self.missing_entities,
            "user_info": self.user_info,
            "channel_id": self.channel_id,
            "thread_ts": self.thread_ts,
            "execution_plan": self.execution_plan,
            "conversation": {
                "incoming": [
                    {
                        "content": m.content,
                        "timestamp": m.timestamp.isoformat(),
                        "metadata": m.metadata
                    }
                    for m in self.incoming_messages
                ],
                "outgoing": [
                    {
                        "content": m.content,
                        "timestamp": m.timestamp.isoformat(),
                        "metadata": m.metadata
                    }
                    for m in self.outgoing_messages
                ]
            },
            "history": {
                "steps": self.steps_executed,
                "errors": self.errors,
                "created_services": self.created_services
            },
            "results": self.execution_results,
            "final_response": self.final_response
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Ticket':
        """Create a ticket from dictionary data."""
        ticket = cls()
        ticket.ticket_id = data.get("ticket_id", ticket.ticket_id)
        ticket.status = TicketStatus(data.get("status", TicketStatus.CREATED.value))
        ticket.intent = data.get("intent")
        ticket.service = data.get("service")
        ticket.entities = data.get("entities", {})
        ticket.missing_entities = data.get("missing_entities", [])
        ticket.user_info = data.get("user_info", {})
        ticket.channel_id = data.get("channel_id", "")
        ticket.thread_ts = data.get("thread_ts")
        ticket.execution_plan = data.get("execution_plan", [])
        
        # Load conversation history
        conversation = data.get("conversation", {})
        for msg in conversation.get("incoming", []):
            ticket.add_incoming_message(
                msg["content"],
                metadata=msg.get("metadata", {})
            )
        for msg in conversation.get("outgoing", []):
            ticket.add_outgoing_message(
                msg["content"],
                metadata=msg.get("metadata", {})
            )
        
        # Load execution history
        history = data.get("history", {})
        ticket.steps_executed = history.get("steps", [])
        ticket.errors = history.get("errors", [])
        ticket.created_services = history.get("created_services", [])
        
        ticket.execution_results = data.get("results", [])
        ticket.final_response = data.get("final_response")
        
        return ticket 

    def add_execution_step(self, step: Dict[str, Any]):
        """Add a step to the execution plan."""
        step_number = len(self.execution_steps) + 1
        step['step_number'] = step_number
        self.execution_steps.append(step)
        return step_number
    
    def store_step_result(self, step_number: int, result: Any):
        """Store the result of a step execution."""
        self.step_results[step_number] = result
    
    def get_next_step(self) -> Optional[Dict[str, Any]]:
        """Get the next step that hasn't been executed yet."""
        executed_steps = set(self.step_results.keys())
        for step in self.execution_steps:
            if step['step_number'] not in executed_steps:
                return step
        return None 

    @property
    def messages(self) -> List[Message]:
        """Get all messages in chronological order."""
        all_messages = list(self.incoming_messages) + list(self.outgoing_messages)
        return sorted(all_messages, key=lambda m: m.timestamp)
        
    def add_message(self, content: str, source: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a message to the appropriate queue."""
        message = Message(
            content=content,
            timestamp=datetime.now(),
            direction="incoming" if source == "user" else "outgoing",
            metadata=metadata or {}
        )
        
        if source == "user":
            self.incoming_messages.append(message)
        else:
            self.outgoing_messages.append(message)
            
    def get_last_message(self, direction: Optional[str] = None) -> Optional[Message]:
        """Get the last message, optionally filtered by direction."""
        if direction == "incoming":
            return self.incoming_messages[-1] if self.incoming_messages else None
        elif direction == "outgoing":
            return self.outgoing_messages[-1] if self.outgoing_messages else None
        else:
            messages = self.messages
            return messages[-1] if messages else None 