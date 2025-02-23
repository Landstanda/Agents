from typing import Dict, Any, Optional
import yaml
from pathlib import Path
import logging
from src.utils.logging import get_logger

logger = get_logger(__name__)

class ServiceRegistry:
    """Manages service definitions and their validation"""
    
    def __init__(self, services_path: str = "src/services/service_definitions.yaml"):
        self.services_path = Path(services_path)
        self.services: Dict[str, Any] = {}
        logger.debug(f"ServiceRegistry initialized with path: {services_path}")
        
    async def load_services(self) -> None:
        """Load services from the service definitions file"""
        try:
            logger.debug(f"Loading services from: {self.services_path}")
            
            if not self.services_path.exists():
                raise FileNotFoundError(f"Services file not found: {self.services_path}")
                
            with open(self.services_path, 'r') as f:
                services = yaml.safe_load(f)
                
            if not services:
                raise ValueError("No services found in services file")
                
            # Validate each service
            for service_name, service_def in services.items():
                if self.validate_service(service_def):
                    self.services[service_name] = service_def
                else:
                    logger.warning(f"Skipping invalid service: {service_name}")
                    
            logger.info(f"Loaded {len(self.services)} services successfully")
            
        except Exception as e:
            logger.error(f"Error loading services: {str(e)}")
            raise
            
    def get_service(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a service definition by name"""
        return self.services.get(name)
        
    def validate_service(self, service_def: Dict[str, Any]) -> bool:
        """
        Validate a service definition has all required fields and correct structure
        """
        try:
            # Check required top-level fields
            required_fields = {'name', 'steps'}
            if not all(field in service_def for field in required_fields):
                logger.error(f"Missing required fields: {required_fields - set(service_def.keys())}")
                return False
                
            # Validate steps
            steps = service_def.get('steps', [])
            if not steps:
                logger.error("Service must have at least one step")
                return False
                
            # Validate each step
            for step in steps:
                if not self._validate_step(step):
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error validating service: {str(e)}")
            return False
            
    def _validate_step(self, step: Dict[str, Any]) -> bool:
        """Validate a single step in a service definition"""
        try:
            # Check required step fields
            required_fields = {'name', 'tool', 'action'}
            if not all(field in step for field in required_fields):
                logger.error(f"Step missing required fields: {required_fields - set(step.keys())}")
                return False
                
            # Validate success criteria if present
            if 'success_criteria' in step:
                if not self._validate_success_criteria(step['success_criteria']):
                    return False
                    
            # Validate error handling if present
            if 'on_error' in step:
                if not self._validate_error_handling(step['on_error']):
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error validating step: {str(e)}")
            return False
            
    def _validate_success_criteria(self, criteria: Dict[str, Any]) -> bool:
        """Validate success criteria structure"""
        try:
            if 'type' not in criteria:
                logger.error("Success criteria must have 'type' field")
                return False
                
            if criteria['type'] not in {'all', 'any', 'custom'}:
                logger.error(f"Invalid success criteria type: {criteria['type']}")
                return False
                
            if 'conditions' not in criteria:
                logger.error("Success criteria must have 'conditions' field")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating success criteria: {str(e)}")
            return False
            
    def _validate_error_handling(self, error_handling: Dict[str, Any]) -> bool:
        """Validate error handling configuration"""
        try:
            if isinstance(error_handling, list):
                for handler in error_handling:
                    if 'action' not in handler:
                        logger.error("Error handler must have 'action' field")
                        return False
            elif isinstance(error_handling, dict):
                if 'action' not in error_handling:
                    logger.error("Error handler must have 'action' field")
                    return False
            else:
                logger.error("Invalid error handling structure")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating error handling: {str(e)}")
            return False 