from typing import Dict, Any, Optional, List, Set
import re
import logging
import yaml
from pathlib import Path
from src.utils.flow_logger import FlowLogger
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pytz
from dateutil import parser
from dateutil.relativedelta import relativedelta

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

@dataclass
class ServiceMatch:
    """Represents a potential service match with scoring details"""
    service_name: str
    service_def: Dict[str, Any]
    matched_triggers: Set[str] = field(default_factory=set)
    matched_entities: Set[str] = field(default_factory=set)
    
    @property
    def trigger_count(self) -> int:
        """Number of triggers matched"""
        return len(self.matched_triggers)
    
    @property
    def total_triggers(self) -> int:
        """Total number of triggers in service"""
        return len(self.service_def.get('triggers', []))
    
    @property
    def match_percentage(self) -> float:
        """Percentage of service triggers matched"""
        if self.total_triggers == 0:
            return 0.0
        return (self.trigger_count / self.total_triggers) * 100
    
    @property
    def required_entities_present(self) -> bool:
        """Check if all required entities are present"""
        required = set(self.service_def.get('required_entities', []))
        return required.issubset(self.matched_entities)
    
    def add_trigger_match(self, trigger: str):
        """Add a matched trigger word"""
        self.matched_triggers.add(trigger)
    
    def add_entity_match(self, entity: str):
        """Add a matched entity"""
        self.matched_entities.add(entity)

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
            # First pass: Create service entries
            for service_id, service in services.items():
                logger.debug(f"Loading service: {service_id}")
                self.lexicon[service_id] = {
                    'service': service_id,
                    'intent': service.get('intent', '').lower(),
                    'required_entities': service.get('required_entities', []),
                    'optional_entities': service.get('optional_entities', []),
                    'triggers': service.get('triggers', []),
                    'description': service.get('description', '')
                }
                logger.debug(f"Service {service_id} loaded with {len(service.get('triggers', []))} triggers")
            
            await self.flow_logger.log_event(
                "NLPAnalyzer",
                "lexicon_refresh",
                {
                    "services_count": len(services),
                    "services": list(self.lexicon.keys()),
                    "triggers_count": sum(len(s.get('triggers', [])) for s in services.values())
                }
            )
                    
        except Exception as e:
            logger.error(f"Error loading services lexicon: {str(e)}")
            await self.flow_logger.log_event(
                "NLPAnalyzer",
                "lexicon_refresh_error",
                {"error": str(e)}
            )
    
    def _score_services(self, message: str, entities: Dict[str, Any]) -> List[ServiceMatch]:
        """
        Score each service based on trigger matches and entities.
        
        Args:
            message: The user's message
            entities: Extracted entities from the message
            
        Returns:
            List of ServiceMatch objects sorted by score
        """
        logger.debug(f"\n{'='*50}")
        logger.debug(f"Starting service scoring for message: '{message}'")
        logger.debug(f"Extracted entities: {entities}")
        message_words = set(message.lower().split())
        logger.debug(f"Message words: {message_words}")
        service_matches: Dict[str, ServiceMatch] = {}
        
        # Initialize matches for each service
        for service_id, service_def in self.lexicon.items():
            logger.debug(f"\nScoring service: {service_id}")
            logger.debug(f"Service triggers: {service_def.get('triggers', [])}")
            logger.debug(f"Required entities: {service_def.get('required_entities', [])}")
            service_matches[service_id] = ServiceMatch(
                service_name=service_id,
                service_def=service_def
            )
        
        # Score trigger matches
        logger.debug("\nScoring trigger matches:")
        logger.debug("-" * 30)
        for word in message_words:
            logger.debug(f"\nChecking word: '{word}'")
            for service_id, service_def in self.lexicon.items():
                triggers = service_def.get('triggers', [])
                logger.debug(f"Service {service_id} triggers: {triggers}")
                for trigger in triggers:
                    trigger_lower = trigger.lower()
                    # Only match exact words, not partial matches
                    if word == trigger_lower:
                        logger.debug(f"✓ Exact match found: '{trigger}' for service '{service_id}'")
                        service_matches[service_id].add_trigger_match(trigger)
                    else:
                        logger.debug(f"  ✗ No match: '{trigger}' vs '{word}'")
        
        # Log trigger match summary with simplified format
        logger.debug("\nService Match Tallies:")
        logger.debug("-" * 30)
        for service_id, match in service_matches.items():
            if match.matched_triggers:
                logger.debug(f"\n{service_id}:")
                logger.debug(f"  Total trigger words: {match.total_triggers}")
                logger.debug(f"  Matched words tally: {match.trigger_count}")
                logger.debug(f"  Matched triggers: {', '.join(match.matched_triggers)}")
        
        # Filter and sort matches
        valid_matches = [
            match for match in service_matches.values()
            if match.trigger_count > 0  # Must have at least one trigger match
        ]
        
        # Sort by:
        # 1. Number of trigger matches (tallies) - highest first
        # 2. Total trigger count - lowest first (for breaking ties)
        sorted_matches = sorted(
            valid_matches,
            key=lambda m: (
                m.trigger_count,
                -m.total_triggers  # Negative because we want ascending order in case of tie
            ),
            reverse=True
        )
        
        # Log final ranking
        logger.debug("\nFinal Service Ranking:")
        logger.debug("=" * 50)
        for i, match in enumerate(sorted_matches, 1):
            logger.debug(f"\n{i}. Service: {match.service_name}")
            logger.debug(f"   Total trigger words: {match.total_triggers}")
            logger.debug(f"   Matched words tally: {match.trigger_count}")
            logger.debug(f"   Matched triggers: {', '.join(match.matched_triggers)}")
        logger.debug("=" * 50)
        
        return sorted_matches
    
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
            
        # Extract entities from the message
        entities = self._extract_entities(message)
        current_ticket.entities.update(entities)
        
        # If this is a follow-up message, merge with existing entities
        if ticket and ticket.service:
            if ticket.missing_entities:
                # Remove from missing_entities if we found them
                current_ticket.missing_entities = [
                    entity for entity in current_ticket.missing_entities
                    if entity not in entities or not entities[entity]
                ]
                
                # If we have all required entities, update status
                if not current_ticket.missing_entities:
                    current_ticket.update_status(TicketStatus.EXECUTING)
            return current_ticket
            
        # Score services against the message
        service_matches = self._score_services(message, entities)
        
        if not service_matches:
            current_ticket.update_status(TicketStatus.SERVICE_CREATION)
            await self.flow_logger.log_event(
                "NLPAnalyzer",
                "no_match_found",
                {"ticket_id": current_ticket.ticket_id}
            )
            return current_ticket
            
        # Use the best match
        best_match = service_matches[0]
        service_def = best_match.service_def
        
        # Update ticket with matched service
        current_ticket.service = best_match.service_name
        
        # Set intent based on matched triggers from service definition
        current_ticket.intent = next(iter(best_match.matched_triggers)) if best_match.matched_triggers else service_def.get('identifier')
        current_ticket.entities['intent'] = current_ticket.intent
        
        # Check for missing required entities
        missing_entities = [
            entity for entity in service_def.get('required_entities', [])
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
                    "service": best_match.service_name,
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
                    "service": best_match.service_name,
                    "matched_triggers": list(best_match.matched_triggers),
                    "match_percentage": best_match.match_percentage
                }
            )
            
        return current_ticket
    
    def _extract_entities(self, message: str) -> Dict[str, Any]:
        """Extract entities from the message."""
        entities = {}
        
        # Time patterns
        time_patterns = [
            r'at\s+(\d{1,2}(?::\d{2})?)\s*(?:am|pm|AM|PM)',  # e.g., "at 3:30pm" or "at 3pm"
            r'(\d{1,2}(?::\d{2})?)\s*(?:am|pm|AM|PM)',  # e.g., "3:30pm" or "3pm"
        ]
        
        # Extract time
        for pattern in time_patterns:
            match = re.search(pattern, message.lower())
            if match:
                time_str = match.group(1)
                # Convert to 24-hour format
                try:
                    # Parse the time
                    if ':' not in time_str:
                        time_str += ':00'
                    time_obj = datetime.strptime(time_str + ('am' if 'am' in message.lower() else 'pm'), '%I:%M%p')
                    # Format as HH:mm
                    entities['time'] = time_obj.strftime('%H:%M')
                    break
                except ValueError:
                    continue

        # Extract date using dateutil.parser
        # First, try to find date-like patterns in the message
        date_patterns = [
            # Common date formats
            r'(?:on\s+)?(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?',
            r'(?:on\s+)?\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s*,?\s*\d{4})?',
            r'(?:on\s+)?(?:this|next)?\s*(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'(?:on\s+)?today|tomorrow',
            r'\d{4}-\d{2}-\d{2}'  # ISO format
        ]

        # Try to find a date in the message
        date_str = None
        for pattern in date_patterns:
            match = re.search(pattern, message.lower())
            if match:
                date_str = match.group(0)
                break

        if date_str:
            try:
                # Clean up the date string
                date_str = date_str.lower().replace('on ', '')
                
                # Handle relative dates
                if date_str == 'today':
                    date_obj = datetime.now()
                elif date_str == 'tomorrow':
                    date_obj = datetime.now() + timedelta(days=1)
                elif any(day in date_str for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
                    # Parse the weekday and calculate next occurrence
                    date_obj = parser.parse(date_str)
                    if date_obj.date() < datetime.now().date():
                        date_obj += timedelta(days=7)
                else:
                    # Parse the date string
                    date_obj = parser.parse(date_str, fuzzy=True)
                    
                    # If year is not specified, use current or next year
                    if date_str.count(str(datetime.now().year)) == 0:
                        if date_obj.date() < datetime.now().date():
                            date_obj = date_obj.replace(year=datetime.now().year + 1)
                        else:
                            date_obj = date_obj.replace(year=datetime.now().year)
                
                # Format as YYYY-MM-DD
                entities['date'] = date_obj.strftime('%Y-%m-%d')
                logger.debug(f"Successfully parsed date: {date_str} -> {entities['date']}")
            except (ValueError, parser.ParserError) as e:
                logger.debug(f"Failed to parse date '{date_str}': {str(e)}")
                
        # Extract location (if present)
        location_match = re.search(r'(?:at|in)\s+(.+?)(?:\s+(?:at|on|from|until|with)|$)', message)
        if location_match:
            entities['location'] = location_match.group(1).strip()
        
        # Extract participants (if present)
        participants_match = re.search(r'with\s+(.+?)(?:\s+(?:at|on|from|until|in)|$)', message)
        if participants_match:
            # Split and clean participant names
            participants = [p.strip() for p in participants_match.group(1).split(',')]
            entities['participants'] = participants
            
        # Extract event type
        event_types = ['lunch', 'meeting', 'appointment', 'call', 'discussion', 'review', 'interview', 'sync']
        message_words = message.lower().split()
        for word in message_words:
            if word in event_types:
                entities['event_type'] = word
                break
        if 'event_type' not in entities:
            entities['event_type'] = 'meeting'  # default type
            
        return entities 