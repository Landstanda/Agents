from typing import Dict, Any, Optional, List
import re
import logging
import yaml
from pathlib import Path
from src.utils.flow_logger import FlowLogger
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
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
    
    # History tracking
    messages: List[Dict[str, Any]] = field(default_factory=list)
    steps_executed: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    created_services: List[Dict[str, Any]] = field(default_factory=list)
    
    # Results
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    final_response: Optional[str] = None

    def __post_init__(self):
        """Called after dataclass initialization to set up initial state."""
        if self.original_message:
            self.add_message(self.original_message, "user")
            
        # Set channel_id and thread_ts from user_info if available
        if self.user_info:
            self.channel_id = self.user_info.get("channel_id", "")
            self.thread_ts = self.user_info.get("thread_ts")

    def add_message(self, message: str, source: str, timestamp: Optional[datetime] = None):
        """Add a message to the conversation history."""
        self.messages.append({
            "message": message,
            "source": source,
            "timestamp": timestamp or datetime.now()
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
        """Update ticket status and log the transition."""
        self.status = new_status

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
            "history": {
                "messages": self.messages,
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
        
        # Load history
        history = data.get("history", {})
        ticket.messages = history.get("messages", [])
        ticket.steps_executed = history.get("steps", [])
        ticket.errors = history.get("errors", [])
        ticket.created_services = history.get("created_services", [])
        
        ticket.execution_results = data.get("results", [])
        ticket.final_response = data.get("final_response")
        
        return ticket

class NLPAnalyzer:
    """
    Analyzes incoming Slack messages to identify intents and extract entities.
    Uses a local lexicon built from Services to match intents.
    """
    
    def __init__(self, services_path: str = "src/services/services.yaml", flow_logger: Optional[FlowLogger] = None):
        """Initialize NLP processor with enhanced patterns."""
        self.services_path = Path(services_path)
        self.flow_logger = flow_logger
        self.lexicon = {}
        
    @classmethod
    async def create(cls, services_path: str = "src/services/services.yaml", flow_logger: Optional[FlowLogger] = None) -> 'NLPAnalyzer':
        """Create and initialize an NLPAnalyzer instance."""
        analyzer = cls(services_path, flow_logger or FlowLogger())
        await analyzer.refresh_lexicon()
        return analyzer
        
    async def refresh_lexicon(self):
        """Rebuild lexicon from services file."""
        try:
            if not self.services_path.exists():
                logger.warning(f"Services file not found at {self.services_path}")
                await self.flow_logger.log_event(
                    "NLPAnalyzer",
                    "lexicon_refresh_error",
                    {"error": f"Services file not found at {self.services_path}"}
                )
                return
                
            with open(self.services_path, 'r') as f:
                services = yaml.safe_load(f) or {}
                
            self.lexicon = {}
            for name, service in services.items():
                # Add service name as intent
                intent = service.get('intent', '').lower()
                if intent:
                    self.lexicon[intent] = {
                        'service': name,
                        'intent': intent,
                        'required_entities': service.get('required_entities', []),
                        'triggers': service.get('triggers', [])
                    }
                    
                # Add triggers to lexicon
                for trigger in service.get('triggers', []):
                    self.lexicon[trigger.lower()] = {
                        'service': name,
                        'intent': intent,  # Store the actual intent
                        'required_entities': service.get('required_entities', []),
                        'triggers': service.get('triggers', [])
                    }
            
            await self.flow_logger.log_event(
                "NLPAnalyzer",
                "lexicon_refresh",
                {"services_count": len(services), "triggers_count": sum(len(s.get('triggers', [])) for s in services.values())}
            )
                    
        except Exception as e:
            logger.error(f"Error loading services lexicon: {str(e)}")
            await self.flow_logger.log_event(
                "NLPAnalyzer",
                "lexicon_refresh_error",
                {"error": str(e)}
            )
    
    async def analyze_message(self, message: str, user_info: Dict[str, Any], ticket: Optional[Ticket] = None) -> Ticket:
        """
        Analyze a message to identify intent and extract entities.
        
        Args:
            message: The message text
            user_info: Information about the user who sent the message
            ticket: Optional existing ticket for follow-up messages
            
        Returns:
            Ticket containing analysis results and history
        """
        # Create new ticket or use existing
        current_ticket = ticket or Ticket(user_info=user_info, original_message=message)
        current_ticket.add_message(message, "user")
        
        await self.flow_logger.log_event(
            "NLPAnalyzer",
            "message_received",
            {"ticket_id": current_ticket.ticket_id, "message": message}
        )

        if not message:
            current_ticket.update_status(TicketStatus.ERROR)
            current_ticket.add_error("Empty message", "validation_error")
            return current_ticket
            
        # Clean and lowercase message for matching
        clean_message = message.lower().strip()
        
        # Extract entities from the new message
        new_entities = self._extract_entities(message)
        
        # Always update entities, even if no service is matched
        current_ticket.entities.update(new_entities)
        
        # If this is a follow-up message, merge with existing entities
        if ticket and ticket.entities:
            # Remove from missing_entities if we found them
            current_ticket.missing_entities = [
                entity for entity in current_ticket.missing_entities
                if entity not in new_entities or not new_entities[entity]
            ]
            
            # If we have all required entities, update status
            if not current_ticket.missing_entities:
                current_ticket.update_status(TicketStatus.EXECUTING)
            return current_ticket
            
        # For new messages, try to match against lexicon
        matched_service = None
        matched_intent = None
        required_entities = []
        
        # First try exact matches
        for key, info in self.lexicon.items():
            if key in clean_message:
                matched_service = info['service']
                matched_intent = info['intent']
                required_entities = info['required_entities']
                break
                
        # If no exact match, try fuzzy matching triggers
        if not matched_service:
            for key, info in self.lexicon.items():
                key_words = set(key.split())
                message_words = set(clean_message.split())
                if key_words.issubset(message_words):
                    matched_service = info['service']
                    matched_intent = info['intent']
                    required_entities = info['required_entities']
                    break
        
        if not matched_service:
            current_ticket.update_status(TicketStatus.SERVICE_CREATION)
            await self.flow_logger.log_event(
                "NLPAnalyzer",
                "no_match_found",
                {"ticket_id": current_ticket.ticket_id}
            )
            return current_ticket
            
        # Update ticket with matched service
        current_ticket.service = matched_service
        current_ticket.intent = matched_intent
        
        # Check for missing required entities
        missing_entities = [
            entity for entity in required_entities
            if entity not in current_ticket.entities or not current_ticket.entities[entity]
        ]
        
        if missing_entities:
            current_ticket.update_status(TicketStatus.WAITING_INPUT)
            current_ticket.missing_entities = missing_entities
            await self.flow_logger.log_event(
                "NLPAnalyzer",
                "incomplete_match",
                {
                    "ticket_id": current_ticket.ticket_id,
                    "missing_entities": missing_entities
                }
            )
        else:
            current_ticket.update_status(TicketStatus.EXECUTING)
            await self.flow_logger.log_event(
                "NLPAnalyzer",
                "successful_match",
                {
                    "ticket_id": current_ticket.ticket_id,
                    "service": matched_service,
                    "intent": matched_intent
                }
            )
            
        return current_ticket
    
    def _extract_entities(self, message: str) -> Dict[str, Any]:
        """Extract entities from message."""
        entities = {}
        
        # Extract time
        time_patterns = [
            r'\b(\d{1,2}(?::\d{2})?)\s*(?:am|pm|AM|PM)\b',
            r'\b(\d{1,2}:\d{2})\b',
            r'\b(morning|afternoon|evening|noon|midnight)\b',
            r'\b(\d{1,2})\s*(?:am|pm|AM|PM)\b'  # Added pattern for "2pm" format
        ]
        
        special_times = {
            'morning': '09:00',
            'afternoon': '14:00',
            'evening': '18:00',
            'noon': '12:00',
            'midnight': '00:00'
        }
        
        for pattern in time_patterns:
            match = re.search(pattern, message)  # Don't lowercase here
            if match:
                time_str = match.group(1)
                message_lower = message.lower()
                
                # Handle special time words
                if time_str.lower() in special_times:
                    time_str = special_times[time_str.lower()]
                # Handle AM/PM times
                elif "pm" in message_lower and ":" in time_str:
                    hour, minute = map(int, time_str.split(":"))
                    if hour < 12:
                        hour += 12
                    time_str = f"{hour:02d}:{minute:02d}"
                elif "pm" in message_lower:
                    hour = int(time_str)
                    if hour < 12:
                        hour += 12
                    time_str = f"{hour:02d}:00"
                elif ":" not in time_str and not any(word in time_str.lower() for word in special_times.keys()):
                    # Handle AM times
                    hour = int(time_str)
                    if "am" in message_lower and hour == 12:
                        hour = 0
                    time_str = f"{hour:02d}:00"
                
                entities['time'] = time_str
                break
                
        # Extract date
        date_patterns = [
            r'\b(today|tomorrow|next week)\b',
            r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?))\b',
            r'\b(tomorrow|next|this)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\b(tonight|this morning|this afternoon|this evening)\b'  # Added pattern for time-based dates
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, message.lower())
            if match:
                date_str = match.group(1)
                if len(match.groups()) > 1 and match.group(2):
                    date_str = f"{match.group(1)} {match.group(2)}"
                # Convert time-based references to actual dates
                if date_str in ['tonight', 'this evening']:
                    date_str = 'today'
                elif date_str in ['this morning', 'this afternoon']:
                    date_str = 'today'
                entities['date'] = date_str
                break
                
        # Extract location
        location_patterns = [
            r'\bin\s+([A-Z][a-zA-Z\s]*(?:Room|Hall|Office|Building|Floor)(?:\s+[A-Z])?)\b',
            r'\bat\s+([A-Z][a-zA-Z\s]*(?:Room|Hall|Office|Building|Floor)(?:\s+[A-Z])?)\b',
            r'\b(Room|Hall|Office|Building|Floor)\s+([A-Z][a-zA-Z0-9\s]*)\b'  # Added pattern for "Room 101" format
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, message)
            if match:
                entities['location'] = match.group(1)
                break
                
        # Extract participants (names starting with capital letters, excluding location matches)
        participant_pattern = r'\b(?:with\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'  # Updated to handle "with John" format
        participants = re.findall(participant_pattern, message)
        if participants:
            # Filter out location words and common words
            location_words = {'Room', 'Hall', 'Office', 'Building', 'Floor', 'Conference', 'Schedule', 'Meeting'}
            participants = [p for p in participants if p not in location_words]
            if participants:
                entities['participants'] = participants
            
        return entities 