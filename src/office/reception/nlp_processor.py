from typing import Dict, Any, List, Optional
import re
import logging
from datetime import datetime
from dateutil import parser
import pytz

logger = logging.getLogger(__name__)

class NLPProcessor:
    """
    Handles natural language processing for the Front Desk.
    Extracts intents, entities, and contextual information from user messages.
    """
    
    def __init__(self, cookbook_manager=None):
        """Initialize the NLP processor with cookbook lexicon."""
        # Add conversation state tracking
        self.conversation_state = {}  # Format: {channel_id: {last_intent, entities, timestamp}}
        self.state_timeout = 300  # 5 minutes
        self.cookbook_manager = cookbook_manager
        self.task_lexicon = self._build_task_lexicon()
        self.flow_logger = None  # Will be set by front_desk
        
        # Initialize patterns
        self._initialize_patterns()
        
    def _initialize_patterns(self):
        """Initialize all the pattern dictionaries."""
        # Add conversational patterns
        self.conversational_patterns = {
            "greeting": [
                r"\b(hi|hello|hey|good morning|good afternoon|good evening)\b",
                r"\bhow are you\b",
                r"\bnice to meet you\b"
            ],
            "farewell": [
                r"\b(goodbye|bye|see you|talk to you later)\b"
            ],
            "gratitude": [
                r"\b(thank you|thanks|appreciate it)\b"
            ],
            "pleasantry": [
                r"\bhow('s| is) it going\b",
                r"\bhow are you\b",
                r"\bhope you('re| are) well\b"
            ],
            "acknowledgment": [
                r"\b(ok|okay|got it|understood|alright|i see)\b"
            ],
            "affirmative": [
                r"\b(yes|yeah|yep|sure|definitely|absolutely)\b"
            ],
            "negative": [
                r"\b(no|nope|not really|negative)\b"
            ]
        }
        
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

    def _build_task_lexicon(self):
        """Build lexicon from cookbook recipes."""
        lexicon = {
            "intents": {},  # Map of words/phrases to intents
            "aliases": {},  # Intent aliases (e.g., "scheduling" -> "schedule_meeting")
            "entities": {}  # Entity extraction patterns per intent
        }
        
        if self.cookbook_manager:
            for recipe_name, recipe in self.cookbook_manager.recipes.items():
                intent = recipe.get("intent")
                if intent:
                    # Add all keywords
                    for keyword in recipe.get("keywords", []):
                        lexicon["intents"][keyword.lower()] = intent
                    
                    # Add all triggers
                    for trigger in recipe.get("common_triggers", []):
                        lexicon["intents"][trigger.lower()] = intent
                    
                    # Add intent aliases
                    if intent == "schedule_meeting":
                        lexicon["aliases"].update({
                            "scheduling": intent,
                            "appointment": intent,
                            "book meeting": intent,
                            "set up meeting": intent
                        })
                    elif intent == "email_read":
                        lexicon["aliases"].update({
                            "check_email": intent,
                            "view_email": intent,
                            "show_email": intent,
                            "get_email": intent
                        })
                    
                    # Add entity patterns
                    lexicon["entities"][intent] = recipe.get("required_entities", [])
        
        return lexicon

    def refresh_lexicon(self):
        """Rebuild the task lexicon from the cookbook."""
        self.task_lexicon = self._build_task_lexicon()

    async def process_message(self, message: str, user_info: Dict[str, Any], channel_id: str = None) -> Dict[str, Any]:
        """Process a message with enhanced intent classification."""
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
            
            # Extract entities
            entities = self._extract_entities(message, current_state)
            
            # Calculate urgency
            urgency = self._calculate_urgency(message)
            
            # Extract temporal context
            temporal = self._extract_temporal_context(message)
            
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
                    "user_id": user_info.get("id")
                })

            # Determine if this needs request tracking
            needs_tracking = intent_info["intent_type"] == "task"

            result = {
                "status": "success",
                "raw_text": message,
                "intent": intent_info["primary_intent"],
                "intent_type": intent_info["intent_type"],
                "all_intents": intent_info["all_intents"],
                "confidence": intent_info["confidence"],
                "entities": entities,
                "urgency": urgency,
                "temporal_context": temporal,
                "user_context": user_context,
                "conversation_state": current_state,
                "needs_tracking": needs_tracking
            }

            if self.flow_logger:
                await self.flow_logger.log_event(
                    "NLP Processor",
                    "Message Analysis",
                    {
                        "intent": result["intent"],
                        "intent_type": result["intent_type"],
                        "confidence": result["confidence"],
                        "entities": entities,
                        "urgency": urgency,
                        "needs_tracking": needs_tracking,
                        "message_length": len(message)
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

    def _extract_intents(self, text: str, current_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract intents with enhanced classification."""
        intent_info = {
            "primary_intent": None,
            "intent_type": None,  # "conversational" or "task"
            "all_intents": [],
            "confidence": 0.0
        }

        # Clean and normalize text
        text = text.lower()
        words = [word.rstrip('.,!?') for word in text.split()]
        text = ' '.join(words)
        
        logger.debug(f"Extracting intents from: {text}")
        
        # First check for conversational intents
        for intent_type, patterns in self.conversational_patterns.items():
            if any(re.search(pattern, text) for pattern in patterns):
                logger.debug(f"Found conversational intent: {intent_type}")
                intent_info["primary_intent"] = intent_type
                intent_info["intent_type"] = "conversational"
                intent_info["all_intents"].append(intent_type)
                intent_info["confidence"] = 0.9
                return intent_info
        
        # Check task lexicon for exact matches
        for phrase, intent in self.task_lexicon["intents"].items():
            if phrase in text:
                logger.debug(f"Found exact task match: {phrase} -> {intent}")
                intent_info["primary_intent"] = intent
                intent_info["intent_type"] = "task"
                intent_info["all_intents"].append(intent)
                intent_info["confidence"] = 0.9
                return intent_info
        
        # Check aliases
        for alias, intent in self.task_lexicon["aliases"].items():
            if alias in text:
                logger.debug(f"Found task alias match: {alias} -> {intent}")
                intent_info["primary_intent"] = intent
                intent_info["intent_type"] = "task"
                intent_info["all_intents"].append(intent)
                intent_info["confidence"] = 0.8
                return intent_info
        
        # More flexible matching for tasks
        words = set(words)
        
        # Check for email-related terms
        email_terms = {"email", "emails", "mail", "inbox", "message", "messages"}
        if email_terms & words:
            read_terms = {"check", "see", "look", "show", "get", "have", "any", "new"}
            send_terms = {"send", "write", "compose"}
            
            if read_terms & words:
                intent_info["primary_intent"] = "email_read"
                intent_info["intent_type"] = "task"
                intent_info["confidence"] = 0.7
            elif send_terms & words:
                intent_info["primary_intent"] = "email_send"
                intent_info["intent_type"] = "task"
                intent_info["confidence"] = 0.7
        
        # Check for meeting/scheduling terms
        schedule_terms = {"schedule", "meeting", "appointment", "book", "set", "setup"}
        if schedule_terms & words:
            intent_info["primary_intent"] = "schedule_meeting"
            intent_info["intent_type"] = "task"
            intent_info["confidence"] = 0.7
        
        if intent_info["primary_intent"]:
            intent_info["all_intents"].append(intent_info["primary_intent"])
        
        return intent_info

    def _extract_entities(self, text: str, current_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract entities with conversation context."""
        entities = {
            "people": [],
            "dates": [],
            "numbers": [],
            "emails": [],
            "email_attributes": [],
            "time": None,
            "participants": []
        }

        # Extract time information first
        time_info = self._extract_time_info(text)
        if time_info:
            entities["time"] = time_info

        # Extract participants
        participants = self._extract_participants(text)
        if participants:
            entities["participants"] = participants

        # Combine with previous entities if available
        if current_state and "entities" in current_state:
            prev_entities = current_state["entities"]
            # Only keep non-empty values from previous state
            for key, value in prev_entities.items():
                if value and not entities.get(key):
                    entities[key] = value

        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        entities["emails"] = re.findall(email_pattern, text)
        
        # Extract email attributes being requested
        for attr_type, pattern in self.email_patterns.items():
            if re.search(pattern, text):
                entities["email_attributes"].append(attr_type)
        
        # Extract numbers
        number_pattern = r'\b\d+\b'
        entities["numbers"] = re.findall(number_pattern, text)
        
        return entities

    def _extract_time_info(self, text: str) -> Optional[str]:
        """
        Enhanced time extraction with support for various formats.
        
        Handles:
        - 12/24 hour formats
        - AM/PM indicators
        - Natural language time references (morning, afternoon, evening)
        - Relative time (today, tomorrow)
        - Contextual time inference
        
        Args:
            text: The message text to process
            
        Returns:
            Optional[str]: Normalized time string or None if no time found
        """
        if not text:
            return None
            
        text = text.lower().strip()
        
        # Try to extract specific time first
        time_match = re.search(r"(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.|morning|afternoon|evening)?", text)
        if time_match:
            hour = int(time_match.group(1))
            minutes = time_match.group(2) or "00"
            period = time_match.group(3)
            
            # Determine AM/PM
            if period:
                if any(p in period for p in ["pm", "p.m.", "afternoon", "evening"]):
                    if hour < 12:
                        hour += 12
                elif any(p in period for p in ["am", "a.m.", "morning"]):
                    if hour == 12:
                        hour = 0
            elif hour < 7:  # Assume PM for times like 2:00 without AM/PM
                hour += 12
            
            time_str = f"{hour:02d}:{minutes}"
            
            # Look for date context
            if "tomorrow" in text:
                return f"tomorrow at {time_str}"
            elif "today" in text:
                return f"today at {time_str}"
            else:
                return time_str
        
        # Check for general time indicators
        for time_indicator in ["morning", "afternoon", "evening", "noon", "midnight"]:
            if time_indicator in text:
                if "tomorrow" in text:
                    return f"tomorrow {time_indicator}"
                elif "today" in text:
                    return f"today {time_indicator}"
                return time_indicator
        
        # Check for just date indicators
        if "tomorrow" in text:
            return "tomorrow"
        elif "today" in text:
            return "today"
        
        return None

    def _extract_participants(self, text: str) -> List[str]:
        """
        Enhanced participant name extraction from natural language.
        
        Strategies:
        1. Extracts names following "with" or "and"
        2. Identifies standalone capitalized names
        3. Filters out common words and false positives
        4. Handles multi-word names
        
        Args:
            text: The message text to process
            
        Returns:
            List[str]: List of extracted participant names
        """
        participants = []
        
        # Common words to ignore
        ignore_words = {"hi", "hey", "hello", "dear", "thanks", "thank", "with", "and"}
        
        # First try to extract from "with X" or "and X" patterns
        with_pattern = r"(?:with|and)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
        matches = re.finditer(with_pattern, text)
        for match in matches:
            name = match.group(1)
            if name.lower() not in ignore_words:
                participants.append(name)
        
        # Then look for standalone capitalized names
        name_pattern = r"(?:^|\s)([A-Z][a-z]+)(?=\s|$|\?|\.)"
        matches = re.finditer(name_pattern, text)
        for match in matches:
            name = match.group(1)
            if (name.lower() not in ignore_words and 
                name not in participants):
                participants.append(name)
        
        return participants

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