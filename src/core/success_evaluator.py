from typing import Dict, Any
from src.core.module_interface import ModuleResponse
from src.utils.logging import get_logger

logger = get_logger(__name__)

class DotDict:
    """Dictionary that supports both dot notation and dictionary access"""
    def __init__(self, dictionary):
        self._dict = dictionary if isinstance(dictionary, dict) else {}

    def __getattr__(self, key):
        try:
            value = self._dict[key]
            return DotDict(value) if isinstance(value, dict) else value
        except (KeyError, TypeError):
            return None

    def get(self, key, default=None):
        try:
            value = self._dict.get(key, default)
            return DotDict(value) if isinstance(value, dict) else value
        except (KeyError, TypeError):
            return default

    def __getitem__(self, key):
        return self.get(key)

    def __str__(self):
        return str(self._dict)

    def __repr__(self):
        return repr(self._dict)

    def __bool__(self):
        return bool(self._dict)

    def __eq__(self, other):
        if isinstance(other, DotDict):
            return self._dict == other._dict
        return self._dict == other

class SuccessEvaluator:
    """Handles success condition evaluation for all modules"""
    
    def evaluate(self, criteria: Dict[str, Any], response: ModuleResponse) -> Dict[str, Any]:
        """
        Evaluate success criteria against a module response
        
        Args:
            criteria: Dictionary containing success criteria definition
            response: ModuleResponse object to evaluate
            
        Returns:
            Dictionary containing evaluation results:
            {
                "success": bool,
                "next_step": Optional[str],
                "action": Optional[str],
                "action_params": Optional[Dict]
            }
        """
        try:
            logger.debug(f"\n=== Evaluating Success Criteria ===")
            logger.debug(f"Criteria: {criteria}")
            logger.debug(f"Response: {response.to_dict() if isinstance(response, ModuleResponse) else response}")
            
            criteria_type = criteria.get("type", "all")
            conditions = criteria.get("conditions", [])
            
            # Evaluate conditions based on type
            if criteria_type == "all":
                success = all(self._evaluate_condition(cond, response) for cond in conditions)
            elif criteria_type == "any":
                success = any(self._evaluate_condition(cond, response) for cond in conditions)
            elif criteria_type == "custom":
                success = self._evaluate_custom_condition(criteria.get("expression"), response)
            else:
                logger.error(f"Unknown criteria type: {criteria_type}")
                success = False
                
            logger.debug(f"Overall success: {success}")
            
            # Determine next action based on success/failure
            if success:
                on_success = criteria.get("on_success", {})
                result = {
                    "success": True,
                    "next_step": on_success.get("next_step"),
                    "action": on_success.get("action"),
                    "action_params": on_success.get("params", {})
                }
                logger.debug(f"Success result: {result}")
                return result
            else:
                on_failure = criteria.get("on_failure", {})
                # Handle conditional failure actions
                if "actions" in on_failure:
                    for action_def in on_failure["actions"]:
                        if self._evaluate_condition(action_def["condition"], response):
                            result = {
                                "success": False,
                                "next_step": action_def.get("target_step"),
                                "action": action_def["action"],
                                "action_params": action_def.get("params", {})
                            }
                            logger.debug(f"Conditional failure result: {result}")
                            return result
                # Default failure action
                result = {
                    "success": False,
                    "next_step": on_failure.get("target_step"),
                    "action": on_failure.get("action", "error"),
                    "action_params": on_failure.get("params", {})
                }
                logger.debug(f"Default failure result: {result}")
                return result
                
        except Exception as e:
            logger.error(f"Error evaluating success criteria: {str(e)}")
            return {
                "success": False,
                "next_step": None,
                "action": "error",
                "action_params": {"error": str(e)}
            }
            
    def _evaluate_condition(self, condition: str, response: ModuleResponse) -> bool:
        """Safely evaluate a single condition against a response"""
        try:
            # Create a safe evaluation environment
            eval_globals = {"__builtins__": {}}
            
            # Convert response to dict and wrap in DotDict for flexible access
            if isinstance(response, ModuleResponse):
                response_dict = DotDict(response.to_dict())
            else:
                response_dict = DotDict(response if isinstance(response, dict) else {})
            
            # Create evaluation locals with response as DotDict
            eval_locals = {
                "response": response_dict,
                "True": True,
                "False": False,
                "None": None
            }
            
            logger.debug(f"\n=== Evaluating Condition ===")
            logger.debug(f"Condition: {condition}")
            logger.debug(f"Response data: {response_dict}")
            
            # Test access patterns for debugging
            logger.debug("\nTesting access patterns:")
            logger.debug(f"Direct success: {response_dict.success}")
            logger.debug(f"Direct credentials: {response_dict.credentials}")
            if response_dict.credentials:
                logger.debug(f"Nested valid: {response_dict.credentials.valid}")
            
            result = eval(condition, eval_globals, eval_locals)
            logger.debug(f"Condition evaluation result: {result}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {str(e)}")
            return False
            
    def _evaluate_custom_condition(self, expression: str, response: ModuleResponse) -> bool:
        """Evaluate a custom condition expression"""
        try:
            # Create a safe evaluation environment with more operators
            eval_globals = {"__builtins__": {}}
            
            # Convert response to DotDict for flexible access
            if isinstance(response, ModuleResponse):
                response_dict = DotDict(response.to_dict())
            else:
                response_dict = DotDict(response if isinstance(response, dict) else {})
            
            eval_locals = {
                "response": response_dict,
                "True": True,
                "False": False,
                "None": None,
                "and": lambda x, y: x and y,
                "or": lambda x, y: x or y,
                "not": lambda x: not x,
                "in": lambda x, y: x in y,
                "len": len
            }
            
            logger.debug(f"\n=== Evaluating Custom Expression ===")
            logger.debug(f"Expression: {expression}")
            logger.debug(f"Response data: {response_dict}")
            
            result = bool(eval(expression, eval_globals, eval_locals))
            logger.debug(f"Custom expression result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating custom expression '{expression}': {str(e)}")
            return False 