import pytest
from datetime import datetime
from src.models.ticket import Ticket, TicketStatus
from src.core.module_interface import ModuleResponse

@pytest.fixture
def user_info():
    return {
        "user_id": "U123",
        "channel_id": "C456",
        "thread_ts": "1234567890.123",
        "username": "test_user"
    }

@pytest.fixture
def basic_ticket(user_info):
    return Ticket(
        user_info=user_info,
        original_message="Schedule a meeting with John tomorrow at 3 PM"
    )

class TestTicket:
    def test_ticket_initialization(self, user_info):
        """Test basic ticket initialization and attributes"""
        message = "Schedule a meeting with John tomorrow at 3 PM"
        ticket = Ticket(user_info=user_info, original_message=message)
        
        assert ticket.ticket_id is not None
        assert ticket.user_info == user_info
        assert ticket.original_message == message
        assert ticket.status == TicketStatus.CREATED
        assert isinstance(ticket.created_at, datetime)
        assert ticket.entities == {}
        assert ticket.conversation_history == []
        assert ticket.error_history == []
        
    def test_status_lifecycle(self, basic_ticket):
        """Test ticket status transitions through typical lifecycle"""
        # Initial state
        assert basic_ticket.status == TicketStatus.CREATED
        
        # Typical flow
        basic_ticket.update_status(TicketStatus.ANALYZING)
        assert basic_ticket.status == TicketStatus.ANALYZING
        
        basic_ticket.update_status(TicketStatus.EXECUTING)
        assert basic_ticket.status == TicketStatus.EXECUTING
        
        basic_ticket.update_status(TicketStatus.COMPLETED)
        assert basic_ticket.status == TicketStatus.COMPLETED
        
        # Verify status history
        assert len(basic_ticket.status_history) == 4
        assert basic_ticket.status_history[0]["status"] == TicketStatus.CREATED
        
    def test_entity_management(self, basic_ticket):
        """Test entity addition, update, and retrieval"""
        # Add entities
        entities = {
            "time": "3 PM",
            "date": "tomorrow",
            "person": "John"
        }
        basic_ticket.update_entities(entities)
        assert basic_ticket.entities == entities
        
        # Update existing entity
        basic_ticket.update_entities({"time": "4 PM"})
        assert basic_ticket.entities["time"] == "4 PM"
        assert len(basic_ticket.entities) == 3
        
        # Add new entity
        basic_ticket.update_entities({"location": "office"})
        assert basic_ticket.entities["location"] == "office"
        assert len(basic_ticket.entities) == 4
        
    def test_conversation_management(self, basic_ticket):
        """Test conversation history tracking"""
        # Add incoming message
        basic_ticket.add_incoming_message("What time works best for you?")
        assert len(basic_ticket.conversation_history) == 1
        assert basic_ticket.conversation_history[0]["type"] == "incoming"
        
        # Add outgoing message
        basic_ticket.add_outgoing_message("I can schedule it for 3 PM.")
        assert len(basic_ticket.conversation_history) == 2
        assert basic_ticket.conversation_history[1]["type"] == "outgoing"
        
        # Verify conversation order and content
        conversation = basic_ticket.get_conversation_history()
        assert len(conversation) == 2
        assert conversation[0]["message"] == "What time works best for you?"
        assert conversation[1]["message"] == "I can schedule it for 3 PM."
        
    def test_error_handling(self, basic_ticket):
        """Test error tracking and management"""
        # Add error with context
        basic_ticket.add_error(
            "Failed to connect to calendar",
            error_type="api_error",
            context="calendar_service"
        )
        assert len(basic_ticket.error_history) == 1
        assert basic_ticket.error_history[0]["message"] == "Failed to connect to calendar"
        assert basic_ticket.error_history[0]["type"] == "api_error"
        
        # Add another error
        basic_ticket.add_error(
            "Invalid time format",
            error_type="validation_error"
        )
        assert len(basic_ticket.error_history) == 2
        
        # Verify error history
        errors = basic_ticket.get_error_history()
        assert len(errors) == 2
        assert errors[0]["type"] == "api_error"
        assert errors[1]["type"] == "validation_error"
        
    def test_service_execution_tracking(self, basic_ticket):
        """Test tracking of service execution details"""
        # Add service execution
        service_def = {
            "name": "calendar_service",
            "steps": [
                {"name": "validate_time"},
                {"name": "check_availability"}
            ]
        }
        basic_ticket.set_service(service_def)
        assert basic_ticket.service["name"] == "calendar_service"
        
        # Add step results
        basic_ticket.add_step_result(1, {
            "success": True,
            "data": {"valid_time": True}
        })
        assert len(basic_ticket.step_results) == 1
        
        basic_ticket.add_step_result(2, {
            "success": False,
            "error": "Time slot not available"
        })
        assert len(basic_ticket.step_results) == 2
        
        # Verify execution summary
        summary = basic_ticket.get_execution_summary()
        assert summary["total_steps"] == 2
        assert summary["successful_steps"] == 1
        assert not summary["success"]
        
    def test_waiting_state_management(self, basic_ticket):
        """Test handling of waiting states and user input"""
        # Set waiting state
        basic_ticket.update_status(TicketStatus.WAITING_INPUT)
        basic_ticket.set_waiting_for("time_confirmation")
        
        assert basic_ticket.status == TicketStatus.WAITING_INPUT
        assert basic_ticket.waiting_for == "time_confirmation"
        
        # Add user response
        basic_ticket.add_incoming_message("Yes, 3 PM works.")
        basic_ticket.clear_waiting_state()
        
        assert basic_ticket.waiting_for is None
        assert len(basic_ticket.conversation_history) == 1
        
    def test_retry_handling(self, basic_ticket):
        """Test retry mechanism and attempt tracking"""
        # Set up retry scenario
        basic_ticket.set_retry_count("calendar_check", max_attempts=3)
        
        # First attempt
        basic_ticket.increment_retry("calendar_check")
        assert basic_ticket.get_retry_count("calendar_check") == 1
        
        # Second attempt
        basic_ticket.increment_retry("calendar_check")
        assert basic_ticket.get_retry_count("calendar_check") == 2
        
        # Check if can retry
        assert basic_ticket.can_retry("calendar_check") is True
        
        # Final attempt
        basic_ticket.increment_retry("calendar_check")
        assert basic_ticket.can_retry("calendar_check") is False
        
    def test_context_preservation(self, basic_ticket):
        """Test preservation of context across status changes"""
        # Set initial context
        basic_ticket.update_entities({"time": "3 PM"})
        basic_ticket.add_context_data("calendar_id", "primary")
        
        # Change status
        basic_ticket.update_status(TicketStatus.ANALYZING)
        
        # Verify context preserved
        assert basic_ticket.entities["time"] == "3 PM"
        assert basic_ticket.get_context_data("calendar_id") == "primary"
        
        # Update context
        basic_ticket.update_context_data("calendar_id", "secondary")
        assert basic_ticket.get_context_data("calendar_id") == "secondary"
        
    def test_serialization(self, basic_ticket):
        """Test ticket serialization and deserialization"""
        # Add some data
        basic_ticket.update_entities({"time": "3 PM"})
        basic_ticket.add_incoming_message("Can we make it 4 PM?")
        basic_ticket.add_error("Test error", "test_error")
        
        # Serialize
        ticket_dict = basic_ticket.to_dict()
        
        # Create new ticket from dict
        new_ticket = Ticket.from_dict(ticket_dict)
        
        # Verify data preserved
        assert new_ticket.ticket_id == basic_ticket.ticket_id
        assert new_ticket.entities == basic_ticket.entities
        assert len(new_ticket.conversation_history) == len(basic_ticket.conversation_history)
        assert len(new_ticket.error_history) == len(basic_ticket.error_history)
        
    def test_invalid_status_transition(self, basic_ticket):
        """Test handling of invalid status transitions"""
        basic_ticket.update_status(TicketStatus.ANALYZING)
        
        # Try to transition from ANALYZING to COMPLETED (invalid)
        with pytest.raises(ValueError):
            basic_ticket.update_status(TicketStatus.COMPLETED)
            
    def test_execution_result_tracking(self, basic_ticket):
        """Test tracking of execution results and success evaluation"""
        # Add successful step
        step1_result = ModuleResponse(
            success=True,
            data={"validated": True}
        )
        basic_ticket.add_step_result(1, step1_result)
        
        # Add failed step
        step2_result = ModuleResponse(
            success=False,
            error="API Error"
        )
        basic_ticket.add_step_result(2, step2_result)
        
        # Get execution summary
        summary = basic_ticket.get_execution_summary()
        assert not summary["success"]
        assert summary["successful_steps"] == 1
        assert summary["failed_steps"] == 1
        
        # Check last error
        assert basic_ticket.get_last_error()["message"] == "API Error"

if __name__ == "__main__":
    pytest.main(["-v", "test_ticket.py"]) 