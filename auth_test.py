import asyncio
import logging
from src.modules.google_auth import GoogleAuthModule
from typing import Dict, Any
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestAgent:
    """Simplified agent for testing authentication flow"""
    
    def _safe_json_serialize(self, obj: Any) -> Any:
        """Safely serialize objects to JSON, handling non-serializable types."""
        if isinstance(obj, bool):
            return obj
        elif hasattr(obj, '__dict__'):
            return str(obj)
        elif isinstance(obj, (list, tuple)):
            return [self._safe_json_serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._safe_json_serialize(v) for k, v in obj.items()}
        elif isinstance(obj, (int, float, bool)):
            return obj
        return str(obj)

    def _evaluate_condition(self, condition: str, result: Dict[str, Any]) -> bool:
        """Test condition evaluation logic"""
        try:
            logger.debug(f"\nTesting condition evaluation:")
            logger.debug(f"Condition: {condition}")
            
            # Create a safe copy of the result for evaluation
            safe_result = {}
            if isinstance(result, dict):
                for key, value in result.items():
                    if key == 'success':
                        safe_result[key] = bool(value)
                    elif key == 'credentials':
                        safe_result[key] = bool(value)
                    else:
                        safe_result[key] = self._safe_json_serialize(value)
            
            logger.debug(f"Safe result: {json.dumps(safe_result, indent=2)}")
            
            # Create namespace and evaluate
            namespace = {'response': safe_result}
            logger.debug(f"Evaluation namespace: {json.dumps(namespace, indent=2)}")
            
            eval_result = eval(condition, {"__builtins__": {}}, namespace)
            logger.debug(f"Evaluation result: {eval_result}")
            return bool(eval_result)
            
        except Exception as e:
            logger.error(f"Error in condition evaluation: {str(e)}")
            return False

async def test_auth_flow():
    """Test the authentication flow and condition evaluation"""
    try:
        logger.info("\n=== Starting Authentication Flow Test ===")
        
        # Initialize test agent and auth module
        test_agent = TestAgent()
        auth_module = GoogleAuthModule()
        
        # Execute authentication
        logger.info("\nExecuting authentication...")
        auth_result = await auth_module.execute({})
        logger.info("Authentication completed")
        
        # Log the raw result structure
        logger.debug("\nRaw authentication result structure:")
        for key in auth_result:
            logger.debug(f"Key: {key}, Type: {type(auth_result[key])}")
        
        # Test condition evaluation
        logger.info("\nTesting success condition evaluation...")
        condition = "response.get('success')"
        result = test_agent._evaluate_condition(condition, auth_result)
        
        logger.info(f"\nFinal evaluation result: {result}")
        
        if result:
            logger.info("✓ Success condition evaluated correctly")
        else:
            logger.error("❌ Success condition evaluation failed")
            
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_auth_flow()) 