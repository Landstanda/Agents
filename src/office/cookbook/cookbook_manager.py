import os
import yaml
import logging
from typing import Dict, List, Any, Optional, Tuple
from difflib import SequenceMatcher
from pathlib import Path

logger = logging.getLogger(__name__)

class CookbookManager:
    """
    Manages the storage and retrieval of task recipes.
    A recipe defines how to accomplish a specific type of task,
    including the steps, required parameters, and success criteria.
    """
    
    def __init__(self):
        """Initialize the cookbook manager."""
        self.recipes_file = Path("src/office/cookbook/recipes.yaml")
        self.recipes = self._load_recipes()
        self.nlp_processors = set()  # Track NLP processors using this cookbook
        self.flow_logger = None  # Will be set by front_desk
        if not self.recipes:
            self._initialize_default_recipes()
        logger.info(f"Loaded {len(self.recipes)} recipes from cookbook")
    
    def _initialize_default_recipes(self):
        """Initialize the cookbook with some default recipes."""
        default_recipes = {
            "Document Management": {
                "name": "Document Management",
                "intent": "document",
                "description": "Create and manage documents",
                "steps": [
                    {"type": "api_call", "action": "create_document", "params": {"type": "{doc_type}"}},
                    {"type": "api_call", "action": "add_content", "params": {"content": "{content}"}}
                ],
                "required_entities": ["doc_type"],
                "keywords": ["document", "create", "write", "record"],
                "common_triggers": ["create a document", "write documentation"],
                "success_criteria": ["Document created", "Content added"]
            },
            "Research Report": {
                "name": "Research Report",
                "intent": "research",
                "description": "Research a topic and create a detailed report",
                "steps": [
                    {"type": "api_call", "action": "search_info", "params": {"topic": "{topic}"}},
                    {"type": "api_call", "action": "analyze_results", "params": {"depth": "detailed"}},
                    {"type": "api_call", "action": "create_summary", "params": {"format": "report"}}
                ],
                "required_entities": ["topic"],
                "keywords": ["research", "analyze", "report", "investigate"],
                "common_triggers": ["research about", "analyze topic"],
                "success_criteria": ["Research completed", "Report created"]
            },
            "Meeting Scheduler": {
                "name": "Meeting Scheduler",
                "intent": "schedule_meeting",
                "description": "Schedule a meeting with participants",
                "steps": [
                    {
                        "type": "api_call",
                        "action": "check_availability",
                        "params": {"time": "{time}", "participants": "{participants}"}
                    },
                    {
                        "type": "api_call",
                        "action": "create_meeting",
                        "params": {"time": "{time}", "participants": "{participants}"}
                    }
                ],
                "required_entities": ["time", "participants"],
                "keywords": ["schedule", "meeting", "calendar", "invite"],
                "common_triggers": ["schedule a meeting", "set up a meeting"],
                "success_criteria": ["Meeting scheduled", "Invites sent"]
            }
        }
        self.recipes = default_recipes
        self._save_recipes()
    
    def _save_recipes(self):
        """Save recipes to the YAML file."""
        try:
            self.recipes_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.recipes_file, 'w') as f:
                yaml.safe_dump(self.recipes, f)
        except Exception as e:
            logger.error(f"Error saving recipes: {str(e)}")
    
    def _load_recipes(self) -> Dict[str, Any]:
        """Load recipes from the YAML file."""
        try:
            if not self.recipes_file.exists():
                logger.warning(f"Recipes file not found at {self.recipes_file}, will create with defaults")
                return {}
            
            with open(self.recipes_file, 'r') as f:
                recipes = yaml.safe_load(f) or {}
                
            # Validate loaded recipes
            valid_recipes = {}
            for name, recipe in recipes.items():
                if isinstance(recipe, dict) and all(field in recipe for field in [
                    "name", "intent", "description", "steps",
                    "required_entities", "keywords", "common_triggers",
                    "success_criteria"
                ]):
                    valid_recipes[name] = recipe
                else:
                    logger.warning(f"Skipping invalid recipe: {name}")
            
            return valid_recipes
        except Exception as e:
            logger.error(f"Error loading recipes: {str(e)}")
            return {}
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using SequenceMatcher."""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    async def find_matching_recipe(self, nlp_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find a recipe that matches the NLP result.
        
        Args:
            nlp_result: The processed NLP result containing intent and entities
            
        Returns:
            Matching recipe if found, None otherwise
        """
        try:
            intent = nlp_result.get("intent")
            all_intents = nlp_result.get("all_intents", [])
            if intent:
                all_intents = [intent] + [i for i in all_intents if i != intent]
            
            if not all_intents:
                return None
            
            matches = []
            keywords = set(nlp_result.get("keywords", []))
            
            # Try exact and fuzzy intent matching
            for recipe_name, recipe in self.recipes.items():
                recipe_intent = recipe.get("intent", "")
                
                # Skip invalid recipes
                if not recipe_intent or not isinstance(recipe, dict):
                    continue
                
                # Calculate intent match score
                intent_scores = []
                for user_intent in all_intents:
                    # Exact match gets highest score
                    if user_intent == recipe_intent:
                        intent_scores.append(1.0)
                    # Partial string match
                    elif user_intent in recipe_intent or recipe_intent in user_intent:
                        intent_scores.append(0.8)
                    # Fuzzy match
                    else:
                        intent_scores.append(self._calculate_similarity(recipe_intent, user_intent))
                
                best_intent_score = max(intent_scores) if intent_scores else 0
                
                # Calculate keyword match
                recipe_keywords = set(recipe.get("keywords", []))
                if recipe_keywords:
                    matching_keywords = keywords & recipe_keywords
                    keyword_match = len(matching_keywords) / len(recipe_keywords)
                    
                    # Boost score if important keywords match
                    if any(kw in matching_keywords for kw in ["research", "report", "document"]):
                        keyword_match = min(1.0, keyword_match + 0.2)
                else:
                    keyword_match = 0
                
                # Calculate trigger match
                triggers = recipe.get("common_triggers", [])
                trigger_scores = []
                for trigger in triggers:
                    words = set(trigger.lower().split())
                    if words & keywords:
                        trigger_scores.append(len(words & keywords) / len(words))
                trigger_match = max(trigger_scores) if trigger_scores else 0
                
                # Calculate entity match
                validation = self._validate_recipe_requirements(recipe, nlp_result)
                entity_match = 1.0 if validation["status"] == "success" else 0.5
                
                # Combine scores with weights
                match_score = (
                    0.4 * best_intent_score +  # Intent is important
                    0.2 * keyword_match +      # Keywords help disambiguate
                    0.2 * trigger_match +      # Triggers provide context
                    0.2 * entity_match        # Entities indicate completeness
                )
                
                # Add to matches if score is good enough
                if match_score >= 0.4:  # Lower threshold since we consider entities
                    matches.append((recipe, match_score))
            
            if not matches:
                return None
            
            # Sort by score
            matches.sort(key=lambda x: x[1], reverse=True)
            
            # Return best match if it's a strong match
            best_recipe, best_score = matches[0]
            if best_score >= 0.8:
                return best_recipe
            
            # For exact intent matches, be more lenient with missing entities
            for recipe, score in matches:
                if recipe.get("intent") == intent:
                    return recipe
            
            # For weaker matches, prefer recipes with fewer missing entities
            best_missing = float('inf')
            best_match = None
            
            for recipe, score in matches:
                if score < 0.5:  # Only consider reasonably good matches
                    continue
                    
                validation = self._validate_recipe_requirements(recipe, nlp_result)
                missing = len(validation.get("missing_requirements", []))
                
                if missing < best_missing or (missing == best_missing and score > 0.6):
                    best_missing = missing
                    best_match = recipe
            
            return best_match
            
        except Exception as e:
            logger.error(f"Error finding matching recipe: {str(e)}")
            return None
    
    def register_nlp_processor(self, nlp_processor):
        """Register an NLP processor to receive lexicon updates."""
        self.nlp_processors.add(nlp_processor)
    
    def unregister_nlp_processor(self, nlp_processor):
        """Unregister an NLP processor."""
        self.nlp_processors.discard(nlp_processor)
    
    async def add_recipe(self, recipe: Dict[str, Any]) -> bool:
        """Add a new recipe and update NLP processors."""
        try:
            # Validate recipe
            required_fields = {
                "name", "intent", "description", "steps",
                "required_entities", "keywords", "common_triggers",
                "success_criteria"
            }
            if not all(field in recipe for field in required_fields):
                missing_fields = required_fields - set(recipe.keys())
                if self.flow_logger:
                    await self.flow_logger.log_event(
                        "Cookbook Manager",
                        "Recipe Validation Failed",
                        {
                            "recipe": recipe.get("name", "Unknown"),
                            "missing_fields": list(missing_fields)
                        }
                    )
                logger.error(f"Recipe missing required fields: {missing_fields}")
                return False
            
            # Add recipe to cookbook
            self.recipes[recipe["name"]] = recipe
            
            # Save to file
            self._save_recipes()
            
            # Notify all registered NLP processors
            for nlp in self.nlp_processors:
                nlp.refresh_lexicon()
            
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "Cookbook Manager",
                    "Recipe Added",
                    {
                        "name": recipe["name"],
                        "intent": recipe["intent"],
                        "steps": len(recipe["steps"]),
                        "required_entities": recipe["required_entities"]
                    }
                )
            
            logger.info(f"Added new recipe: {recipe['name']}")
            return True
            
        except Exception as e:
            error_msg = f"Error adding recipe: {str(e)}"
            logger.error(error_msg)
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "Cookbook Manager",
                    "Recipe Addition Failed",
                    {
                        "error": error_msg,
                        "recipe": recipe.get("name", "Unknown")
                    }
                )
            return False
    
    async def get_recipe(self, intent: str) -> Dict[str, Any]:
        """Get a recipe by intent with detailed response about match status."""
        try:
            if not intent:
                if self.flow_logger:
                    await self.flow_logger.log_event(
                        "Cookbook Manager",
                        "Recipe Lookup Failed",
                        {
                            "error": "No intent provided",
                            "status": "not_found"
                        }
                    )
                return {
                    "status": "not_found",
                    "recipe": None,
                    "missing_requirements": [],
                    "suggested_next_steps": "consult_ceo",
                    "details": "No intent provided"
                }
            
            # First try exact match
            for recipe in self.recipes.values():
                if recipe.get("intent") == intent:
                    result = self._validate_recipe_requirements(recipe, intent)
                    if self.flow_logger:
                        await self.flow_logger.log_event(
                            "Cookbook Manager",
                            "Recipe Found",
                            {
                                "intent": intent,
                                "recipe": recipe["name"],
                                "status": result["status"],
                                "missing_requirements": result.get("missing_requirements", [])
                            }
                        )
                    return result
                
            # Then try partial match
            for recipe in self.recipes.values():
                recipe_intent = recipe.get("intent", "")
                if recipe_intent and (intent in recipe_intent or recipe_intent in intent):
                    result = self._validate_recipe_requirements(recipe, intent)
                    if self.flow_logger:
                        await self.flow_logger.log_event(
                            "Cookbook Manager",
                            "Recipe Found (Partial Match)",
                            {
                                "intent": intent,
                                "recipe": recipe["name"],
                                "status": result["status"],
                                "missing_requirements": result.get("missing_requirements", [])
                            }
                        )
                    return result
                
            # Special case for scheduling intents
            if any(term in intent.lower() for term in ["schedule", "meeting", "appointment"]):
                schedule_recipe = self.recipes.get("schedule_meeting")
                if schedule_recipe:
                    result = self._validate_recipe_requirements(schedule_recipe, intent)
                    if self.flow_logger:
                        await self.flow_logger.log_event(
                            "Cookbook Manager",
                            "Recipe Found (Special Case)",
                            {
                                "intent": intent,
                                "recipe": "schedule_meeting",
                                "status": result["status"],
                                "missing_requirements": result.get("missing_requirements", [])
                            }
                        )
                    return result
            
            # No recipe found
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "Cookbook Manager",
                    "Recipe Not Found",
                    {
                        "intent": intent,
                        "status": "not_found"
                    }
                )
            return {
                "status": "not_found",
                "recipe": None,
                "missing_requirements": [],
                "suggested_next_steps": "consult_ceo",
                "details": f"No recipe found for intent: {intent}"
            }
            
        except Exception as e:
            error_msg = f"Error getting recipe: {str(e)}"
            logger.error(error_msg)
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "Cookbook Manager",
                    "Recipe Lookup Error",
                    {
                        "error": error_msg,
                        "intent": intent
                    }
                )
            return {
                "status": "error",
                "recipe": None,
                "missing_requirements": [],
                "suggested_next_steps": "consult_ceo",
                "details": error_msg
            }
    
    def _validate_recipe_requirements(self, recipe: Dict[str, Any], entities: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that all required entities for a recipe are present."""
        if not recipe or not entities:
            return {
                "status": "error",
                "recipe": None,
                "missing_requirements": [],
                "suggested_next_steps": "consult_ceo",
                "details": "Invalid recipe or entities"
            }
            
        required_entities = recipe.get("required_entities", [])
        missing_entities = []
        
        for entity in required_entities:
            if entity not in entities or not entities[entity]:
                missing_entities.append(entity)
                
        if not missing_entities:
            return {
                "status": "success",
                "recipe": recipe,
                "missing_requirements": [],
                "suggested_next_steps": "execute_recipe",
                "details": "All required entities present"
            }
        else:
            return {
                "status": "missing_info",
                "recipe": recipe,
                "missing_requirements": missing_entities,
                "suggested_next_steps": "request_info",
                "details": f"Missing required entities: {', '.join(missing_entities)}"
            }
    
    def list_recipes(self) -> List[str]:
        """Get a list of all recipe names."""
        return list(self.recipes.keys())
    
    def find_matching_recipes(self, request: str) -> List[Tuple[str, float]]:
        """
        Find recipes that match the given request.
        
        Args:
            request (str): The user's request
            
        Returns:
            List[Tuple[str, float]]: List of (recipe_name, match_score) tuples
        """
        matches = set()  # Use set to avoid duplicates
        request_lower = request.lower()
        
        # Split compound requests on common conjunctions and punctuation
        sub_requests = []
        for part in request_lower.replace(" and ", ". ").replace(",", ".").split("."):
            part = part.strip()
            if part:
                # Further split on action verbs if possible
                action_splits = [s.strip() for s in part.split(" to ")]
                sub_requests.extend(action_splits)
        
        # Common action verbs that might indicate separate tasks
        action_verbs = ["check", "schedule", "create", "prepare", "research", "analyze", "send"]
        
        for sub_request in sub_requests:
            sub_request_words = set(sub_request.split())
            
            # Check if this sub-request contains any action verbs
            contains_action = any(verb in sub_request_words for verb in action_verbs)
            
            for recipe_id, recipe in self.recipes.items():
                match_score = 0.0
                
                # Check for exact trigger matches
                for trigger in recipe["common_triggers"]:
                    trigger_lower = trigger.lower()
                    if trigger_lower in sub_request:
                        match_score = max(match_score, 0.9)
                    elif all(word in sub_request for word in trigger_lower.split()):
                        match_score = max(match_score, 0.8)
                
                # If no trigger match, check word overlap
                if match_score == 0.0:
                    # Check description overlap
                    desc_words = set(recipe["description"].lower().split())
                    word_overlap = len(sub_request_words.intersection(desc_words))
                    if word_overlap > 0:
                        overlap_score = word_overlap / max(len(sub_request_words), len(desc_words))
                        match_score = max(match_score, overlap_score)
                    
                    # Check trigger word overlap
                    for trigger in recipe["common_triggers"]:
                        trigger_words = set(trigger.lower().split())
                        overlap = len(sub_request_words.intersection(trigger_words))
                        if overlap > 0:
                            overlap_score = overlap / max(len(sub_request_words), len(trigger_words))
                            match_score = max(match_score, overlap_score)
                
                # Boost score if the sub-request contains action verbs
                if contains_action and match_score > 0:
                    match_score = min(1.0, match_score + 0.1)
                
                if match_score > 0.35:
                    matches.add((recipe_id, match_score))
        
        # Convert set to list and sort by match score
        return sorted(list(matches), key=lambda x: x[1], reverse=True)
    
    def analyze_request(self, request: str) -> Dict[str, Any]:
        """
        Analyze a request and determine the best recipe(s) to handle it.
        
        Args:
            request (str): The user's request
            
        Returns:
            Dict containing:
                - matched_recipes: List of matching recipes with scores
                - required_ingredients: List of required ingredients
                - success_criteria: Combined success criteria
                - confidence: Overall confidence in the match
        """
        matches = self.find_matching_recipes(request)
        
        if not matches:
            return {
                "status": "no_match",
                "matched_recipes": [],
                "required_ingredients": [],
                "success_criteria": [],
                "confidence": 0.0,
                "notes": "No matching recipes found"
            }
            
        # Get details for top matches (those within 20% of the best match)
        best_score = matches[0][1]
        top_matches = [m for m in matches if m[1] >= best_score * 0.8]
        
        # Collect details from all top matches
        matched_recipes = []
        all_ingredients = set()
        all_criteria = set()
        
        for recipe_id, score in top_matches:
            recipe = self.recipes[recipe_id]
            matched_recipes.append({
                "name": recipe["name"],
                "match_score": score,
                "description": recipe["description"]
            })
            all_ingredients.update(recipe["required_ingredients"])
            all_criteria.update(recipe["success_criteria"])
        
        return {
            "status": "success",
            "matched_recipes": matched_recipes,
            "required_ingredients": list(all_ingredients),
            "success_criteria": list(all_criteria),
            "confidence": best_score,
            "notes": f"Found {len(matched_recipes)} relevant recipes"
        }
    
    def get_ingredient_details(self, ingredient_name: str) -> Optional[Dict[str, Any]]:
        """Get details about a specific ingredient."""
        for category in self.recipes["ingredients"].values():
            for ingredient in category:
                if ingredient["name"] == ingredient_name:
                    return ingredient
        return None
    
    def list_available_ingredients(self) -> Dict[str, List[str]]:
        """Get a list of all available ingredients by category."""
        return {
            category: [i["name"] for i in ingredients]
            for category, ingredients in self.recipes["ingredients"].items()
        }
    
    def get_recipe_details(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """Get full details about a specific recipe."""
        return self.recipes.get(recipe_id) 