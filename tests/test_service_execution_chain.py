import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any, Callable
from datetime import datetime
from src.core.registry import ServiceRegistry, ToolRegistry
from src.core.agent.executor import ServiceExecutor
from src.core.module_interface import BaseModule, ModuleResponse
from src.models import Ticket, TicketStatus
from src.execution.context import ExecutionContext

class MockTool(BaseModule):
    """Mock tool for testing"""
    __name__ = "MockTool"
    capabilities = ["test_action"]  # List of supported actions
    
    _execution_count = 0  # Class-level counter
    
    def __init__(self, should_succeed=True):
        self.should_succeed = should_succeed

    async def execute(self, context: ExecutionContext, **params) -> Dict[str, Any]:
        """Execute the mock tool"""
        MockTool._execution_count += 1
        if not self.should_succeed:
            return ModuleResponse(success=False, error="Mock tool execution failed").to_dict()
        return ModuleResponse(success=True, data={"execution_count": MockTool._execution_count, **params}).to_dict()

    @classmethod
    def create(cls, **kwargs):
        """Factory method for creating instances"""
        return cls(**kwargs)

class FailingMockTool(MockTool):
    """Mock tool that always fails"""
    __name__ = "FailingMockTool"
    capabilities = ["test_action"]
    
    def __init__(self):
        super().__init__(should_succeed=False)

class MockServiceRegistry(ServiceRegistry):
    """Mock service registry that doesn't load from files"""
    async def load_items(self) -> None:
        """Don't load items from files"""
        pass

class MockToolRegistry(ToolRegistry):
    """Mock tool registry that doesn't load from files"""
    async def load_items(self) -> None:
        """Don't load items from files"""
        pass

@pytest.fixture
def mock_service_def():
    """Create a mock service definition"""
    return {
        "name": "test_service",
        "description": "Test service for execution chain",
        "steps": [
            {
                "name": "step1",
                "tool": "mock_tool",
                "action": "test_action",
                "params": {"param1": "value1"}
            }
        ]
    }

@pytest.fixture
def mock_ticket():
    """Create a mock ticket"""
    return Ticket(
        user_info={"user_id": "test_user"},
        original_message="Test request"
    )

@pytest.fixture
async def service_executor(mock_service_def):
    """Create a service executor instance with mock registries"""
    # Create registries
    service_registry = MockServiceRegistry()
    tool_registry = MockToolRegistry()
    
    # Initialize registries
    await service_registry.initialize()
    await tool_registry.initialize()
    
    # Register mock service
    await service_registry.register_item("test_service", mock_service_def)
    
    # Register MockTool class
    await tool_registry.register_item("mock_tool", MockTool)
    
    # Create and initialize executor
    executor = ServiceExecutor(service_registry, tool_registry)
    await executor.initialize()
    
    return executor

class TestServiceExecutionChain:
    """Test cases for service execution chain"""
    
    @pytest.fixture(autouse=True)
    def reset_execution_count(self):
        """Reset the execution count before each test"""
        MockTool._execution_count = 0
        yield
    
    @pytest.mark.asyncio
    async def test_single_step_execution(self, service_executor, mock_service_def, mock_ticket):
        """Test execution of a single step with time tracking"""
        executor = await service_executor
        
        result = await executor.execute_service(mock_service_def, mock_ticket)
        
        assert result["status"] == "completed"
        assert len(result["results"]) == 1
        
        step_result = result["results"][0]
        assert step_result["success"] is True
        assert "start_time" in step_result
        assert "end_time" in step_result
        assert "duration" in step_result
        assert isinstance(datetime.fromisoformat(step_result["start_time"]), datetime)
        assert isinstance(datetime.fromisoformat(step_result["end_time"]), datetime)
        assert isinstance(step_result["duration"], float)
        assert step_result["duration"] >= 0

    @pytest.mark.asyncio
    async def test_successful_execution_chain(self, service_executor, mock_service_def, mock_ticket):
        """Test successful execution of a service through the entire chain"""
        # Get initialized executor
        executor = await service_executor
        
        # Execute service
        result = await executor.execute_service(mock_service_def, mock_ticket)
        
        # Verify successful execution
        assert result["status"] == "completed"
        assert len(result.get("results", [])) == 2
        assert all(r.get("success", False) for r in result.get("results", []))

    @pytest.mark.asyncio
    async def test_failed_step_execution(self, service_executor, mock_service_def, mock_ticket):
        """Test handling of failed step execution"""
        # Get initialized executor
        executor = await service_executor
        
        # Register failing tool
        await executor.tool_registry.register_item("failing_tool", FailingMockTool)
        
        # Modify first step to use failing tool
        service_def = dict(mock_service_def)  # Make a copy
        service_def["steps"] = list(service_def["steps"])  # Copy steps list
        service_def["steps"][0] = dict(service_def["steps"][0])  # Copy first step
        service_def["steps"][0]["tool"] = "failing_tool"
        
        # Execute service
        result = await executor.execute_service(service_def, mock_ticket)
        
        # Verify failure handling
        assert result["status"] == "error"
        assert result.get("error") is not None
        assert mock_ticket.status == TicketStatus.ERROR

    @pytest.mark.asyncio
    async def test_context_preservation(self, service_executor, mock_service_def, mock_ticket):
        """Test preservation of context data between steps"""
        # Get initialized executor
        executor = await service_executor
        
        # Execute service
        result = await executor.execute_service(mock_service_def, mock_ticket)
        
        # Verify context preservation
        assert result["status"] == "completed"
        assert len(result.get("results", [])) == 2
        
        # Check that step2 has access to step1's results
        step2_result = result["results"][1]
        assert step2_result.get("execution_count") == 2  # Second execution
        assert step2_result.get("param2") == "value2"  # Original param preserved

    @pytest.mark.asyncio
    async def test_service_not_found(self, service_executor, mock_ticket):
        """Test handling of non-existent service"""
        # Get initialized executor
        executor = await service_executor
        
        invalid_service = {
            "name": "nonexistent_service",
            "steps": []
        }
        
        # Execute invalid service
        result = await executor.execute_service(invalid_service, mock_ticket)
        
        # Verify error handling
        assert result["status"] == "error"
        assert result.get("error") is not None
        assert mock_ticket.status == TicketStatus.ERROR

    @pytest.mark.asyncio
    async def test_tool_not_found(self, service_executor, mock_service_def, mock_ticket):
        """Test handling of non-existent tool"""
        # Get initialized executor
        executor = await service_executor
        
        # Modify service to use non-existent tool
        service_def = dict(mock_service_def)
        service_def["steps"] = list(service_def["steps"])
        service_def["steps"][0] = dict(service_def["steps"][0])
        service_def["steps"][0]["tool"] = "nonexistent_tool"
        
        # Execute service
        result = await executor.execute_service(service_def, mock_ticket)
        
        # Verify error handling
        assert result["status"] == "error"
        assert result.get("error") is not None
        assert mock_ticket.status == TicketStatus.ERROR

    @pytest.mark.asyncio
    async def test_step_result_tracking(self, service_executor, mock_service_def, mock_ticket):
        """Test tracking of step execution results"""
        # Get initialized executor
        executor = await service_executor
        
        # Execute service
        result = await executor.execute_service(mock_service_def, mock_ticket)
        
        # Verify result tracking
        assert result["status"] == "completed"
        assert len(result.get("results", [])) == 2
        
        # Check individual step results
        step1_result = result["results"][0]
        assert step1_result.get("success") is True
        assert step1_result.get("execution_count") == 1
        assert step1_result.get("param1") == "value1"
        
        step2_result = result["results"][1]
        assert step2_result.get("success") is True
        assert step2_result.get("execution_count") == 2
        assert step2_result.get("param2") == "value2"

    @pytest.mark.asyncio
    async def test_error_recovery(self, service_executor, mock_service_def, mock_ticket):
        """Test error recovery mechanisms"""
        # Get initialized executor
        executor = await service_executor
        
        # Register failing tool
        await executor.tool_registry.register_item("failing_tool", FailingMockTool)
        
        # Modify first step to use failing tool
        service_def = dict(mock_service_def)
        service_def["steps"] = list(service_def["steps"])
        service_def["steps"][0] = dict(service_def["steps"][0])
        service_def["steps"][0]["tool"] = "failing_tool"
        
        # Execute service
        result = await executor.execute_service(service_def, mock_ticket)
        
        # Verify error recovery
        assert result["status"] == "error"
        assert result.get("error") is not None
        assert mock_ticket.status == TicketStatus.ERROR
        assert len(result.get("results", [])) == 0  # No successful steps

    @pytest.mark.asyncio
    async def test_parallel_execution_isolation(self, service_executor, mock_service_def):
        """Test isolation of parallel service executions"""
        # Get initialized executor
        executor = await service_executor
        
        # Create two tickets
        ticket1 = Ticket(user_info={"user_id": "user1"}, original_message="Request 1")
        ticket2 = Ticket(user_info={"user_id": "user2"}, original_message="Request 2")
        
        # Execute services in parallel
        task1 = executor.execute_service(mock_service_def, ticket1)
        task2 = executor.execute_service(mock_service_def, ticket2)
        results = await asyncio.gather(task1, task2)
        
        # Verify isolation
        assert all(r["status"] == "completed" for r in results)
        assert all(len(r.get("results", [])) == 2 for r in results)
        assert all(all(step["success"] for step in r["results"]) for r in results)

    @pytest.mark.asyncio
    async def test_execution_monitoring(self, service_executor, mock_service_def, mock_ticket):
        """Test execution monitoring and progress tracking"""
        # Get initialized executor
        executor = await service_executor
        
        # Execute service
        result = await executor.execute_service(mock_service_def, mock_ticket)
        
        # Verify monitoring data
        assert result["status"] == "completed"
        assert len(result.get("results", [])) == 2
        
        # Check execution timestamps and durations
        for step_result in result["results"]:
            assert "start_time" in step_result
            assert "end_time" in step_result
            assert "duration" in step_result
            assert step_result["duration"] >= 0  # Duration should be non-negative 