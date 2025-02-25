import pytest
from typing import Dict, Any, List
import asyncio
from src.core.module_interface import ModuleResponse, BaseModule
from src.execution.context import ExecutionContext
from src.models import Ticket
from unittest.mock import MagicMock

class TestModuleResponse:
    def test_initialization(self):
        """Test basic initialization of ModuleResponse"""
        # Test successful response
        response = ModuleResponse(
            success=True,
            data={"key": "value"},
            error=None,
            error_type=None
        )
        assert response.success is True
        assert response.data == {"key": "value"}
        assert response.error is None
        assert response.error_type is None
        assert response.key == "value"  # Test direct attribute access
        
        # Test error response
        error_response = ModuleResponse(
            success=False,
            data=None,
            error="Something went wrong",
            error_type="validation_error"
        )
        assert error_response.success is False
        assert error_response.data == {}
        assert error_response.error == "Something went wrong"
        assert error_response.error_type == "validation_error"
        
    def test_nested_data_access(self):
        """Test handling of nested data structures"""
        nested_data = {
            "user": {
                "name": "John",
                "settings": {
                    "theme": "dark",
                    "notifications": True
                }
            },
            "metadata": {
                "version": "1.0"
            }
        }
        
        response = ModuleResponse(success=True, data=nested_data)
        assert response.user["name"] == "John"
        assert response.user["settings"]["theme"] == "dark"
        assert response.metadata["version"] == "1.0"
        
    def test_to_dict_conversion(self):
        """Test conversion of ModuleResponse to dictionary"""
        data = {
            "result": "success",
            "count": 42,
            "items": ["a", "b", "c"]
        }
        response = ModuleResponse(
            success=True,
            data=data,
            error=None,
            error_type=None
        )
        
        dict_response = response.to_dict()
        assert dict_response["success"] is True
        assert dict_response["data"] == data
        assert "error" not in dict_response
        assert "error_type" not in dict_response
        assert dict_response["result"] == "success"
        assert dict_response["count"] == 42
        assert dict_response["items"] == ["a", "b", "c"]
        
    def test_from_dict_conversion(self):
        """Test creation of ModuleResponse from dictionary"""
        input_dict = {
            "success": True,
            "error": None,
            "error_type": None,
            "custom_field": "value",
            "nested": {"key": "value"}
        }
        
        response = ModuleResponse.from_dict(input_dict)
        assert response.success is True
        assert response.error is None
        assert response.error_type is None
        assert response.custom_field == "value"
        assert response.nested["key"] == "value"
        
    def test_error_handling(self):
        """Test error handling in ModuleResponse"""
        # Test with error information
        response = ModuleResponse(
            success=False,
            error="Invalid input",
            error_type="validation_error",
            data={"field": "username"}
        )
        
        dict_response = response.to_dict()
        assert dict_response["success"] is False
        assert dict_response["error"] == "Invalid input"
        assert dict_response["error_type"] == "validation_error"
        assert dict_response["field"] == "username"
        
        # Test error response reconstruction
        reconstructed = ModuleResponse.from_dict(dict_response)
        assert reconstructed.success is False
        assert reconstructed.error == "Invalid input"
        assert reconstructed.error_type == "validation_error"
        
    def test_data_attribute_conflicts(self):
        """Test handling of data attributes that might conflict with base attributes"""
        # Create response with conflicting data attributes
        response = ModuleResponse(
            success=True,
            data={
                "success": "custom_value",
                "error": "custom_error",
                "to_dict": "custom_method"
            }
        )
        
        # Base attributes should be preserved
        assert response.success is True  # Base attribute
        assert callable(response.to_dict)  # Method should still be callable
        
        # Data should be accessible through data dict
        assert response.data["success"] == "custom_value"
        assert response.data["error"] == "custom_error"
        assert response.data["to_dict"] == "custom_method"

class MockModule(BaseModule):
    """Mock implementation of BaseModule for testing"""
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.execute_called = False
        
    async def execute(self, context: ExecutionContext, **params) -> Dict[str, Any]:
        self.execute_called = True
        if self.should_succeed:
            return {"success": True, "data": params}
        else:
            return {"success": False, "error": "Mock error"}
            
    @property
    def capabilities(self) -> List[str]:
        return ["mock_capability_1", "mock_capability_2"]

class TestBaseModule:
    @pytest.fixture
    def mock_context(self, mocker):
        """Create a mock execution context"""
        mock_ticket = MagicMock(spec=Ticket)
        mock_ticket.entities = {}  # Add required attribute
        mock_service = {"name": "test_service"}
        return ExecutionContext(mock_ticket, mock_service)
        
    @pytest.mark.asyncio
    async def test_module_execution(self, mock_context):
        """Test basic module execution"""
        # Test successful execution
        success_module = MockModule(should_succeed=True)
        result = await success_module.execute(mock_context, param1="value1")
        assert result["success"] is True
        assert result["data"]["param1"] == "value1"
        assert success_module.execute_called is True
        
        # Test failed execution
        fail_module = MockModule(should_succeed=False)
        result = await fail_module.execute(mock_context)
        assert result["success"] is False
        assert result["error"] == "Mock error"
        assert fail_module.execute_called is True
        
    def test_capabilities(self):
        """Test module capabilities property"""
        module = MockModule()
        capabilities = module.capabilities
        assert isinstance(capabilities, list)
        assert "mock_capability_1" in capabilities
        assert "mock_capability_2" in capabilities
        assert len(capabilities) == 2
        
    def test_abstract_methods(self):
        """Test that abstract methods are enforced"""
        # Attempt to instantiate BaseModule directly
        with pytest.raises(TypeError):
            BaseModule()
            
        # Create incomplete module class and attempt to instantiate it
        class IncompleteModule(BaseModule):
            pass
            
        with pytest.raises(TypeError):
            IncompleteModule()
            
        # Create module missing capabilities
        class NoCapabilitiesModule(BaseModule):
            async def execute(self, context: ExecutionContext, **params):
                pass
                
        with pytest.raises(TypeError):
            NoCapabilitiesModule()
                    
    @pytest.mark.asyncio
    async def test_execution_with_context(self, mock_context):
        """Test module execution with context interaction"""
        class ContextAwareModule(MockModule):
            async def execute(self, context: ExecutionContext, **params):
                # Store something in context
                context.set_variable("test_key", "test_value")
                return {"success": True, "data": {"context_test": "passed"}}
                
        module = ContextAwareModule()
        result = await module.execute(mock_context)
        
        assert result["success"] is True
        assert mock_context.get_variable("test_key") == "test_value"
        assert result["data"]["context_test"] == "passed"

if __name__ == "__main__":
    pytest.main(["-v", "test_module_interface.py"]) 