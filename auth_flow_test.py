import asyncio
import logging
from src.modules.google_auth import GoogleAuthModule
from typing import Dict, Any
import json
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class FlowTestAgent:
    """Test agent that mirrors the main program's execution flow"""
    
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

    async def _execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Mirror the main program's execute_step method"""
        try:
            logger.info("\n=== Executing Step ===")
            tool_name = 'google_auth'  # Hardcoded for test
            
            # Initialize auth module
            auth_module = GoogleAuthModule()
            
            # Execute authentication
            logger.info("Executing authentication...")
            result = await auth_module.execute({})
            
            logger.debug("\nRaw authentication result:")
            logger.debug(f"Type: {type(result)}")
            for key, value in result.items():
                logger.debug(f"Key: {key}, Type: {type(value)}")
            
            # Mirror the main program's result wrapping
            wrapped_result = {
                'status': 'success' if result.get('success') else 'error',
                'result': result
            }
            
            logger.debug("\nWrapped result structure:")
            safe_wrapped = self._safe_json_serialize(wrapped_result)
            logger.debug(json.dumps(safe_wrapped, indent=2))
            
            return wrapped_result
            
        except Exception as e:
            logger.error(f"Error in execute_step: {str(e)}")
            return {'status': 'error', 'error': str(e)}

    def _evaluate_success_conditions(self, step: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """Mirror the main program's success condition evaluation"""
        try:
            logger.info("\n=== Evaluating Success Conditions ===")
            logger.debug(f"Step: {json.dumps(step, indent=2)}")
            logger.debug("Result structure:")
            logger.debug(json.dumps(self._safe_json_serialize(result), indent=2))
            
            # Test both direct and nested result access
            direct_success = result.get('success')
            nested_success = result.get('result', {}).get('success')
            logger.debug(f"Direct success value: {direct_success}")
            logger.debug(f"Nested success value: {nested_success}")
            
            # Create safe result for evaluation
            safe_result = {}
            if isinstance(result, dict):
                if 'result' in result:
                    # Handle nested result structure
                    inner_result = result['result']
                    safe_result = {
                        'success': bool(inner_result.get('success')),
                        'credentials': bool(inner_result.get('credentials')),
                        'scopes': self._safe_json_serialize(inner_result.get('scopes', []))
                    }
                else:
                    # Handle flat result structure
                    safe_result = {
                        'success': bool(result.get('success')),
                        'credentials': bool(result.get('credentials')),
                        'scopes': self._safe_json_serialize(result.get('scopes', []))
                    }
            
            logger.debug("\nSafe result for evaluation:")
            logger.debug(json.dumps(safe_result, indent=2))
            
            # Test condition evaluation
            condition = "response.get('success')"
            namespace = {'response': safe_result}
            eval_result = eval(condition, {"__builtins__": {}}, namespace)
            logger.debug(f"Condition evaluation result: {eval_result}")
            
            return {
                'complete': eval_result,
                'next_step': 'create_event' if eval_result else None
            }
            
        except Exception as e:
            logger.error(f"Error in condition evaluation: {str(e)}")
            return {'complete': False, 'next_step': None}

async def test_complete_flow():
    """Test the complete authentication and evaluation flow"""
    try:
        logger.info("\n=== Starting Complete Flow Test ===")
        
        test_agent = FlowTestAgent()
        
        # Define test step
        step = {
            'name': 'Authenticate',
            'tool': 'google_auth',
            'action': 'execute',
            'params': {},
            'on_success': [
                {
                    'condition': "response.get('success')",
                    'next_step': 'create_event'
                }
            ]
        }
        
        # Execute step
        result = await test_agent._execute_step(step)
        
        # Evaluate success conditions
        evaluation = test_agent._evaluate_success_conditions(step, result)
        
        logger.info("\n=== Test Results ===")
        logger.info(f"Step execution status: {result.get('status')}")
        logger.info(f"Success evaluation result: {evaluation.get('complete')}")
        logger.info(f"Next step: {evaluation.get('next_step')}")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_complete_flow()) 