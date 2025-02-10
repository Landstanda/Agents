from typing import Dict, Any, List, Optional
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class NLPProcessor:
    """
    Handles natural language processing for the Front Desk.
    Extracts intents, entities, and contextual information from user messages.
    """
    
    def __init__(self):
        """Initialize the NLP processor."""
        # Common time-related phrases
        self.time_patterns = {
            "urgent": r"\b(urgent|asap|emergency|right away)\b",
            "today": r"\b(today|tonight)\b",
            "tomorrow": r"\b(tomorrow|next day)\b",
            "next_week": r"\b(next week|upcoming week)\b",
            "specific_day": r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"
        }
        
        # Common action verbs that indicate intent
        self.action_verbs = {
            "communication": ["email", "send", "message", "contact", "write"],
            "scheduling": ["schedule", "book", "arrange", "plan", "set up"],
            "research": ["research", "find", "look up", "investigate", "analyze"],
            "document": ["create", "prepare", "draft", "write", "make"],
            "review": ["review", "check", "examine", "look at", "verify"]
        }
        
    def process_message(self, message: str, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a message and extract structured information.
        
        Args:
            message: The user's message
            user_info: Information about the user
            
        Returns:
            Dict containing:
                - raw_text: Original message
                - intents: List of detected intents
                - entities: Dict of extracted entities
                - urgency: Urgency level (0-1)
                - temporal_context: Time-related information
                - user_context: User-related context
        """
        try:
            # Convert to lowercase for processing
            text = message.lower()
            
            # Extract intents based on action verbs
            intents = self._extract_intents(text)
            
            # Extract entities (people, dates, etc.)
            entities = self._extract_entities(text)
            
            # Determine urgency
            urgency = self._calculate_urgency(text)
            
            # Extract temporal context
            temporal = self._extract_temporal_context(text)
            
            # Build user context
            user_context = {
                "user_id": user_info.get("id"),
                "user_name": user_info.get("real_name"),
                "timestamp": datetime.now().isoformat(),
                "is_dm": user_info.get("is_dm", False)
            }
            
            return {
                "status": "success",
                "raw_text": message,
                "processed_text": text,
                "intents": intents,
                "entities": entities,
                "urgency": urgency,
                "temporal_context": temporal,
                "user_context": user_context
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "raw_text": message
            }
    
    def _extract_intents(self, text: str) -> List[str]:
        """Extract intents based on action verbs and patterns."""
        found_intents = []
        
        # Check each intent category
        for category, verbs in self.action_verbs.items():
            if any(verb in text for verb in verbs):
                found_intents.append(category)
        
        return found_intents
    
    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities like people, dates, numbers, etc."""
        entities = {
            "people": [],
            "dates": [],
            "numbers": [],
            "emails": []
        }
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        entities["emails"] = re.findall(email_pattern, text)
        
        # Extract numbers
        number_pattern = r'\b\d+\b'
        entities["numbers"] = re.findall(number_pattern, text)
        
        # Extract dates (basic patterns)
        date_patterns = [
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',  # MM/DD/YYYY
            r'\b\d{1,2}-\d{1,2}-\d{2,4}\b',  # MM-DD-YYYY
            r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2}\b'  # Month Day
        ]
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            entities["dates"].extend(matches)
        
        return entities
    
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