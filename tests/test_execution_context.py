import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from src.execution.context import ExecutionContext, StepResult
from src.models import Ticket

@pytest.fixture
def mock_ticket():
    ticket = Mock(spec=Ticket)
    ticket.ticket_id = "test-123"
    ticket.entities = {"entity1": "value1", "entity2": "value2"}
    return ticket

@pytest.fixture
def mock_service():
    return {
        "name": "test_service",
        "steps": [
            {"name": "step1", "tool": "tool1"},
            {"name": "step2", "tool": "tool2"}
        ]
    }

@pytest.fixture
def context(mock_ticket, mock_service):
    return ExecutionContext(mock_ticket, mock_service)

class TestStepResult:
    def test_step_result_initialization(self):
        """Test StepResult dataclass initialization"""
        step = StepResult(
            step_number=1,
            step_name="test_step",
            success=True,
            result={"data": "test"},
            error=None
        )
        
        assert step.step_number == 1
        assert step.step_name == "test_step"
        assert step.success is True
        assert step.result == {"data": "test"}
        assert step.error is None
        assert isinstance(step.start_time, datetime)
        assert step.end_time is None
        assert step.duration is None

class TestExecutionContext:
    def test_initialization(self, context, mock_ticket, mock_service):
        """Test ExecutionContext initialization"""
        assert context.ticket == mock_ticket
        assert context.service == mock_service
        assert context.current_step is None
        assert context.step_results == {}
        assert context.variables == mock_ticket.entities
        assert isinstance(context.start_time, datetime)

    def test_store_result(self, context):
        """Test storing step results"""
        # Set current step
        current_step = {"name": "test_step"}
        context.set_current_step(current_step, 1)
        
        # Store result
        result = {"output": "test_output"}
        context.store_result(step_number=1, result=result, success=True)
        
        # Verify stored result
        stored = context.step_results[1]
        assert stored.step_number == 1
        assert stored.step_name == "test_step"
        assert stored.success is True
        assert stored.result == result
        assert stored.error is None
        assert isinstance(stored.end_time, datetime)
        assert isinstance(stored.duration, float)

    def test_store_result_with_output_vars(self, context):
        """Test storing results with output variable mapping"""
        current_step = {
            "name": "test_step",
            "output_vars": {
                "output_var": "output.value"
            }
        }
        context.set_current_step(current_step, 1)
        
        result = {"output": {"value": "test_value"}}
        context.store_result(step_number=1, result=result)
        
        assert context.get_variable("output_var") == "test_value"

    def test_get_result(self, context):
        """Test retrieving step results"""
        # Store a result
        context.store_result(step_number=1, result={"data": "test"}, success=True)
        
        # Get the result
        result = context.get_result(1)
        assert result == {"data": "test"}
        
        # Test non-existent result
        assert context.get_result(999) is None

    def test_variable_operations(self, context):
        """Test variable operations"""
        # Test setting and getting simple variables
        context.set_variable("test_var", "test_value")
        assert context.get_variable("test_var") == "test_value"
        
        # Test nested variable operations
        context.set_variable("nested.var", "nested_value")
        assert context.get_variable("nested.var") == "nested_value"
        
        # Test default value
        assert context.get_variable("non_existent", "default") == "default"

    def test_execution_summary(self, context):
        """Test getting execution summary"""
        # Add some step results
        context.store_result(step_number=1, result={"data": "test1"}, success=True)
        context.store_result(step_number=2, result={"data": "test2"}, success=False, error="Error message")
        
        summary = context.get_execution_summary()
        
        assert summary["ticket_id"] == "test-123"
        assert summary["service"] == "test_service"
        assert summary["total_steps"] == 2
        assert summary["successful_steps"] == 1
        assert summary["success"] is False
        assert isinstance(summary["duration"], float)

    def test_failed_steps(self, context):
        """Test failed steps tracking"""
        # Add mixed success/failure results
        context.store_result(step_number=1, result={"data": "test1"}, success=True)
        context.store_result(step_number=2, result={"data": "test2"}, success=False, error="Error")
        
        assert context.has_failed_steps() is True
        failed_steps = context.get_failed_steps()
        assert len(failed_steps) == 1
        assert failed_steps[0].step_number == 2
        assert failed_steps[0].error == "Error"

    def test_rollback(self, context):
        """Test context rollback"""
        # Set up some state
        context.set_variable("test_var", "test_value")
        context.store_result(step_number=1, result={"data": "test"}, success=True)
        context.set_current_step({"name": "test_step"}, 1)
        
        # Perform rollback
        context.rollback()
        
        # Verify state is reset
        assert context.step_results == {}
        assert context.current_step is None
        assert context.variables == context.ticket.entities  # Original entities should remain

    def test_clear_variables(self, context):
        """Test clearing variables while preserving entities"""
        # Set up variables
        original_entities = context.ticket.entities.copy()
        context.set_variable("test_var", "test_value")
        
        # Clear variables
        context.clear_variables()
        
        # Verify only entities remain
        assert context.variables == original_entities
        assert "test_var" not in context.variables

    @pytest.mark.parametrize("step_number,step", [
        (1, {"name": "step1"}),
        (2, {"name": "step2"}),
    ])
    def test_set_current_step(self, context, step_number, step):
        """Test setting current step with different values"""
        context.set_current_step(step, step_number)
        assert context.current_step == {**step, "step_number": step_number}

    def test_get_all_results(self, context):
        """Test retrieving all results in order"""
        # Store results out of order
        context.store_result(step_number=2, result={"data": "test2"}, success=True)
        context.store_result(step_number=1, result={"data": "test1"}, success=True)
        
        results = context.get_all_results()
        assert len(results) == 2
        assert results[0].step_number == 1
        assert results[1].step_number == 2

    def test_error_handling(self, context):
        """Test error handling in variable operations"""
        # Test invalid nested variable access
        assert context.get_variable("invalid.nested.path") is None
        
        # Test setting invalid nested path
        context.set_variable("test", "not_a_dict")  # Set a non-dict value
        with pytest.raises(Exception):
            context.set_variable("test.nested.path", "value")  # Try to set nested path on non-dict

if __name__ == "__main__":
    pytest.main(["-v", "test_execution_context.py"]) 