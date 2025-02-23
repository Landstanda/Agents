import yaml
import logging
from typing import Dict, Any
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def validate_next_step_structure(step_data: Dict[str, Any], path: str = "") -> bool:
    """Validate the structure of next_step definitions"""
    if isinstance(step_data, str):
        return True
    elif isinstance(step_data, dict):
        required_keys = {"condition", "then", "else"}
        if not all(key in step_data for key in required_keys):
            logger.error(f"Missing required keys in next_step at {path}. Found keys: {list(step_data.keys())}")
            return False
        return True
    else:
        logger.error(f"Invalid next_step type at {path}: {type(step_data)}")
        return False

def validate_success_criteria(criteria: Dict[str, Any], path: str = "") -> bool:
    """Validate success criteria structure"""
    required_keys = {"type", "conditions"}
    if not all(key in criteria for key in required_keys):
        logger.error(f"Missing required keys in success_criteria at {path}")
        return False
    
    if "on_success" in criteria:
        if not validate_next_step_structure(criteria["on_success"].get("next_step", ""), f"{path}.on_success.next_step"):
            return False
            
    return True

def validate_service_step(step: Dict[str, Any], path: str) -> bool:
    """Validate a single service step"""
    required_keys = {"name", "tool", "action", "params"}
    if not all(key in step for key in required_keys):
        logger.error(f"Missing required keys in step at {path}")
        return False
        
    if "success_criteria" in step:
        if not validate_success_criteria(step["success_criteria"], f"{path}.success_criteria"):
            return False
            
    return True

def validate_service(service: Dict[str, Any], name: str) -> bool:
    """Validate a single service definition"""
    required_keys = {"name", "required_entities", "steps"}
    if not all(key in service for key in required_keys):
        logger.error(f"Missing required keys in service {name}")
        return False
        
    # Validate each step
    for i, step in enumerate(service["steps"]):
        if not validate_service_step(step, f"{name}.steps[{i}]"):
            return False
            
    return True

def test_load_services():
    """Test loading and validating service definitions"""
    try:
        logger.info("\n=== Testing Service Definitions Loading ===")
        
        # Use the same path construction as the Agent
        workspace_root = Path("/home/jeff/Agents")
        services_path = workspace_root / "src/services/service_definitions.yaml"
        logger.info(f"Loading services from: {services_path}")
        
        if not services_path.exists():
            logger.error(f"Services file not found at {services_path}")
            return False
        
        # Load the YAML file
        with open(services_path, "r") as f:
            try:
                # Print the raw content for debugging
                content = f.read()
                logger.debug(f"Raw file content:\n{content[:500]}...")  # First 500 chars
                
                # Reset file pointer and parse YAML
                f.seek(0)
                services = yaml.safe_load(f)
                if services is None:
                    logger.error("YAML file loaded as None")
                    return False
                logger.info("✓ YAML file loaded successfully")
                logger.debug(f"Loaded {len(services)} services")
                
            except yaml.YAMLError as e:
                logger.error(f"YAML parsing error: {str(e)}")
                if hasattr(e, 'problem_mark'):
                    mark = e.problem_mark
                    logger.error(f"Error position: line {mark.line + 1}, column {mark.column + 1}")
                    # Print the problematic lines
                    lines = content.split('\n')
                    start = max(0, mark.line - 2)
                    end = min(len(lines), mark.line + 3)
                    logger.error("Context:")
                    for i in range(start, end):
                        prefix = ">>>" if i == mark.line else "   "
                        logger.error(f"{prefix} {i+1}: {lines[i]}")
                return False
        
        # Validate overall structure
        if not isinstance(services, dict):
            logger.error("Root element is not a dictionary")
            return False
            
        # Validate each service
        for service_name, service_def in services.items():
            logger.info(f"\nValidating service: {service_name}")
            if not validate_service(service_def, service_name):
                return False
            logger.info(f"✓ Service {service_name} validated successfully")
            
        logger.info("\n✓ All services validated successfully")
        return True
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_load_services()
    if success:
        logger.info("\n=== All Tests Passed ===")
    else:
        logger.error("\n=== Test Failed ===") 