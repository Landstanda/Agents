from typing import Dict, Any, List, Optional
import re
import logging
from datetime import datetime, timedelta
from dateutil import parser
import pytz

from .request_tracker import Request

logger = logging.getLogger(__name__)

class NLPProcessor:
    """
    Handles natural language processing for the Front Desk.
    Extracts intents, entities, and contextual information from user messages.
    """
    
    def __init__(self, cookbook_manager=None, flow_logger=None):
        """Initialize NLP processor with enhanced patterns."""
        self.cookbook_manager = cookbook_manager
        self.flow_logger = flow_logger
        self.conversation_state = {}
        
        # Initialize conversational patterns
        self.conversational_patterns = {
            "greeting": [
                r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening))(?:\s+|$)",
                r"^(?:hi|hello|hey)\s+there(?:\s+|$)"
            ],
            "farewell": [
                r"^(?:bye|goodbye|see\s+you|talk\s+to\s+you\s+later)(?:\s+|$)",
                r"^(?:have\s+a\s+(?:good|nice|great)\s+(?:day|evening|weekend))(?:\s+|$)"
            ],
            "gratitude": [
                r"^(?:thanks|thank\s+you|thx)(?:\s+|$)",
                r"^(?:appreciate\s+(?:it|that))(?:\s+|$)"
            ],
            "pleasantry": [
                r"^(?:how\s+are\s+you|how's\s+it\s+going|what's\s+up)(?:\s+|$)",
                r"^(?:nice\s+to\s+(?:meet|see)\s+you)(?:\s+|$)"
            ],
            "acknowledgment": [
                r"^(?:ok|okay|sure|alright|got\s+it)(?:\s+|$)",
                r"^(?:understood|i\s+see|makes\s+sense)(?:\s+|$)"
            ],
            "affirmative": [
                r"^(?:yes|yeah|yep|yup|correct|right)(?:\s+|$)",
                r"^(?:that's\s+right|that\s+is\s+correct)(?:\s+|$)"
            ],
            "negative": [
                r"^(?:no|nope|nah|not\s+really)(?:\s+|$)",
                r"^(?:that's\s+wrong|that\s+is\s+incorrect)(?:\s+|$)"
            ],
            "help": [
                r"^(?:help|what\s+can\s+you\s+do|how\s+do\s+i)(?:\s+|$)",
                r"^(?:show\s+me\s+help|need\s+assistance)(?:\s+|$)"
            ]
        }
        
        # Build task lexicon
        self.task_lexicon = self._build_task_lexicon()
        
        # Add conversation state tracking
        self.state_timeout = 300  # 5 minutes
        self.task_lexicon = self._build_task_lexicon()
        
        # Initialize patterns
        self._initialize_patterns()
        
    def _initialize_patterns(self):
        """Initialize all the pattern dictionaries."""
        # Common time-related phrases
        self.time_patterns = {
            "urgent": r"\b(urgent|asap|emergency|right away)\b",
            "today": r"\b(today|tonight)\b",
            "tomorrow": r"\b(tomorrow|next day)\b",
            "next_week": r"\b(next week|upcoming week)\b",
            "specific_day": r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            "specific_time": r"\b(?:1[0-2]|0?[1-9])(?::[0-5][0-9])?\s*(?:am|pm|a\.m\.|p\.m\.|AM|PM|morning|afternoon|evening)\b|\b(?:1[0-2]|0?[1-9])(?::[0-5][0-9])?\b",
            "specific_date": r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?\b",
            "date_format": r"\b(?:(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b"
        }
        
        # Common action verbs that indicate intent
        self.action_verbs = {
            "email_read": ["check email", "read email", "view email", "show email", "get email"],
            "email_send": ["send email", "write email", "compose email", "reply to email"],
            "scheduling": ["schedule", "book", "arrange", "plan", "set up"],
            "research": ["research", "find", "look up", "investigate", "analyze"],
            "document": ["create", "prepare", "draft", "write", "make"],
            "review": ["review", "check", "examine", "look at", "verify"]
        }
        
        # Email-specific patterns
        self.email_patterns = {
            "subject": r"\b(subject|title|about)\b",
            "sender": r"\b(from|sent by|sender)\b",
            "recent": r"\b(last|latest|recent|newest)\b",
            "count": r"\b(how many|number of)\b"
        }

    def _build_task_lexicon(self) -> Dict[str, List[str]]:
        """Build task lexicon with intent patterns."""
        return {
            "schedule_meeting": [
                r"schedule\s+(?:a\s+)?meeting",
                r"set\s+up\s+(?:a\s+)?meeting",
                r"book\s+(?:a\s+)?meeting",
                r"arrange\s+(?:a\s+)?meeting"
            ],
            "email_read": [
                r"check\s+(?:my\s+)?(?:email|inbox|messages)",
                r"read\s+(?:my\s+)?(?:email|messages)",
                r"show\s+(?:my\s+)?(?:email|messages)",
                r"any\s+(?:new\s+)?(?:email|messages)"
            ],
            "email_send": [
                r"send\s+(?:an\s+)?email",
                r"write\s+(?:an\s+)?email",
                r"compose\s+(?:an\s+)?email"
            ]
        }

    def refresh_lexicon(self):
        """Rebuild the task lexicon from the cookbook."""
        self.task_lexicon = self._build_task_lexicon()

    async def process_message(self, message: str, user_info: Dict[str, Any], channel_id: str = None) -> Dict[str, Any]:
        """Process a message and extract intent and entities"""
        try:
            if not message or not user_info:
                error_msg = "Missing required input"
                if self.flow_logger:
                    await self.flow_logger.log_event(
                        "NLP Processor",
                        "Processing Error",
                        {
                            "error": error_msg,
                            "message": message or "None"
                        }
                    )
                return self._error_response(error_msg, message)

            # Get conversation state
            current_state = self._get_conversation_state(channel_id) if channel_id else None
            
            # Extract intents with enhanced classification
            intent_info = self._extract_intents(message, current_state)
            
            # Initialize entities with default values
            entities = {
                "time": None,
                "display_time": None,
                "date": None,
                "participants": []
            }
            
            # Extract entities based on intent type
            if intent_info["intent_type"] == "task":
                entities.update(self._extract_entities(message, current_state))
                # Validate and normalize extracted entities
                entities = self._normalize_entities(entities)
            elif current_state and current_state.get("intent_type") == "task":
                # For follow-up messages, try to extract entities even without a clear task intent
                entities.update(self._extract_entities(message, current_state))
                entities = self._normalize_entities(entities)
                # Use the previous intent if we're in a task conversation
                intent_info = {
                    "primary_intent": current_state.get("last_intent"),
                    "intent_type": "task",
                    "all_intents": [current_state.get("last_intent")],
                    "confidence": 0.8
                }
            
            # Build user context
            user_context = {
                "user_id": user_info.get("id"),
                "user_name": user_info.get("real_name"),
                "is_dm": user_info.get("is_dm", False),
                "timestamp": datetime.now().isoformat()
            }

            # Update conversation state if needed
            if channel_id and intent_info["primary_intent"]:
                self._update_conversation_state(channel_id, {
                    "last_intent": intent_info["primary_intent"],
                    "intent_type": intent_info["intent_type"],
                    "entities": entities,
                    "timestamp": datetime.now().timestamp(),
                    "user_id": user_info.get("id"),
                    "channel_id": channel_id
                })

            result = {
                "status": "success",
                "raw_text": message,
                "intent": intent_info["primary_intent"],
                "intent_type": intent_info["intent_type"],
                "confidence": intent_info["confidence"],
                "entities": entities,
                "user_context": user_context,
                "conversation_state": current_state,
                "needs_tracking": intent_info["intent_type"] == "task"
            }

            if self.flow_logger:
                await self.flow_logger.log_event(
                    "NLP Processor",
                    "Message Analysis",
                    {
                        "intent": result["intent"],
                        "intent_type": result["intent_type"],
                        "confidence": result["confidence"],
                        "entities": entities
                    }
                )

            return result
            
        except Exception as e:
            error_msg = str(e)
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "NLP Processor",
                    "Processing Error",
                    {
                        "error": error_msg,
                        "message": message
                    }
                )
            return self._error_response(error_msg, message)

    def _get_conversation_state(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get current conversation state if within timeout."""
        if not channel_id or channel_id not in self.conversation_state:
            return None
            
        state = self.conversation_state[channel_id]
        if datetime.now().timestamp() - state["timestamp"] > self.state_timeout:
            del self.conversation_state[channel_id]
            return None
            
        return state

    def _update_conversation_state(self, channel_id: str, state: Dict[str, Any]):
        """Update conversation state."""
        self.conversation_state[channel_id] = state

    def _extract_intents(self, message: str, current_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract intents from message with enhanced classification."""
        # Initialize with default values for all fields
        result = {
            "primary_intent": None,
            "intent_type": "unknown",
            "all_intents": [],
            "confidence": 0.0
        }
        
        if not message:
            return result
            
        # Check for task intents first
        for task_intent, patterns in self.task_lexicon.items():
            for pattern in patterns:
                if re.search(pattern, message.lower()):
                    result.update({
                        "primary_intent": task_intent,
                        "intent_type": "task",
                        "all_intents": [task_intent],
                        "confidence": 0.95
                    })
                    return result
        
        # Check for conversational intents
        for intent, patterns in self.conversational_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message.lower()):
                    result.update({
                        "primary_intent": intent,
                        "intent_type": "conversational",
                        "all_intents": [intent],
                        "confidence": 0.95
                    })
                    return result
        
        return result

    def _extract_entities(self, message: str, current_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract entities from message with enhanced pattern matching."""
        entities = {
            "time": None,
            "display_time": None,
            "date": None,
            "participants": []
        }
        original_message = message
        message = message.lower()
        
        logger.debug(f"Extracting entities from message: {message}")
        
        # Extract time entities
        time_patterns = [
            # Natural language times
            r'\b(morning|afternoon|evening|noon|midnight)\b',
            # Specific times with optional minutes and AM/PM
            r'(?:at|by)?\s*(\d{1,2})(?::(\d{1,2}))?\s*(?:am|pm|a\.m\.|p\.m\.)',
            # Simple time format (e.g. "2pm")
            r'\b(\d{1,2})(?::(\d{1,2}))?\s*(?:am|pm|a\.m\.|p\.m\.)\b',
            # 24-hour format
            r'\b([01]?\d|2[0-3])(?::([0-5]\d))?\b'
        ]
        
        logger.debug(f"Message to process: {message}")
        logger.debug("Trying time patterns...")
        
        for pattern in time_patterns:
            logger.debug(f"Trying pattern: {pattern}")
            matches = list(re.finditer(pattern, message, re.IGNORECASE))
            logger.debug(f"Found matches: {len(matches)}")
            
            for match in matches:
                logger.debug(f"Processing match: {match.group()}")
                full_match = match.group().lower()
                groups = match.groups()
                logger.debug(f"Match groups: {groups}")
                logger.debug(f"Full match: {full_match}")
                
                # Handle natural language times first
                if len(groups) == 1 and groups[0] and groups[0].lower() in ["morning", "afternoon", "evening", "noon", "midnight"]:
                    time_str = groups[0].lower()
                    entities["time"] = time_str
                    entities["display_time"] = time_str
                    logger.debug(f"Found natural language time: {time_str}")
                    break
                
                # Handle specific times
                if len(groups) >= 1 and groups[0] and groups[0].lower() not in ["morning", "afternoon", "evening", "noon", "midnight"]:
                    hour = int(groups[0])
                    minutes = groups[1] if len(groups) > 1 and groups[1] else "00"
                    logger.debug(f"Extracted hour: {hour}, minutes: {minutes}")
                    
                    # Check for PM/AM in the full match
                    if "pm" in full_match or "p.m." in full_match:
                        logger.debug("PM detected")
                        if hour < 12:
                            hour += 12
                    elif "am" in full_match or "a.m." in full_match:
                        logger.debug("AM detected")
                        if hour == 12:
                            hour = 0
                    
                    logger.debug(f"Final hour after AM/PM adjustment: {hour}")
                    
                    # Store machine-processable time (24-hour format)
                    time_str = f"{hour:02d}:{minutes}"
                    entities["time"] = time_str
                    
                    # Store human-readable time
                    display_hour = hour if hour <= 12 else hour - 12
                    if hour >= 12:
                        entities["display_time"] = f"{display_hour}:{minutes}pm"
                    else:
                        entities["display_time"] = f"{display_hour}:{minutes}am"
                    
                    logger.debug(f"Found time: {time_str} (display: {entities['display_time']})")
                    break
        
            if entities.get("time"):
                break
            
        logger.debug(f"Final entities after time extraction: {entities}")
        
        # Extract date entities
        date_patterns = [
            r'(?:on|for|this|next)?\s*(tomorrow|today|monday|tuesday|wednesday|thursday|friday|next\s+\w+)',
            r'\b(tomorrow|today|monday|tuesday|wednesday|thursday|friday|next\s+\w+)\b'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                entities["date"] = match.group(1).lower()
                break
                
        # Add date context to display time if both are present
        if entities.get("time") and entities.get("date"):
            if entities.get("display_time"):
                entities["display_time"] = f"{entities['date']} at {entities['display_time']}"
            
        logger.debug(f"Final normalized entities: {entities}")
        
        # Extract participant entities from original message to preserve case
        participant_patterns = [
            r'(?:with|and)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "with Bob Smith"
            r'(?:^|\s)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'  # Names at start or after space
        ]
        
        participants = set()
        for pattern in participant_patterns:
            for match in re.finditer(pattern, original_message):
                name = match.group(1).strip()
                if name and not any(word.lower() in ['with', 'and', 'at', 'by', 'on', 'for'] for word in name.split()):
                    participants.add(name)
                
        if participants:
            entities["participants"] = sorted(list(participants))

        # Combine with previous entities if in follow-up
        if current_state and "entities" in current_state:
            prev_entities = current_state["entities"]
            for key, value in prev_entities.items():
                if value and key not in entities:
                    if key == "participants":
                        # Merge participant lists
                        current = set(entities.get("participants", []))
                        current.update(value)
                        entities["participants"] = sorted(list(current))
                    else:
                    entities[key] = value

        logger.debug(f"Final entities before normalization: {entities}")
        return entities

    def _normalize_entities(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and validate extracted entities."""
        normalized = {
            "time": entities.get("time"),
            "display_time": entities.get("display_time"),
            "date": entities.get("date"),
            "participants": entities.get("participants", [])
        }
        
        if normalized["time"]:
            time_str = normalized["time"].lower()
            try:
                # Handle natural language times
                if time_str in ["morning", "afternoon", "evening", "noon", "midnight"]:
                    normalized["time"] = time_str
                    normalized["display_time"] = time_str
                else:
                    # Parse time components
                    time_match = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(?:am|pm)?', time_str)
        if time_match:
                        hour = int(time_match.group(1))
                        minutes = time_match.group(2) or "00"
                        
                        # Store 24-hour format for machine processing
                        if "pm" in time_str.lower() and hour < 12:
                            normalized["time"] = f"{hour+12}:{minutes}"
                        elif "am" in time_str.lower() and hour == 12:
                            normalized["time"] = f"00:{minutes}"
                        else:
                            normalized["time"] = f"{hour:02d}:{minutes}"
                        
                        # Store 12-hour format for display
                        if hour > 12:
                            display_hour = hour - 12
                            normalized["display_time"] = f"{display_hour}:{minutes}pm"
                        elif hour == 12:
                            normalized["display_time"] = f"12:{minutes}pm"
                        elif hour == 0:
                            normalized["display_time"] = f"12:{minutes}am"
                        else:
                            if "pm" in time_str.lower():
                                normalized["display_time"] = f"{hour}:{minutes}pm"
                            else:
                                normalized["display_time"] = f"{hour}:{minutes}am"
                    else:
                        # If we can't parse it, keep the original
                        normalized["time"] = time_str
                        normalized["display_time"] = time_str
            except Exception as e:
                logger.warning(f"Error normalizing time: {str(e)}")
                normalized["time"] = time_str
                normalized["display_time"] = time_str
                
        if normalized["date"]:
            normalized["date"] = normalized["date"].lower()
            # Only add date context to display time if it's not a natural language time
            if normalized.get("display_time") and normalized["display_time"] not in ["morning", "afternoon", "evening", "noon", "midnight"]:
                normalized["display_time"] = f"{normalized['date']} at {normalized['display_time']}"
                
        if normalized["participants"]:
            normalized["participants"] = sorted(list(set(
                name.strip() for name in normalized["participants"]
                if name.strip() and len(name.split()) <= 2
            )))
            
        return normalized

    def _calculate_urgency(self, text: str) -> float:
        """
        Calculate message urgency based on multiple factors.
        
        Factors considered:
        - Urgent keywords and their weights
        - Exclamation marks
        - Time pressure words
        - Text emphasis (ALL CAPS)
        - Temporal context
        
        Returns:
            float: Urgency score between 0.0 and 1.0
        """
        urgency_score = 0.0
        
        # Check for urgent keywords with higher weights
        urgent_words = {
            "urgent": 0.5,
            "asap": 0.5,
            "emergency": 0.6,
            "immediately": 0.5,
            "right away": 0.5,
            "critical": 0.5,
            "important": 0.4
        }
        
        for word, weight in urgent_words.items():
            if word in text.lower():
                urgency_score += weight
        
        # Check for exclamation marks (up to 0.2)
        urgency_score += min(0.2, text.count('!') * 0.1)
        
        # Check for time pressure words
        pressure_words = {
            "deadline": 0.3,
            "due": 0.3,
            "today": 0.4,
            "tomorrow": 0.3,
            "asap": 0.4,
            "now": 0.3,
            "soon": 0.2,
            "this week": 0.2,
            "next week": 0.1
        }
        
        # Add base urgency for any time-related request
        has_time_pressure = False
        for word, weight in pressure_words.items():
            if word in text.lower():
                urgency_score += weight
                has_time_pressure = True
        
        # If there's any time pressure but no urgent words, ensure minimum medium urgency
        if has_time_pressure and not any(word in text.lower() for word in urgent_words):
            urgency_score = max(urgency_score, 0.3)
        
        # Check for ALL CAPS (indicates emphasis)
        if text.isupper() and len(text) > 5:
            urgency_score += 0.2
        
        # Add base urgency for any request (minimum 0.1)
        urgency_score = max(0.1, urgency_score)
        
        return min(1.0, urgency_score)
    
    def _extract_temporal_context(self, text: str) -> Dict[str, Any]:
        """Extract time-related context from the message."""
        temporal = {
            "has_deadline": False,
            "timeframe": None,
            "specific_day": None
        }
        
        # Check each time pattern
        for timeframe, pattern in self.time_patterns.items():
            if re.search(pattern, text):
                temporal["has_deadline"] = True
                if timeframe == "specific_day":
                    # Extract the specific day mentioned
                    match = re.search(pattern, text)
                    if match:
                        temporal["specific_day"] = match.group()
                else:
                    temporal["timeframe"] = timeframe
        
        return temporal 

    def _error_response(self, error_msg: str, message: str = "") -> Dict[str, Any]:
        """Generate error response."""
        return {
            "status": "error",
            "error": error_msg,
            "raw_text": message or "",
            "intent": None,
            "all_intents": [],
            "entities": {},
            "urgency": 0.0
        } 

    def update_request(self, request: Request, intent: str = None, intent_type: str = None, 
                       entities: Dict = None, confidence: float = None) -> bool:
        """Update the request with new information if provided."""
        changes_made = False
        
        if intent and intent != request.intent:
            request.intent = intent
            changes_made = True
            
        if intent_type and intent_type != request.intent_type:
            request.intent_type = intent_type
            changes_made = True
            
        if confidence is not None and confidence != request.confidence:
            request.confidence = confidence
            changes_made = True
            
        if entities:
            # Initialize request.entities if empty
            if not request.entities:
                request.entities = {}
                
            # Merge new entities with existing ones
            for key, value in entities.items():
                if key not in request.entities or request.entities[key] != value:
                    request.entities[key] = value
                    changes_made = True
                    
            logger.debug(f"Updated request entities: {request.entities}")
            
        return changes_made 