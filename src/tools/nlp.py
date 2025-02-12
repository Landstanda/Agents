from typing import Dict, Any, Optional
import re
import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

class NLPAnalyzer:
    """
    Analyzes incoming Slack messages to identify intents and extract entities.
    Uses a local lexicon built from Services to match intents.
    """
    
    def __init__(self, services_path: str = "src/services/services.yaml"):
        self.services_path = Path(services_path)
        self.lexicon = {}
        self.refresh_lexicon()
        
    def refresh_lexicon(self):
        """Rebuild lexicon from services file."""
        try:
            if not self.services_path.exists():
                logger.warning(f"Services file not found at {self.services_path}")
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
                    
        except Exception as e:
            logger.error(f"Error loading services lexicon: {str(e)}")
    
    def analyze_message(self, message: str, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a message to identify intent and extract entities.
        
        Args:
            message: The message text
            user_info: Information about the user who sent the message
            
        Returns:
            Dict containing:
                - status: "matched", "incomplete", or "unknown"
                - service: Service name if matched
                - intent: Identified intent
                - entities: Extracted entities
                - missing_entities: List of required but missing entities
        """
        if not message:
            return {
                'status': 'error',
                'error': 'Empty message'
            }
            
        # Clean and lowercase message for matching
        clean_message = message.lower().strip()
        
        # Try to match against lexicon
        matched_service = None
        matched_intent = None
        required_entities = []
        
        # First try exact matches
        for key, info in self.lexicon.items():
            if key in clean_message:
                matched_service = info['service']
                matched_intent = info['intent']  # Use the actual intent
                required_entities = info['required_entities']
                break
                
        # If no exact match, try fuzzy matching triggers
        if not matched_service:
            for key, info in self.lexicon.items():
                # Check if all words in the trigger appear in the message
                key_words = set(key.split())
                message_words = set(clean_message.split())
                if key_words.issubset(message_words):
                    matched_service = info['service']
                    matched_intent = info['intent']  # Use the actual intent
                    required_entities = info['required_entities']
                    break
        
        if not matched_service:
            return {
                'status': 'unknown',
                'message': clean_message,
                'user_info': user_info
            }
            
        # Extract entities
        entities = self._extract_entities(message)
        
        # Check for key=value pairs
        for pair in message.split():
            if '=' in pair:
                key, value = pair.split('=', 1)
                entities[key.strip()] = value.strip()
        
        # Check for missing required entities
        missing_entities = [
            entity for entity in required_entities
            if entity not in entities or not entities[entity]
        ]
        
        if missing_entities:
            return {
                'status': 'incomplete',
                'service': matched_service,
                'intent': matched_intent,
                'entities': entities,
                'missing_entities': missing_entities,
                'user_info': user_info
            }
            
        return {
            'status': 'matched',
            'service': matched_service,
            'intent': matched_intent,
            'entities': entities,
            'user_info': user_info
        }
    
    def _extract_entities(self, message: str) -> Dict[str, Any]:
        """Extract entities from message."""
        entities = {}
        
        # Extract time
        time_patterns = [
            r'\b(\d{1,2}(?::\d{2})?)\s*(?:am|pm)\b',
            r'\b(\d{1,2}:\d{2})\b',
            r'\b(morning|afternoon|evening|noon|midnight)\b'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, message.lower())
            if match:
                entities['time'] = match.group(1)
                break
                
        # Extract date
        date_patterns = [
            r'\b(today|tomorrow|next week)\b',
            r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?))\b'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, message.lower())
            if match:
                entities['date'] = match.group(1)
                break
                
        # Extract participants (names starting with capital letters)
        participant_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        participants = re.findall(participant_pattern, message)
        if participants:
            entities['participants'] = participants
            
        return entities 