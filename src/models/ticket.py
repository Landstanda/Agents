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
    service: Optional[Dict[str, Any]] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    missing_entities: List[str] = field(default_factory=list)
    
    # Processing state
    status: TicketStatus = TicketStatus.CREATED
    current_step: Optional[str] = None
    execution_plan: List[Dict[str, Any]] = field(default_factory=list)
    
    # History tracking
    status_history: List[Dict[str, Any]] = field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    
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
    
    # Additional state
    waiting_for: Optional[str] = None
    retry_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    context_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Called after dataclass initialization to set up initial state."""
        if self.original_message:
            self.add_incoming_message(self.original_message)
            
        # Set channel_id and thread_ts from user_info if available
        if self.user_info:
            self.channel_id = self.user_info.get("channel_id", "")
            self.thread_ts = self.user_info.get("thread_ts")
            
        # Initialize status history
        self.status_history.append({
            "status": self.status,
            "timestamp": self.created_at
        })

    def add_incoming_message(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add an incoming message (from user). Called by ServiceAnalyzer."""
        # Skip if this is the original message during initialization
        if content == self.original_message and not self.conversation_history:
            return
            
        message = Message(
            content=content,
            timestamp=datetime.now(),
            direction="incoming",
            metadata=metadata or {}
        )
        self.incoming_messages.append(message)
        self.conversation_history.append({
            "type": "incoming",
            "message": content,
            "timestamp": message.timestamp,
            "metadata": message.metadata
        })

    def add_outgoing_message(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add an outgoing message (to user). Called by MessageMaker."""
        message = Message(
            content=content,
            timestamp=datetime.now(),
            direction="outgoing",
            metadata=metadata or {}
        )
        self.outgoing_messages.append(message)
        self.conversation_history.append({
            "type": "outgoing",
            "message": content,
            "timestamp": message.timestamp,
            "metadata": message.metadata
        })

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

    def add_error(self, error_message: str, error_type: str, step: Optional[str] = None, context: Optional[str] = None):
        """Record an error."""
        error = {
            "message": error_message,
            "type": error_type,
            "step": step,
            "context": context,
            "timestamp": datetime.now()
        }
        self.errors.append(error)
        self.error_history.append(error)

    def add_created_service(self, service_name: str, service_def: Dict[str, Any]):
        """Record a newly created service."""
        self.created_services.append({
            "name": service_name,
            "definition": service_def,
            "timestamp": datetime.now()
        })

    def update_status(self, new_status: TicketStatus):
        """Update ticket status with validation."""
        # Validate status transition
        valid_transitions = {
            TicketStatus.CREATED: {TicketStatus.ANALYZING, TicketStatus.WAITING_INPUT, TicketStatus.ERROR},
            TicketStatus.ANALYZING: {TicketStatus.EXECUTING, TicketStatus.WAITING_INPUT, TicketStatus.ERROR},
            TicketStatus.EXECUTING: {TicketStatus.COMPLETED, TicketStatus.ERROR, TicketStatus.WAITING_INPUT},
            TicketStatus.WAITING_INPUT: {TicketStatus.ANALYZING, TicketStatus.EXECUTING, TicketStatus.ERROR},
            TicketStatus.ERROR: {TicketStatus.ANALYZING, TicketStatus.EXECUTING, TicketStatus.WAITING_INPUT},
            TicketStatus.COMPLETED: set()  # Terminal state
        }
        
        if new_status not in valid_transitions.get(self.status, set()):
            raise ValueError(f"Invalid status transition from {self.status} to {new_status}")
            
        self.status = new_status
        self.status_history.append({
            "status": new_status,
            "timestamp": datetime.now()
        })

    def update_entities(self, entities: Dict[str, Any]) -> None:
        """Update ticket entities."""
        self.entities.update(entities)

    def set_service(self, service_def: Dict[str, Any]) -> None:
        """Set the service definition for this ticket."""
        self.service = service_def

    def add_step_result(self, step_number: int, result: Any) -> None:
        """Add a step execution result."""
        self.step_results[step_number] = result
        
        # Handle both ModuleResponse and dict results
        success = result.success if hasattr(result, 'success') else result.get('success', False)
        error = result.error if hasattr(result, 'error') else result.get('error')
        
        if not success:
            self.add_error(error or "Step failed", "step_failure", str(step_number))

    def set_waiting_for(self, wait_type: str) -> None:
        """Set what the ticket is waiting for."""
        self.waiting_for = wait_type

    def clear_waiting_state(self) -> None:
        """Clear the waiting state."""
        self.waiting_for = None

    def set_retry_count(self, operation: str, max_attempts: int = 3) -> None:
        """Initialize retry tracking for an operation."""
        self.retry_counts[operation] = {
            "count": 0,
            "max_attempts": max_attempts
        }

    def increment_retry(self, operation: str) -> None:
        """Increment retry count for an operation."""
        if operation in self.retry_counts:
            self.retry_counts[operation]["count"] += 1

    def can_retry(self, operation: str) -> bool:
        """Check if an operation can be retried."""
        if operation not in self.retry_counts:
            return False
        return self.retry_counts[operation]["count"] < self.retry_counts[operation]["max_attempts"]

    def get_retry_count(self, operation: str) -> int:
        """Get current retry count for an operation."""
        return self.retry_counts.get(operation, {}).get("count", 0)

    def add_context_data(self, key: str, value: Any) -> None:
        """Add data to the context."""
        self.context_data[key] = value

    def get_context_data(self, key: str, default: Any = None) -> Any:
        """Get data from the context."""
        return self.context_data.get(key, default)

    def update_context_data(self, key: str, value: Any) -> None:
        """Update context data."""
        self.context_data[key] = value

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of the execution progress."""
        successful_steps = sum(1 for result in self.step_results.values() 
                             if (hasattr(result, 'success') and result.success) or 
                                (isinstance(result, dict) and result.get('success', False)))
        total_steps = len(self.step_results)
        failed_steps = total_steps - successful_steps
        
        return {
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": failed_steps,
            "completion_percentage": (successful_steps / total_steps * 100) if total_steps > 0 else 0,
            "success": failed_steps == 0 and total_steps > 0
        }

    def get_last_error(self) -> Optional[Dict[str, Any]]:
        """Get the most recent error."""
        return self.errors[-1] if self.errors else None

    def get_failed_services(self) -> List[str]:
        """Get list of services that failed execution."""
        return [
            step["service"]
            for step in self.steps_executed
            if step.get("result", {}).get("status") == "error"
        ]

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the complete conversation history."""
        return self.conversation_history

    def to_dict(self) -> Dict[str, Any]:
        """Convert ticket to dictionary for serialization."""
        return {
            "ticket_id": self.ticket_id,
            "created_at": self.created_at.isoformat(),
            "user_info": self.user_info,
            "channel_id": self.channel_id,
            "thread_ts": self.thread_ts,
            "original_message": self.original_message,
            "intent": self.intent,
            "service": self.service,
            "entities": self.entities,
            "missing_entities": self.missing_entities,
            "status": self.status.value,
            "current_step": self.current_step,
            "execution_plan": self.execution_plan,
            "status_history": [{
                "status": item["status"].value,
                "timestamp": item["timestamp"].isoformat()
            } for item in self.status_history],
            "conversation_history": self.conversation_history,
            "error_history": self.error_history,
            "steps_executed": list(self.steps_executed),
            "errors": list(self.errors),
            "created_services": list(self.created_services),
            "execution_results": self.execution_results,
            "final_response": self.final_response,
            "execution_steps": list(self.execution_steps),
            "step_results": self.step_results,
            "waiting_for": self.waiting_for,
            "retry_counts": self.retry_counts,
            "context_data": self.context_data
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Ticket':
        """Create ticket from dictionary."""
        ticket = cls()
        ticket.ticket_id = data.get("ticket_id", ticket.ticket_id)
        ticket.created_at = datetime.fromisoformat(data.get("created_at", ticket.created_at.isoformat()))
        ticket.user_info = data.get("user_info", ticket.user_info)
        ticket.channel_id = data.get("channel_id", ticket.channel_id)
        ticket.thread_ts = data.get("thread_ts")
        ticket.original_message = data.get("original_message", ticket.original_message)
        ticket.intent = data.get("intent")
        ticket.service = data.get("service")
        ticket.entities = data.get("entities", ticket.entities)
        ticket.missing_entities = data.get("missing_entities", ticket.missing_entities)
        ticket.status = TicketStatus(data.get("status", TicketStatus.CREATED.value))
        ticket.current_step = data.get("current_step")
        ticket.execution_plan = data.get("execution_plan", ticket.execution_plan)
        
        # Convert status history timestamps back to datetime
        ticket.status_history = [{
            "status": TicketStatus(item["status"]),
            "timestamp": datetime.fromisoformat(item["timestamp"])
        } for item in data.get("status_history", [])]
        
        ticket.conversation_history = data.get("conversation_history", [])
        ticket.error_history = data.get("error_history", [])
        ticket.steps_executed = deque(data.get("steps_executed", []), maxlen=MAX_HISTORY)
        ticket.errors = deque(data.get("errors", []), maxlen=MAX_HISTORY)
        ticket.created_services = deque(data.get("created_services", []), maxlen=MAX_HISTORY)
        ticket.execution_results = data.get("execution_results", [])
        ticket.final_response = data.get("final_response")
        ticket.execution_steps = deque(data.get("execution_steps", []), maxlen=MAX_HISTORY)
        ticket.step_results = data.get("step_results", {})
        ticket.waiting_for = data.get("waiting_for")
        ticket.retry_counts = data.get("retry_counts", {})
        ticket.context_data = data.get("context_data", {})
        
        # Add original message to conversation if provided
        if ticket.original_message:
            ticket.add_incoming_message(ticket.original_message)
        
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

    def get_error_history(self) -> List[Dict[str, Any]]:
        """Get the complete error history."""
        return self.error_history

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of the execution progress."""
        successful_steps = sum(1 for result in self.step_results.values() 
                             if (hasattr(result, 'success') and result.success) or 
                                (isinstance(result, dict) and result.get('success', False)))
        total_steps = len(self.step_results)
        failed_steps = total_steps - successful_steps
        
        return {
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": failed_steps,
            "completion_percentage": (successful_steps / total_steps * 100) if total_steps > 0 else 0,
            "success": failed_steps == 0 and total_steps > 0
        } 