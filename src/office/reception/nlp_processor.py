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
            ]
        }
        
        # Initialize cookbook integration
        self.cookbook_manager = cookbook_manager
        self.task_lexicon = self._build_task_lexicon()
        
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
        """Process a message with conversation context."""
        try:
            if not message or not user_info:
                return self._error_response("Missing required input", message)

            # Check conversation state
            current_state = self._get_conversation_state(channel_id) if channel_id else None
            
            # Try to parse complete datetime first
            try:
                dt = parser.parse(message, fuzzy=True)
                parsed_time = dt.strftime("%Y-%m-%d %I:%M %p")
            except:
                parsed_time = None
            
            # Extract intents first
            all_intents = self._extract_intents(message, current_state)
            
            # If no new intent but we have a previous intent in state, maintain it
            if not all_intents and current_state and current_state.get("last_intent"):
                all_intents = [current_state["last_intent"]]
            
            # Extract entities with context
            entities = self._extract_entities(message, current_state)
            
            # If we parsed a complete datetime, use it
            if parsed_time:
                entities["time"] = parsed_time
            
            # Determine urgency
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

            # Update conversation state
            if channel_id:
                self._update_conversation_state(channel_id, {
                    "last_intent": all_intents[0] if all_intents else None,
                    "entities": entities,
                    "timestamp": datetime.now().timestamp(),
                    "user_id": user_info.get("id")
                })

            return {
                "status": "success",
                "raw_text": message,
                "intent": all_intents[0] if all_intents else None,
                "all_intents": all_intents,
                "entities": entities,
                "urgency": urgency,
                "temporal_context": temporal,
                "user_context": user_context,
                "conversation_state": current_state
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return self._error_response(str(e), message)

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

    def _extract_intents(self, text: str, current_state: Optional[Dict[str, Any]] = None) -> List[str]:
        """Extract intents based on action verbs and patterns."""
        found_intents = []
        # Clean and normalize text
        text = text.lower()
        # Remove punctuation from the end of words but keep internal punctuation
        words = [word.rstrip('.,!?') for word in text.split()]
        text = ' '.join(words)
        
        logger.debug(f"Extracting intents from: {text}")
        
        # First check task lexicon for exact matches
        for phrase, intent in self.task_lexicon["intents"].items():
            if phrase in text:
                logger.debug(f"Found exact match: {phrase} -> {intent}")
                found_intents.append(intent)
                break
        
        # If no exact matches, check aliases
        if not found_intents:
            for alias, intent in self.task_lexicon["aliases"].items():
                if alias in text:
                    logger.debug(f"Found alias match: {alias} -> {intent}")
                    found_intents.append(intent)
                    break
        
        # If still no matches, do more flexible matching
        if not found_intents:
            # Create clean word set for matching
            words = set(words)  # Use the cleaned words from earlier
            logger.debug(f"Checking flexible matching with words: {words}")
            
            # Check for email-related terms
            email_terms = {"email", "emails", "mail", "inbox", "message", "messages"}
            email_match = email_terms & words
            if email_match:
                logger.debug(f"Found email terms: {email_match}")
                # Check for read vs send context
                read_terms = {"check", "see", "look", "show", "get", "have", "any", "new"}
                send_terms = {"send", "write", "compose"}
                
                if read_terms & words:
                    logger.debug(f"Context suggests email_read (matched terms: {read_terms & words})")
                    found_intents.append("email_read")
                elif send_terms & words:
                    logger.debug("Context suggests email_send")
                    found_intents.append("email_send")
                else:
                    logger.debug("Defaulting to email_read")
                    found_intents.append("email_read")
            
            # Check for meeting/scheduling terms
            schedule_terms = {"schedule", "meeting", "appointment", "book", "set", "setup"}
            schedule_match = schedule_terms & words
            if schedule_match:
                logger.debug(f"Found scheduling terms: {schedule_match}")
                found_intents.append("schedule_meeting")
        
        # Only check conversational intents if no task intents were found
        if not found_intents:
            for intent_type, patterns in self.conversational_patterns.items():
                if any(re.search(pattern, text) for pattern in patterns):
                    logger.debug(f"Found conversational intent: {intent_type}")
                    found_intents.append(intent_type)
                    break
        
        logger.debug(f"Final extracted intents: {found_intents}")
        return found_intents
    
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
        """Enhanced time extraction."""
        text = text.lower()
        
        # Try to identify time components
        time_found = None
        period = None
        date_context = None
        
        # Check for time patterns
        time_match = re.search(r"\b(?:1[0-2]|0?[1-9])(?::[0-5][0-9])?\b", text)
        if time_match:
            time_found = time_match.group()
            
            # Look for period indicators
            if "morning" in text or "am" in text or "a.m" in text:
                period = "AM"
            elif "afternoon" in text or "evening" in text or "pm" in text or "p.m" in text:
                period = "PM"
            elif int(time_found.split(":")[0]) < 8:  # Assume PM for times like 6:00 without AM/PM
                period = "PM"
            elif int(time_found.split(":")[0]) < 12:  # Assume AM for times like 9:00 without AM/PM
                period = "AM"
            
            # Add minutes if not present
            if ":" not in time_found:
                time_found += ":00"

        # Check for date context
        if "tomorrow" in text:
            date_context = "tomorrow"
        elif "today" in text:
            date_context = "today"
        
        # Combine components
        if time_found:
            if date_context:
                return f"{date_context} at {time_found} {period if period else ''}"
            return f"{time_found} {period if period else ''}"
            
        return None

    def _extract_participants(self, text: str) -> List[str]:
        """Enhanced participant extraction."""
        participants = []
        
        # Match @mentions, "with Name", "and Name" patterns, and standalone names
        patterns = [
            r"@\w+",  # @mentions
            r"(?:with|and)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",  # with/and followed by name
            r"(?:^|\s)([A-Z][a-z]+)(?=\s|$|\?|\.)",  # Capitalized names, including at end of sentence
            r"(?:with|and)\s*([A-Z][a-z]+)(?=\s|$|\?|\.)"  # with/and directly followed by name
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                # Get the actual name, removing any prefixes
                participant = match.group().strip("@ ").strip("with ").strip("and ")
                if (participant.lower() not in ["with", "and"] and 
                    participant not in participants and
                    len(participant) > 1):  # Avoid single letters
                    participants.append(participant)
        
        return participants

    def _calculate_urgency(self, text: str) -> float:
        """Calculate urgency level based on keywords and patterns."""
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