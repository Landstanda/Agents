import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import yaml
from pathlib import Path
from src.core.registry.service_registry import ServiceRegistry

@pytest.fixture
def test_services_file(tmp_path):
    """Create a temporary test services file"""
    services = {
        "test_service": {
            "name": "Test Service",
            "description": "A test service",
            "steps": [
                {
                    "name": "test_step",
                    "tool": "test_tool",
                    "action": "execute",
                    "params": {"test_param": "test_value"}
                }
            ]
        },
        "complex_service": {
            "name": "Complex Service",
            "description": "Service with multiple steps and conditions",
            "steps": [
                {
                    "name": "step_one",
                    "tool": "tool_one",
                    "action": "execute",
                    "success_criteria": {
                        "type": "all",
                        "conditions": ["response['status'] == 'success'"]
                    }
                },
                {
                    "name": "step_two",
                    "tool": "tool_two",
                    "action": "process",
                    "on_error": {
                        "action": "retry",
                        "max_attempts": 3
                    }
                }
            ]
        }
    }
    
    services_file = tmp_path / "test_services.yaml"
    with open(services_file, "w") as f:
        yaml.safe_dump(services, f)
    
    return services_file

@pytest.fixture
def service_registry(test_services_file):
    """Create a ServiceRegistry instance with test file"""
    return ServiceRegistry(services_path=str(test_services_file))

@pytest.mark.asyncio
class TestServiceRegistry:
    """Tests for the ServiceRegistry class"""
    
    async def test_initialization(self, service_registry):
        """Test basic registry initialization"""
        assert service_registry.name == "service"
        assert not service_registry.initialized
        assert isinstance(service_registry.items, dict)
        assert len(service_registry.items) == 0
    
    async def test_load_valid_services(self, service_registry):
        """Test loading valid services from YAML"""
        await service_registry.initialize()
        
        assert service_registry.initialized
        assert len(service_registry.items) == 2
        assert "test_service" in service_registry.items
        assert "complex_service" in service_registry.items
        
        # Verify service structure
        test_service = service_registry.get_item("test_service")
        assert test_service["name"] == "Test Service"
        assert len(test_service["steps"]) == 1
        
        complex_service = service_registry.get_item("complex_service")
        assert complex_service["name"] == "Complex Service"
        assert len(complex_service["steps"]) == 2
    
    async def test_validate_valid_service(self, service_registry):
        """Test validation of a valid service definition"""
        valid_service = {
            "name": "Valid Service",
            "steps": [
                {
                    "name": "valid_step",
                    "tool": "test_tool",
                    "action": "execute"
                }
            ]
        }
        
        is_valid = await service_registry.validate_item(valid_service)
        assert is_valid
    
    async def test_validate_missing_required_fields(self, service_registry):
        """Test validation of service missing required fields"""
        invalid_service = {
            "name": "Invalid Service"
            # Missing steps field
        }
        
        is_valid = await service_registry.validate_item(invalid_service)
        assert not is_valid
    
    async def test_validate_empty_steps(self, service_registry):
        """Test validation of service with empty steps"""
        invalid_service = {
            "name": "Invalid Service",
            "steps": []
        }
        
        is_valid = await service_registry.validate_item(invalid_service)
        assert not is_valid
    
    async def test_validate_step_missing_fields(self, service_registry):
        """Test validation of step missing required fields"""
        invalid_service = {
            "name": "Invalid Service",
            "steps": [
                {
                    "name": "invalid_step"
                    # Missing tool and action fields
                }
            ]
        }
        
        is_valid = await service_registry.validate_item(invalid_service)
        assert not is_valid
    
    async def test_validate_success_criteria(self, service_registry):
        """Test validation of success criteria"""
        service_with_criteria = {
            "name": "Test Service",
            "steps": [
                {
                    "name": "test_step",
                    "tool": "test_tool",
                    "action": "execute",
                    "success_criteria": {
                        "type": "all",
                        "conditions": ["response.status == 'success'"]
                    }
                }
            ]
        }
        
        is_valid = await service_registry.validate_item(service_with_criteria)
        assert is_valid
    
    async def test_validate_invalid_success_criteria(self, service_registry):
        """Test validation of invalid success criteria"""
        service_with_invalid_criteria = {
            "name": "Test Service",
            "steps": [
                {
                    "name": "test_step",
                    "tool": "test_tool",
                    "action": "execute",
                    "success_criteria": {
                        "type": "invalid_type",  # Invalid type
                        "conditions": []
                    }
                }
            ]
        }
        
        is_valid = await service_registry.validate_item(service_with_invalid_criteria)
        assert not is_valid
    
    async def test_validate_error_handling(self, service_registry):
        """Test validation of error handling configuration"""
        service_with_error_handling = {
            "name": "Test Service",
            "steps": [
                {
                    "name": "test_step",
                    "tool": "test_tool",
                    "action": "execute",
                    "on_error": {
                        "action": "retry",
                        "max_attempts": 3
                    }
                }
            ]
        }
        
        is_valid = await service_registry.validate_item(service_with_error_handling)
        assert is_valid
    
    async def test_validate_invalid_error_handling(self, service_registry):
        """Test validation of invalid error handling configuration"""
        service_with_invalid_error_handling = {
            "name": "Test Service",
            "steps": [
                {
                    "name": "test_step",
                    "tool": "test_tool",
                    "action": "execute",
                    "on_error": "invalid"  # Should be dict or list
                }
            ]
        }
        
        is_valid = await service_registry.validate_item(service_with_invalid_error_handling)
        assert not is_valid
    
    async def test_load_nonexistent_file(self, tmp_path):
        """Test loading services from non-existent file"""
        nonexistent_file = tmp_path / "nonexistent.yaml"
        registry = ServiceRegistry(services_path=str(nonexistent_file))
        
        await registry.initialize()
        assert registry.initialized
        assert len(registry.items) == 0
    
    async def test_load_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML file"""
        invalid_file = tmp_path / "invalid.yaml"
        with open(invalid_file, "w") as f:
            f.write("invalid: yaml: content")
        
        registry = ServiceRegistry(services_path=str(invalid_file))
        
        with pytest.raises(Exception):
            await registry.initialize()
    
    async def test_register_service(self, service_registry):
        """Test registering a new service"""
        new_service = {
            "name": "New Service",
            "steps": [
                {
                    "name": "new_step",
                    "tool": "test_tool",
                    "action": "execute"
                }
            ]
        }
        
        await service_registry.register_item("new_service", new_service)
        assert "new_service" in service_registry.items
        assert service_registry.get_item("new_service") == new_service
    
    async def test_register_invalid_service(self, service_registry):
        """Test registering an invalid service"""
        invalid_service = {
            "name": "Invalid Service"
            # Missing required fields
        }
        
        with pytest.raises(ValueError):
            await service_registry.register_item("invalid_service", invalid_service)
        assert "invalid_service" not in service_registry.items
    
    async def test_get_registered_service(self, service_registry):
        """Test retrieving a registered service"""
        service = {
            "name": "Test Service",
            "steps": [{"name": "test", "tool": "test_tool", "action": "execute"}]
        }
        
        await service_registry.register_item("test", service)
        retrieved = service_registry.get_item("test")
        assert retrieved == service
    
    async def test_get_nonexistent_service(self, service_registry):
        """Test retrieving a non-existent service"""
        assert service_registry.get_item("nonexistent") is None
    
    async def test_list_services(self, service_registry):
        """Test listing all registered services"""
        await service_registry.initialize()
        services = service_registry.list_items()
        
        assert len(services) == 2
        assert "test_service" in services
        assert "complex_service" in services
        
        # Verify it's a copy
        services["new_service"] = {}
        assert "new_service" not in service_registry.items 