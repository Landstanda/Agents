import asyncio
import logging
from typing import Dict, Any
import json
from pathlib import Path
import yaml
from src.modules.google_auth import GoogleAuthModule
from src.core.module_interface import ModuleResponse
from src.core.success_evaluator import SuccessEvaluator
from src.utils.flow_logger import FlowLogger
from src.models import Ticket

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataFlowTracer:
    """Traces and validates data flow between components"""
    
    def __init__(self):
        self.success_evaluator = SuccessEvaluator()
        self.flow_logger = FlowLogger()
    
    def trace_data_transformation(self, stage: str, data: Any):
        """Log detailed information about data at each stage"""
        logger.info(f"\n=== Data at {stage} ===")
        if isinstance(data, ModuleResponse):
            logger.info("Type: ModuleResponse")
            logger.info(f"Content: {json.dumps(data.to_dict(), indent=2)}")
        elif isinstance(data, dict):
            logger.info("Type: Dictionary")
            logger.info(f"Content: {json.dumps(data, indent=2)}")
        else:
            logger.info(f"Type: {type(data)}")
            logger.info(f"Content: {str(data)}")

    def trace_condition_evaluation(self, condition: str, response: Any):
        """Trace the evaluation of a single condition"""
        logger.info(f"\n=== Evaluating Condition: {condition} ===")
        
        # Convert response to appropriate format
        if isinstance(response, dict):
            response_dict = response
        elif isinstance(response, ModuleResponse):
            response_dict = response.to_dict()
        else:
            response_dict = {"success": False, "error": "Invalid response type"}
            
        logger.info("Response structure:")
        logger.info(json.dumps(response_dict, indent=2))
        
        # Test different access patterns
        logger.info("\nTesting access patterns:")
        logger.info(f"Direct success: {response_dict.get('success')}")
        logger.info(f"Direct credentials: {response_dict.get('credentials')}")
        if isinstance(response_dict.get('credentials'), dict):
            logger.info(f"Nested valid: {response_dict['credentials'].get('valid')}")
        
        # Evaluate condition
        try:
            namespace = {'response': response_dict}
            result = eval(condition, {"__builtins__": {}}, namespace)
            logger.info(f"Condition evaluation result: {result}")
            return result
        except Exception as e:
            logger.error(f"Condition evaluation failed: {str(e)}")
            return False
    
    def validate_module_response(self, response: Any) -> bool:
        """Validate that a response matches the expected response format"""
        if isinstance(response, ModuleResponse):
            return True
        
        if isinstance(response, dict):
            # Check for success field
            if 'success' not in response:
                logger.error("Missing 'success' field in response")
                return False
                
            # For successful responses, check for required data
            if response['success']:
                if 'credentials' not in response:
                    logger.error("Missing 'credentials' field in successful response")
                    return False
                    
                creds = response['credentials']
                required_cred_fields = {'valid', 'has_refresh_token', 'scopes'}
                if not all(field in creds for field in required_cred_fields):
                    logger.error(f"Missing required credential fields. Found: {list(creds.keys())}")
                    return False
            else:
                # For error responses, check for error field
                if 'error' not in response:
                    logger.error("Missing 'error' field in failed response")
                    return False
            
            return True
            
        logger.error(f"Invalid response type: {type(response)}")
        return False

    def validate_success_criteria(self, criteria: Dict[str, Any]) -> bool:
        """Validate success criteria format"""
        required_fields = {'type', 'conditions'}
        if not all(field in criteria for field in required_fields):
            logger.error(f"Missing required fields in success criteria. Found: {list(criteria.keys())}")
            return False
            
        # Log each condition for analysis
        logger.info("\nAnalyzing success conditions:")
        for condition in criteria['conditions']:
            logger.info(f"Condition: {condition}")
            
        return True

async def test_auth_flow_integration():
    """Test the complete authentication flow with data tracing"""
    try:
        logger.info("\n=== Starting Authentication Flow Integration Test ===")
        tracer = DataFlowTracer()
        
        # Create test ticket
        ticket = Ticket(
            user_info={"user_id": "test_user", "channel_id": "test_channel"},
            original_message="Schedule a meeting",
            service="schedule_meeting"
        )
        ticket.current_step = "Authenticate"
        
        # Load service definitions
        workspace_root = Path("/home/jeff/Agents")
        services_path = workspace_root / "src/services/service_definitions.yaml"
        
        with open(services_path, 'r') as f:
            services = yaml.safe_load(f)
        
        # Get authentication step definition
        auth_step = services['schedule_meeting']['steps'][0]
        tracer.trace_data_transformation("Service Definition - Auth Step", auth_step)
        
        # Initialize and execute auth module
        auth_module = GoogleAuthModule()
        auth_result = await auth_module.execute(ticket, auth_step.get('params', {}))
        tracer.trace_data_transformation("Auth Module Output", auth_result)
        
        # Validate module response format
        if not tracer.validate_module_response(auth_result):
            logger.error("❌ Auth module response format is invalid")
            return
        
        # Get success criteria from service definition
        success_criteria = auth_step['success_criteria']
        tracer.trace_data_transformation("Success Criteria", success_criteria)
        
        # Validate success criteria format
        if not tracer.validate_success_criteria(success_criteria):
            logger.error("❌ Success criteria format is invalid")
            return
        
        # Test each condition individually
        logger.info("\n=== Testing Individual Conditions ===")
        for condition in success_criteria['conditions']:
            result = tracer.trace_condition_evaluation(condition, auth_result)
            logger.info(f"Condition '{condition}' result: {result}")
        
        # Convert dict response to ModuleResponse if needed
        if isinstance(auth_result, dict):
            module_response = ModuleResponse(
                success=auth_result['success'],
                data=auth_result
            )
            auth_result = module_response
        
        # Evaluate success conditions
        evaluation_result = tracer.success_evaluator.evaluate(success_criteria, auth_result)
        tracer.trace_data_transformation("Success Evaluation Result", evaluation_result)
        
        # Analyze results
        logger.info("\n=== Analysis Results ===")
        logger.info(f"Auth Module Response Valid: {tracer.validate_module_response(auth_result)}")
        logger.info(f"Success Criteria Valid: {tracer.validate_success_criteria(success_criteria)}")
        logger.info(f"Evaluation Success: {evaluation_result.get('success', False)}")
        logger.info(f"Next Step: {evaluation_result.get('next_step')}")
        
        # Check response structure details
        logger.info("\n=== Response Structure Analysis ===")
        if isinstance(auth_result, dict):
            logger.info("Dictionary Response Structure:")
            logger.info(f"Top-level keys: {list(auth_result.keys())}")
            if 'credentials' in auth_result:
                logger.info(f"Credentials keys: {list(auth_result['credentials'].keys())}")
        elif isinstance(auth_result, ModuleResponse):
            logger.info("ModuleResponse Structure:")
            dict_form = auth_result.to_dict()
            logger.info(f"Top-level keys: {list(dict_form.keys())}")
            if 'credentials' in dict_form:
                logger.info(f"Credentials keys: {list(dict_form['credentials'].keys())}")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_auth_flow_integration()) 