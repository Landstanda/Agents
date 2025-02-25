import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from src.models import Ticket, TicketStatus
from src.core.agent.service_agent import ServiceAgent, ServiceExecutionState, ExecutionStatus, StepResult
from src.core.registry import ServiceRegistry, ToolRegistry
from src.core.module_interface import ModuleResponse, BaseModule
from src.execution.context import ExecutionContext

# Test Tools
class RetryableFailingTool(BaseModule):
    """Mock tool that fails initially but succeeds on retry"""
    def __init__(self, succeed_after_attempts=2):
        self.attempts = 0
        self.succeed_after_attempts = succeed_after_attempts
        
    async def execute(self, context: ExecutionContext, **params) -> dict:
        self.attempts += 1
        if self.attempts >= self.succeed_after_attempts:
            return ModuleResponse(success=True, data={"attempt": self.attempts}).to_dict()
        return ModuleResponse(
            success=False,
            error=f"Failed attempt {self.attempts}",
            error_type="retryable_error"
        ).to_dict()
        
    @property
    def capabilities(self):
        return ["test_action"]

class PermanentFailingTool(BaseModule):
    """Mock tool that always fails with non-retryable error"""
    async def execute(self, context: ExecutionContext, **params) -> dict:
        return ModuleResponse(
            success=False,
            error="Permanent failure",
            error_type="permanent_error"
        ).to_dict()
        
    @property
    def capabilities(self):
        return ["test_action"]

class AlternativeStepTool(BaseModule):
    """Mock tool for alternative step execution"""
    async def execute(self, context: ExecutionContext, **params) -> dict:
        return ModuleResponse(success=True, data={"alternative": True}).to_dict()
        
    @property
    def capabilities(self):
        return ["alternative_action"]

# Test Fixtures
@pytest.fixture
def service_registry():
    registry = ServiceRegistry()
    registry._initialized = True
    registry.items = {
        "test_service": {
            "name": "test_service",
            "steps": [
                {
                    "name": "retryable_step",
                    "tool": "retryable_tool",
                    "action": "test_action",
                    "retry_count": 3,
                    "retry_delay": 0.1,
                    "alternative_step": {
                        "tool": "alternative_tool",
                        "action": "alternative_action",
                        "name": "retryable_step"
                    }
                }
            ]
        }
    }
    return registry

@pytest.fixture
def tool_registry():
    registry = ToolRegistry()
    registry._initialized = True
    registry.items = {
        "retryable_tool": RetryableFailingTool(succeed_after_attempts=2),
        "permanent_tool": PermanentFailingTool(),
        "alternative_tool": AlternativeStepTool()
    }
    return registry

@pytest.fixture
def service_agent(service_registry, tool_registry):
    agent = ServiceAgent()
    agent.service_registry = service_registry
    agent.tool_registry = tool_registry
    agent._initialized = True
    return agent

@pytest.fixture
def basic_ticket():
    return Ticket(
        user_info={"user_id": "U123", "channel_id": "C456"},
        original_message="Test request"
    )

# Test ServiceExecutionState
class TestServiceExecutionState:
    def test_initial_state(self):
        state = ServiceExecutionState()
        assert state.steps_succeeded == []
        assert state.steps_failed == []
        assert state.current_step is None
        assert state.error_history == []
        assert state.execution_status == ExecutionStatus.SUCCESS
        assert not state.has_permanent_error

    def test_update_from_step_result_success(self):
        state = ServiceExecutionState()
        result = StepResult(
            step_name="test_step",
            success=True,
            status=ExecutionStatus.SUCCESS
        )
        state.update_from_step_result(result)
        assert "test_step" in state.steps_succeeded
        assert "test_step" not in state.steps_failed

    def test_update_from_step_result_permanent_error(self):
        state = ServiceExecutionState()
        result = StepResult(
            step_name="test_step",
            success=False,
            status=ExecutionStatus.PERMANENT_ERROR
        )
        state.update_from_step_result(result)
        assert "test_step" in state.steps_failed
        assert state.has_permanent_error
        assert state.execution_status == ExecutionStatus.PERMANENT_ERROR

# Test Step Execution
class TestStepExecution:
    @pytest.mark.asyncio
    async def test_successful_step(self, service_agent, basic_ticket):
        step = {
            "name": "test_step",
            "tool": "alternative_tool",
            "action": "test_action"
        }
        result = await service_agent._execute_step_with_retry(step, basic_ticket)
        assert result.success
        assert result.status == ExecutionStatus.SUCCESS
        assert not result.error_message

    @pytest.mark.asyncio
    async def test_permanent_error(self, service_agent, basic_ticket):
        step = {
            "name": "test_step",
            "tool": "permanent_tool",
            "action": "test_action"
        }
        result = await service_agent._execute_step_with_retry(step, basic_ticket)
        assert not result.success
        assert result.status == ExecutionStatus.PERMANENT_ERROR
        assert "Permanent failure" in result.error_message

    @pytest.mark.asyncio
    async def test_retry_success(self, service_agent, basic_ticket):
        step = {
            "name": "test_step",
            "tool": "retryable_tool",
            "action": "test_action",
            "retry_count": 3,
            "retry_delay": 0.1
        }
        result = await service_agent._execute_step_with_retry(step, basic_ticket)
        assert result.success
        assert result.status == ExecutionStatus.SUCCESS
        assert result.retries == 1  # Should succeed on second attempt

# Test Service Execution
class TestServiceExecution:
    @pytest.mark.asyncio
    async def test_service_not_found(self, service_agent, basic_ticket):
        result = await service_agent.execute_service("nonexistent_service", basic_ticket)
        assert result["status"] == "error"
        assert "not found" in result["error"]
        assert basic_ticket.status == TicketStatus.ERROR

    @pytest.mark.asyncio
    async def test_successful_service(self, service_agent, basic_ticket):
        # Configure tool to succeed immediately
        service_agent.tool_registry.items["retryable_tool"] = RetryableFailingTool(succeed_after_attempts=1)
        result = await service_agent.execute_service("test_service", basic_ticket)
        assert result["status"] == "completed"
        assert result["success"]
        assert basic_ticket.status == TicketStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_service_with_permanent_error(self, service_agent, basic_ticket):
        # Configure permanent failure
        service_agent.tool_registry.items["retryable_tool"] = PermanentFailingTool()
        result = await service_agent.execute_service("test_service", basic_ticket)
        assert result["status"] == "error"
        assert not result["success"]
        assert basic_ticket.status == TicketStatus.ERROR
        assert "Permanent failure" in result["error"]

if __name__ == "__main__":
    pytest.main(["-v", "test_error_recovery.py"]) 