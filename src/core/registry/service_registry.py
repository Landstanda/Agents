from typing import Dict, Any, Optional
import yaml
from pathlib import Path
from src.utils.logging import get_logger
from src.core.registry.base_registry import BaseRegistry

class ServiceRegistry(BaseRegistry):
    """Manages service definitions and their validation"""
    
    def __init__(self, services_path: str = "src/services/service_definitions.yaml"):
        super().__init__(name="service", base_path=services_path)
        
    async def load_items(self) -> None:
        """Load service definitions from YAML file"""
        try:
            if not self.base_path.exists():
                self.logger.warning(f"Services file not found: {self.base_path}")
                return
                
            with open(self.base_path, 'r') as f:
                services_data = yaml.safe_load(f)
                
            if not services_data:
                self.logger.warning("No services found in services file")
                return
                
            # Register each service
            for service_name, service_def in services_data.items():
                await self.register_item(service_name, service_def)
                    
            self._log_registration_summary()
            
        except Exception as e:
            self.logger.error(f"Error loading services: {str(e)}")
            raise
            
    async def validate_item(self, service_def: Dict[str, Any]) -> bool:
        """Validate service definition"""
        try:
            # Check required top-level fields
            required_fields = {'name', 'steps'}
            if not all(field in service_def for field in required_fields):
                self.logger.error(f"Missing required fields: {required_fields - set(service_def.keys())}")
                return False
                
            # Validate steps
            steps = service_def.get('steps', [])
            if not steps:
                self.logger.error("Service must have at least one step")
                return False
                
            # Validate each step
            for step in steps:
                if not await self._validate_step(step):
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating service: {str(e)}")
            return False
            
    async def _validate_step(self, step: Dict[str, Any]) -> bool:
        """Validate a single step in a service definition"""
        try:
            # Check required step fields
            required_fields = {'name', 'tool', 'action'}
            if not all(field in step for field in required_fields):
                self.logger.error(f"Step missing required fields: {required_fields - set(step.keys())}")
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
            self.logger.error(f"Error validating step: {str(e)}")
            return False
            
    def _validate_success_criteria(self, criteria: Dict[str, Any]) -> bool:
        """Validate success criteria structure"""
        try:
            if 'type' not in criteria:
                self.logger.error("Success criteria must have 'type' field")
                return False
                
            if criteria['type'] not in {'all', 'any', 'custom'}:
                self.logger.error(f"Invalid success criteria type: {criteria['type']}")
                return False
                
            if 'conditions' not in criteria:
                self.logger.error("Success criteria must have 'conditions' field")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating success criteria: {str(e)}")
            return False
            
    def _validate_error_handling(self, error_handling: Dict[str, Any]) -> bool:
        """Validate error handling configuration"""
        try:
            if isinstance(error_handling, list):
                for handler in error_handling:
                    if 'action' not in handler:
                        self.logger.error("Error handler must have 'action' field")
                        return False
            elif isinstance(error_handling, dict):
                if 'action' not in error_handling:
                    self.logger.error("Error handler must have 'action' field")
                    return False
            else:
                self.logger.error("Invalid error handling structure")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating error handling: {str(e)}")
            return False 