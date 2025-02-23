from typing import Dict, Any, Optional, List, Tuple
from packaging import version
import yaml
from pathlib import Path
import logging
from datetime import datetime
from src.utils.logging import get_logger

logger = get_logger(__name__)

def parse_version(version_str: str) -> version.Version:
    """Parse version string into a Version object for comparison"""
    return version.parse(version_str)

class ServiceRegistry:
    """Manages service definitions and their validation"""
    
    def __init__(self, services_file: str = 'src/services/service_definitions.yaml'):
        self.services_file = services_file
        self.services: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"ServiceRegistry initialized with path: {services_file}")
        
    async def load_services(self) -> None:
        """Load service definitions from YAML file"""
        try:
            with open(self.services_file, 'r') as f:
                services_data = yaml.safe_load(f)
                if not services_data:
                    self.logger.warning("No services found in services file")
                    return
                
                for service_name, service_def in services_data.items():
                    if isinstance(service_def, dict):
                        await self.add_service_version(service_name, service_def)
                    
        except FileNotFoundError:
            self.logger.warning(f"Services file not found: {self.services_file}")
        except Exception as e:
            self.logger.error(f"Error loading services: {str(e)}")
            
    async def add_service_version(self, service_name: str, service_def: Dict[str, Any]) -> None:
        """Add a new version of a service"""
        try:
            # Validate service definition
            if not await self.validate_service(service_def):
                self.logger.error(f"Invalid service definition for {service_name}")
                return
                
            # Set default version if not provided
            version = service_def.get('version', '1.0.0')
                
            # Initialize service versions if needed
            if service_name not in self.services:
                self.services[service_name] = {}
                
            # Add new version
            self.services[service_name][version] = service_def
            self.logger.debug(f"Added version {version} for service {service_name}")
            
        except Exception as e:
            self.logger.error(f"Error adding service version: {str(e)}")
            raise
        
    def get_service(self, service_name: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get service definition by name and optionally version"""
        try:
            if service_name not in self.services:
                self.logger.warning(f"Service '{service_name}' not found")
                return None
            
            service_versions = self.services[service_name]
            if not service_versions:
                self.logger.warning(f"No versions found for service '{service_name}'")
                return None
            
            if version:
                if version not in service_versions:
                    self.logger.warning(f"Version {version} not found for service '{service_name}'")
                    return None
                return service_versions[version]
            
            # Return latest version if no specific version requested
            versions = sorted(service_versions.keys(), key=parse_version)
            if not versions:
                self.logger.warning(f"No versions available for service '{service_name}'")
                return None
            
            latest_version = versions[-1]
            return service_versions[latest_version]
            
        except Exception as e:
            self.logger.error(f"Error getting service: {str(e)}")
            return None
        
    async def validate_service(self, service_def: Dict[str, Any]) -> bool:
        """Validate service definition"""
        try:
            # Check required top-level fields
            required_fields = {'name', 'steps'}
            missing_fields = required_fields - set(service_def.keys())
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
                
            # Validate steps
            if not isinstance(service_def['steps'], list):
                raise ValueError("Steps must be a list")
                
            if not service_def['steps']:
                raise ValueError("Service must have at least one step")
                
            # Validate each step
            for step in service_def['steps']:
                await self._validate_step(step)
                    
            return True
            
        except ValueError as e:
            self.logger.error(str(e))
            raise
        except Exception as e:
            self.logger.error(f"Error validating service: {str(e)}")
            raise ValueError(f"Service validation failed: {str(e)}")
            
    async def _validate_step(self, step: Dict[str, Any]) -> None:
        """Validate a single step in a service definition"""
        try:
            # Check required step fields
            required_fields = {'name', 'tool'}
            missing_fields = required_fields - set(step.keys())
            if missing_fields:
                raise ValueError(f"Step missing required fields: {missing_fields}")
                
            # Validate success criteria if present
            if 'success_criteria' in step:
                if not isinstance(step['success_criteria'], (list, dict)):
                    raise ValueError("Success criteria must be a list or dictionary")
                    
            # Validate error handling if present
            if 'error_handling' in step:
                if not isinstance(step['error_handling'], dict):
                    raise ValueError("Error handling must be a dictionary")
                    
        except Exception as e:
            self.logger.error(f"Error validating step: {str(e)}")
            raise
            
    def get_service_versions(self, name: str) -> List[str]:
        """Get all available versions for a service"""
        return sorted(self.services.get(name, {}).keys())
        
    def set_active_version(self, name: str, version: str) -> bool:
        """Set the active version for a service"""
        try:
            if name in self.services and version in self.services[name]:
                self.services[name] = {version: self.services[name][version]}
                self.logger.debug(f"Set active version {version} for service {name}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error setting active version: {str(e)}")
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