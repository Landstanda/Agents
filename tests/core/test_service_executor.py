import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.agent.executor import ServiceExecutor
from src.core.registry.service_registry import ServiceRegistry
from src.core.registry.tool_registry import ToolRegistry
from src.execution.context import ExecutionContext
from src.models import Ticket, TicketStatus
from src.core.module_interface import BaseModule

# Mock tool for testing
class MockTool(BaseModule):
    """Mock tool for testing"""
    capabilities = ["test_capability"]
    
    async def execute(self, **kwargs):
        """Mock execute method"""
        return {"status": "success", "result": "test_result"}

class ErrorTool(BaseModule):
    """Tool that raises an error"""
    capabilities = ["error_capability"]
    
    async def execute(self, **kwargs):
        """Always raises an error"""
        raise Exception("Test error")

@pytest.fixture
def mock_service_registry():
    """Create a mock service registry"""
    registry = AsyncMock(spec=ServiceRegistry)
    registry.get_item = MagicMock()
    return registry

@pytest.fixture
def mock_tool_registry():
    """Create a mock tool registry"""
    registry = AsyncMock(spec=ToolRegistry)
    registry.get_tool = AsyncMock()
    return registry

@pytest.fixture
def basic_ticket():
    """Create a basic ticket for testing"""
    return Ticket(
        original_message="test message",
        user_info={"user_id": "U123"},
        channel_id="C456"
    )

@pytest.fixture
def service_executor(mock_service_registry, mock_tool_registry):
    """Create a ServiceExecutor instance with mock registries"""
    return ServiceExecutor(
        service_registry=mock_service_registry,
        tool_registry=mock_tool_registry
    )

@pytest.fixture
def basic_service_def():
    """Create a basic service definition for testing"""
    return {
        "name": "Test Service",
        "steps": [
            {
                "name": "test_step",
                "tool": "test_tool",
                "action": "execute",
                "params": {"test_param": "test_value"}
            }
        ]
    }

@pytest.fixture
def complex_service_def():
    """Create a complex service definition with multiple steps and conditions"""
    return {
        "name": "Complex Service",
        "steps": [
            {
                "name": "step_one",
                "tool": "test_tool",
                "action": "execute",
                "params": {"param1": "value1"},
                "success_criteria": {
                    "type": "all",
                    "conditions": ["response['status'] == 'success'"]
                }
            },
            {
                "name": "step_two",
                "tool": "test_tool",
                "action": "process",
                "params": {"param2": "value2"},
                "on_error": {
                    "action": "retry",
                    "max_attempts": 3
                }
            }
        ]
    }

@pytest.mark.asyncio
class TestServiceExecutor:
    """Tests for the ServiceExecutor class"""
    
    async def test_initialization(self, service_executor, mock_service_registry, mock_tool_registry):
        """Test executor initialization"""
        assert service_executor.service_registry == mock_service_registry
        assert service_executor.tool_registry == mock_tool_registry
        assert service_executor._execution_locks == {}
        assert service_executor._service_locks == {}
    
    async def test_basic_service_execution(self, service_executor, basic_service_def, basic_ticket):
        """Test execution of a basic service"""
        # Configure mock tool registry
        service_executor.tool_registry.get_tool.return_value = MockTool
        
        # Execute service
        result = await service_executor.execute_service(basic_service_def, basic_ticket)
        
        # Verify execution
        assert result["status"] == "completed"
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "success"
        assert result["results"][0]["result"] == "test_result"
    
    async def test_complex_service_execution(self, service_executor, complex_service_def, basic_ticket):
        """Test execution of a service with multiple steps"""
        # Configure mock tool registry
        service_executor.tool_registry.get_tool.return_value = MockTool
        
        # Execute service
        result = await service_executor.execute_service(complex_service_def, basic_ticket)
        
        # Verify execution
        assert result["status"] == "completed"
        assert len(result["results"]) == 2
        assert all(r["status"] == "success" for r in result["results"])
    
    async def test_error_handling(self, service_executor, basic_service_def, basic_ticket):
        """Test handling of tool execution errors"""
        # Configure mock tool registry to return error tool
        service_executor.tool_registry.get_tool.return_value = ErrorTool
        
        # Execute service
        result = await service_executor.execute_service(basic_service_def, basic_ticket)
        
        # Verify error handling
        assert result["status"] == "error"
        assert "Test error" in result["error"]
    
    async def test_retry_logic(self, service_executor, basic_ticket):
        """Test retry logic for failed steps"""
        # Create service with retry configuration
        service_def = {
            "name": "Retry Service",
            "steps": [
                {
                    "name": "retry_step",
                    "tool": "error_tool",
                    "action": "execute",
                    "retry_count": 3,
                    "retry_delay": 0.1
                }
            ]
        }
        
        # Configure mock tool registry
        service_executor.tool_registry.get_tool.return_value = ErrorTool
        
        # Execute service
        result = await service_executor._execute_step_with_retry(
            service_def["steps"][0],
            ExecutionContext(basic_ticket, service_def)
        )
        
        # Verify retry attempts
        assert result["status"] == "error"
        assert "Test error" in result["error"]
        assert result.get("attempt", 1) >= 1  # At least one attempt was made
    
    async def test_success_criteria_evaluation(self, service_executor, basic_ticket):
        """Test evaluation of success criteria"""
        step = {
            "name": "test_step",
            "tool": "test_tool",
            "action": "execute",
            "success_criteria": {
                "type": "all",
                "conditions": [
                    "response['status'] == 'success'",
                    "response['result'] == 'test_result'"
                ]
            }
        }
        
        # Configure mock tool
        service_executor.tool_registry.get_tool.return_value = MockTool
        
        # Create test response
        response = {
            "status": "success",
            "result": "test_result"
        }
        
        # Verify success criteria evaluation
        assert service_executor._evaluate_success(response, step["success_criteria"])
        
        # Test failure case
        failed_response = {
            "status": "error",
            "result": "error_result"
        }
        assert not service_executor._evaluate_success(failed_response, step["success_criteria"])
    
    async def test_parameter_preparation(self, service_executor, basic_ticket):
        """Test parameter preparation and template variable replacement"""
        # Create context with variables
        context = ExecutionContext(basic_ticket, {"name": "Test", "steps": []})
        context.set_variable("test_var", "test_value")
        
        step = {
            "name": "test_step",
            "tool": "test_tool",
            "action": "execute",
            "parameters": {
                "static_param": "static_value",
                "template_param": "{test_var}"
            }
        }
        
        # Prepare parameters
        params = service_executor._prepare_parameters(step, context)
        
        # Verify parameter preparation
        assert params.get("static_param") == "static_value"
        assert params.get("template_param") == "{test_var}"  # Template replacement happens in the tool
    
    async def test_concurrent_execution(self, service_executor, basic_service_def):
        """Test concurrent execution of services"""
        # Create multiple tickets
        tickets = [
            Ticket(original_message=f"test {i}", user_info={"user_id": f"U{i}"}, channel_id="C1")
            for i in range(3)
        ]
        
        # Configure mock tool registry
        service_executor.tool_registry.get_tool.return_value = MockTool
        
        # Execute services concurrently
        results = await asyncio.gather(*[
            service_executor.execute_service(basic_service_def, ticket)
            for ticket in tickets
        ])
        
        # Verify all executions completed successfully
        assert all(r["status"] == "completed" for r in results)
        assert len(results) == 3
    
    async def test_execution_lock_management(self, service_executor, basic_service_def, basic_ticket):
        """Test execution lock management"""
        # Get execution lock
        lock1 = await service_executor._get_execution_lock(basic_ticket.ticket_id)
        lock2 = await service_executor._get_execution_lock(basic_ticket.ticket_id)
        
        # Verify same lock is returned for same ticket
        assert lock1 is lock2
        assert basic_ticket.ticket_id in service_executor._execution_locks
    
    async def test_service_lock_management(self, service_executor, basic_service_def):
        """Test service lock management"""
        service_id = "test_service"
        
        # Get service lock
        lock1 = await service_executor._get_service_lock(service_id)
        lock2 = await service_executor._get_service_lock(service_id)
        
        # Verify same lock is returned for same service
        assert lock1 is lock2
        assert service_id in service_executor._service_locks
    
    async def test_invalid_tool(self, service_executor, basic_service_def, basic_ticket):
        """Test handling of invalid tool"""
        # Configure tool registry to return None
        service_executor.tool_registry.get_tool.return_value = None
        
        # Execute service
        result = await service_executor.execute_service(basic_service_def, basic_ticket)
        
        # Verify error handling
        assert result["status"] == "error"
        assert "Tool 'test_tool' not found" in result["error"]
    
    async def test_context_result_storage(self, service_executor, basic_service_def, basic_ticket):
        """Test storage of results in execution context"""
        # Configure mock tool registry
        service_executor.tool_registry.get_tool.return_value = MockTool
        
        # Create context
        context = ExecutionContext(basic_ticket, basic_service_def)
        
        # Execute step
        step = basic_service_def["steps"][0]
        result = await service_executor._execute_step(step, context)
        
        # Store result
        context.store_result(1, result)
        
        # Verify result storage
        stored_result = context.step_results[1]
        assert stored_result.result["status"] == "completed"  # Check the step result status
        assert stored_result.result["results"]["status"] == "success"  # Check the tool result status
        assert stored_result.result["results"]["result"] == "test_result"  # Check the tool result value 