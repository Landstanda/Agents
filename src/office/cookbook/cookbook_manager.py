import os
import yaml
import logging
from typing import Dict, List, Any, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class CookbookManager:
    """Manages recipes and ingredients for the office."""
    
    def __init__(self):
        """Initialize the cookbook manager."""
        self.cookbook_path = os.path.join(os.path.dirname(__file__), "recipes.yaml")
        self.cookbook = self._load_cookbook()
        
    def _load_cookbook(self) -> Dict[str, Any]:
        """Load the cookbook from YAML file."""
        try:
            with open(self.cookbook_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading cookbook: {str(e)}")
            return {"ingredients": {}, "recipes": {}}
            
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
            
            for recipe_id, recipe in self.cookbook["recipes"].items():
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
            recipe = self.cookbook["recipes"][recipe_id]
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
        for category in self.cookbook["ingredients"].values():
            for ingredient in category:
                if ingredient["name"] == ingredient_name:
                    return ingredient
        return None
    
    def list_available_ingredients(self) -> Dict[str, List[str]]:
        """Get a list of all available ingredients by category."""
        return {
            category: [i["name"] for i in ingredients]
            for category, ingredients in self.cookbook["ingredients"].items()
        }
    
    def get_recipe_details(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """Get full details about a specific recipe."""
        return self.cookbook["recipes"].get(recipe_id) 