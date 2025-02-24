import pytest
from datetime import datetime
from src.core.module_interface import BaseModule, ModuleResponse
from src.models import Ticket
from src.execution.context import ExecutionContext

class SimpleMockTool(BaseModule):
    """Minimal mock tool for testing"""
    capabilities = ["test"]
    
    async def execute(self, context: ExecutionContext, **params) -> dict:
        return ModuleResponse(success=True, data={"test": "success"}).to_dict()

@pytest.fixture
def simple_service():
    """Create a minimal service definition"""
    return {
        "name": "simple_service",
        "steps": [
            {
                "name": "test_step",
                "tool": "simple_tool",
                "action": "test",
                "params": {}
            }
        ]
    }

@pytest.fixture
def simple_ticket():
    """Create a minimal ticket"""
    return Ticket(
        user_info={"user_id": "test"},
        original_message="test"
    )

@pytest.fixture
def execution_context(simple_ticket, simple_service):
    """Create an execution context"""
    return ExecutionContext(simple_ticket, simple_service)

class TestBasicExecution:
    @pytest.mark.asyncio
    async def test_time_tracking(self, execution_context):
        """Test basic time tracking in execution context"""
        # Set current step
        execution_context.set_current_step({"name": "test_step"}, 1)
        
        # Get current time
        start_time = execution_context.get_current_time()
        
        # Verify time is a datetime object
        assert isinstance(start_time, datetime)
        
        # Store a result
        execution_context.store_result(1, {"test": "success"})
        
        # Get stored result
        result = execution_context.get_result(1)
        
        # Verify result was stored
        assert result == {"test": "success"} 