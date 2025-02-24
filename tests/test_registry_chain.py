import pytest
import asyncio
import logging
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import yaml
import json

from src.core.registry.service_registry import ServiceRegistry
from src.core.registry.tool_registry import ToolRegistry
from src.core.module_interface import BaseModule, ModuleResponse

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Mark all tests as async
pytestmark = pytest.mark.asyncio

class MockTool(BaseModule):
    """Mock tool for testing"""
    capabilities = ["test_capability"]
    
    async def execute(self, context=None, action=None):
        return {"success": True, "result": "mock_result"}

@pytest.fixture
async def service_registry():
    """Create a service registry with mock services"""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('builtins.open', create=True) as mock_open:
        # Mock service definitions
        mock_services = {
            "test_service": {
                "name": "test_service",
                "steps": [
                    {
                        "name": "test_step",
                        "tool": "mock_tool",
                        "action": "test_action"
                    }
                ]
            },
            "complex_service": {
                "name": "complex_service",
                "steps": [
                    {
                        "name": "auth_step",
                        "tool": "auth_tool",
                        "action": "authenticate",
                        "success_criteria": {
                            "type": "all",
                            "conditions": ["authenticated"]
                        }
                    },
                    {
                        "name": "process_step",
                        "tool": "process_tool",
                        "action": "process",
                        "on_error": {
                            "action": "retry",
                            "max_attempts": 3
                        }
                    }
                ]
            }
        }
        
        mock_open.return_value.__enter__.return_value.read.return_value = \
            yaml.dump(mock_services)
            
        registry = ServiceRegistry()
        await registry.initialize()
        return registry

@pytest.fixture
async def tool_registry():
    """Create a tool registry with mock tools"""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.glob') as mock_glob:
        # Set up mock tool files
        mock_files = [
            Mock(name="mock_tool.py", stem="mock_tool"),
            Mock(name="auth_tool.py", stem="auth_tool"),
            Mock(name="process_tool.py", stem="process_tool")
        ]
        mock_glob.return_value = mock_files
        
        # Create registry
        registry = ToolRegistry()
        await registry.initialize()
        
        # Register mock tools
        await registry.register_item("mock_tool", MockTool)
        await registry.register_item("auth_tool", MockTool)
        await registry.register_item("process_tool", MockTool)
        
        return registry

class TestRegistryChain:
    """Test suite for Service and Tool Registry integration"""
    
    async def test_service_registry_loading(self, service_registry):
        """Test service registry initialization and validation"""
        # Get initialized registry
        registry = await service_registry
        
        # Test service definition loading
        assert registry.initialized
        assert "test_service" in registry.items
        assert "complex_service" in registry.items
        
        # Test service structure validation
        test_service = registry.get_item("test_service")
        assert test_service["name"] == "test_service"
        assert len(test_service["steps"]) == 1
        assert test_service["steps"][0]["tool"] == "mock_tool"
        
        # Test complex service validation
        complex_service = registry.get_item("complex_service")
        assert len(complex_service["steps"]) == 2
        assert "success_criteria" in complex_service["steps"][0]
        assert "on_error" in complex_service["steps"][1]
        
        # Test invalid service registration
        invalid_service = {
            "name": "invalid_service"
            # Missing required 'steps' field
        }
        with pytest.raises(Exception):
            await registry.register_item("invalid_service", invalid_service)
            
    async def test_tool_registry_integration(self, service_registry, tool_registry):
        """Test tool registry with service execution"""
        # Get initialized registries
        service_reg = await service_registry
        tool_reg = await tool_registry
        
        # Test tool availability for services
        test_service = service_reg.get_item("test_service")
        for step in test_service["steps"]:
            tool_name = step["tool"]
            tool = tool_reg.get_item(tool_name)
            assert tool is not None
            assert issubclass(tool, BaseModule)
            assert hasattr(tool, "execute")
            
        # Test tool instantiation and execution
        tool_class = tool_reg.get_item("mock_tool")
        tool_instance = tool_class()
        result = await tool_instance.execute()
        assert result["success"]
        assert result["result"] == "mock_result"
        
        # Test tool validation
        invalid_tool = type("InvalidTool", (), {})
        with pytest.raises(Exception):
            await tool_reg.register_item("invalid_tool", invalid_tool)
            
    async def test_service_tool_dependency_resolution(self, service_registry, tool_registry):
        """Test dependency resolution between services and tools"""
        # Get initialized registries
        service_reg = await service_registry
        tool_reg = await tool_registry
        
        # Test all service steps have corresponding tools
        for service_name, service_def in service_reg.items.items():
            for step in service_def["steps"]:
                tool_name = step["tool"]
                assert tool_reg.get_item(tool_name) is not None
                
        # Test tool capabilities match service requirements
        test_service = service_reg.get_item("test_service")
        for step in test_service["steps"]:
            tool = tool_reg.get_item(step["tool"])
            assert tool.capabilities  # Verify tool has capabilities
            
    async def test_error_handling_integration(self, service_registry, tool_registry):
        """Test error handling between services and tools"""
        # Get initialized registries
        service_reg = await service_registry
        tool_reg = await tool_registry
        
        # Create failing tool
        class FailingTool(BaseModule):
            capabilities = ["test_capability"]
            async def execute(self, context=None, action=None):
                raise Exception("Tool execution failed")
                
        # Register failing tool
        await tool_reg.register_item("failing_tool", FailingTool)
        
        # Test service with failing tool
        service_def = {
            "name": "failing_service",
            "steps": [
                {
                    "name": "failing_step",
                    "tool": "failing_tool",
                    "action": "test_action",
                    "on_error": {
                        "action": "fail"
                    }
                }
            ]
        }
        
        # Verify error handling configuration
        assert await service_reg.validate_item(service_def)
        await service_reg.register_item("failing_service", service_def)
        
        # Test error propagation
        failing_service = service_reg.get_item("failing_service")
        failing_tool = tool_reg.get_item("failing_tool")
        with pytest.raises(Exception) as exc_info:
            tool_instance = failing_tool()
            await tool_instance.execute()
        assert str(exc_info.value) == "Tool execution failed"

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 