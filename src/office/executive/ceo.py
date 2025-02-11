from typing import Dict, Any, Optional, List
import logging
import yaml
from pathlib import Path
from openai import AsyncOpenAI
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class CEO:
    """
    The CEO is responsible for high-level decision making and strategy.
    It can analyze unknown requests and create new recipes by combining
    available ingredients (capabilities) in novel ways.
    """
    
    def __init__(self, cookbook_manager=None, task_manager=None):
        """Initialize the CEO with required components."""
        self.name = "Michael"
        self.title = "CEO"
        self.cookbook_manager = cookbook_manager
        self.task_manager = task_manager
        self.ingredients_file = Path("src/office/cookbook/ingredients.yaml")
        self.ingredients = self._load_ingredients()
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.flow_logger = None  # Will be set by front_desk
        logger.info(f"{self.name} ({self.title}) is now online")
    
    def _load_ingredients(self) -> Dict[str, Any]:
        """Load the ingredients file."""
        try:
            if not self.ingredients_file.exists():
                logger.error("Ingredients file not found!")
                return {}
            
            with open(self.ingredients_file, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading ingredients: {str(e)}")
            return {}
    
    async def consider_request(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        request=None
    ) -> Dict[str, Any]:
        """
        Consider a request and determine how to handle it.
        For unknown requests, attempts to create a new recipe.
        """
        try:
            if not message:
                raise ValueError("Empty message received")
            
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "CEO",
                    "Consider Request",
                    {
                        "message": message,
                        "context": context or {}
                    }
                )
            
            # Extract context
            nlp_result = context.get("nlp_result", {}) if context else {}
            intent = nlp_result.get("intent")
            
            # Try to find existing recipe first
            if self.cookbook_manager:
                cookbook_response = self.cookbook_manager.get_recipe(intent)
                if cookbook_response["status"] == "success":
                    if self.flow_logger:
                        await self.flow_logger.log_event(
                            "CEO",
                            "Recipe Found",
                            {
                                "recipe": cookbook_response["recipe"]["name"],
                                "intent": intent
                            }
                        )
                    return {
                        "status": "success",
                        "decision": "I'll handle this with an existing recipe.",
                        "confidence": 0.9,
                        "requires_consultation": False,
                        "recipe": cookbook_response["recipe"],
                        "notes": "Using existing recipe"
                    }
            
            # If no recipe found, try to create one
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "CEO",
                    "Creating New Recipe",
                    {"message": message}
                )
            
            new_recipe = await self._create_recipe(message, nlp_result)
            if not new_recipe:
                if self.flow_logger:
                    await self.flow_logger.log_event(
                        "CEO",
                        "Recipe Creation Failed",
                        {"error": "Could not create recipe"}
                    )
                return {
                    "status": "error",
                    "decision": "I couldn't figure out how to help with this request.",
                    "confidence": 0.0,
                    "requires_consultation": True,
                    "notes": "Failed to create recipe"
                }
            
            # Add new recipe to cookbook
            if self.cookbook_manager:
                added = await self.cookbook_manager.add_recipe(new_recipe)
                if not added:
                    logger.error("Failed to add new recipe to cookbook")
                    if self.flow_logger:
                        await self.flow_logger.log_event(
                            "CEO",
                            "Recipe Storage Failed",
                            {"recipe": new_recipe["name"]}
                        )
                else:
                    if self.flow_logger:
                        await self.flow_logger.log_event(
                            "CEO",
                            "Recipe Added",
                            {
                                "name": new_recipe["name"],
                                "intent": new_recipe["intent"],
                                "steps": [step["action"] for step in new_recipe["steps"]]
                            }
                        )
            
            # Update request if provided
            if request:
                request.recipe = new_recipe
                request.status = "processing"
            
            return {
                "status": "success",
                "decision": "I've created a new way to handle this request.",
                "confidence": 0.8,
                "requires_consultation": False,
                "recipe": new_recipe,
                "notes": "Created new recipe"
            }
            
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            if self.flow_logger:
                await self.flow_logger.log_event(
                    "CEO",
                    "Error",
                    {"error": str(e)}
                )
            return {
                "status": "error",
                "decision": None,
                "confidence": 0.0,
                "requires_consultation": True,
                "notes": str(e)
            }
    
    async def _create_recipe(self, message: str, nlp_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new recipe by analyzing the request and available ingredients."""
        try:
            # Prepare the system prompt with example
            system_prompt = f"""You are {self.name}, the CEO of an AI-powered office.
            Your task is to create a new recipe (workflow) to handle a user request.
            
            Available ingredients (capabilities) are:
            {yaml.dump(self.ingredients, default_flow_style=False)}
            
            Create a recipe that combines these ingredients to handle the request.
            The recipe must follow this exact format:

            name: <clear name>
            description: <clear description>
            intent: <main intent>
            common_triggers:
              - <trigger phrase 1>
              - <trigger phrase 2>
            required_entities:
              - <required entity 1>
              - <required entity 2>
            steps:
              - action: <ingredient action>
                params:
                  param1: value1
              - action: <ingredient action>
                params:
                  param1: value1
            success_criteria:
              - <criterion 1>
              - <criterion 2>

            Rules:
            1. Use ONLY actions that exist in the ingredients list
            2. Each step must have an action and params
            3. All fields are required
            4. No markdown code block markers
            5. Valid YAML format
            6. Intent should be a simple identifier (e.g., create_summary, not "Create Summary")
            7. Common triggers should be actual phrases a user might say
            8. Required entities should be information needed from the user

            Analyze the request and create an appropriate recipe following these rules exactly."""
            
            # Get GPT's recipe creation
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Create a recipe for this request: {message}\n\nRemember to follow the exact format and rules specified."}
                ],
                temperature=0.7
            )
            
            if not response or not response.choices or not response.choices[0].message:
                logger.error("No response received from OpenAI")
                return None
            
            # Get the content and clean it
            recipe_yaml = response.choices[0].message.content
            if not recipe_yaml:
                logger.error("Empty response content from OpenAI")
                return None
            
            # Remove any markdown code block markers and clean whitespace
            recipe_yaml = recipe_yaml.replace("```yaml", "").replace("```", "").strip()
            
            try:
                # Parse the YAML response
                new_recipe = yaml.safe_load(recipe_yaml)
                
                if not isinstance(new_recipe, dict):
                    logger.error("Recipe must be a dictionary")
                    return None
                
                # Validate required fields
                required_fields = {"name", "description", "intent", "steps", "common_triggers", "required_entities", "success_criteria"}
                missing_fields = required_fields - set(new_recipe.keys())
                
                if missing_fields:
                    logger.error(f"Recipe missing required fields: {missing_fields}")
                    return None
                
                # Validate steps
                if not isinstance(new_recipe["steps"], list) or not new_recipe["steps"]:
                    logger.error("Recipe must have at least one step")
                    return None
                
                for step in new_recipe["steps"]:
                    if not isinstance(step, dict) or "action" not in step or "params" not in step:
                        logger.error("Each step must be a dictionary with 'action' and 'params' fields")
                        return None
                    
                    # Validate action exists in ingredients
                    action_found = False
                    for category in self.ingredients.values():
                        for subcategory in category.values():  # Fix: Access values of subcategory dict
                            for ingredient in subcategory:
                                if isinstance(ingredient, dict) and ingredient.get("name") == step["action"]:
                                    action_found = True
                                    break
                            if action_found:
                                break
                        if action_found:
                            break
                    
                    if not action_found:
                        logger.error(f"Invalid action in step: {step['action']}")
                        return None
                
                # Add metadata
                new_recipe["created_at"] = datetime.now().isoformat()
                new_recipe["created_by"] = "ceo"
                new_recipe["version"] = "1.0"
                
                return new_recipe
                
            except yaml.YAMLError as e:
                logger.error(f"Error parsing recipe YAML: {str(e)}")
                return None
            except Exception as e:
                logger.error(f"Error creating recipe: {str(e)}")
                return None
            
        except Exception as e:
            logger.error(f"Error creating recipe: {str(e)}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the CEO."""
        return {
            "name": self.name,
            "title": self.title,
            "status": "online",
            "ready": True,
            "ingredients_loaded": len(self.ingredients) > 0
        } 