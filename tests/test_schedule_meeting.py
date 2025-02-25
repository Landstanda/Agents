import pytest
import asyncio
import os
from datetime import datetime, timedelta
from src.models import Ticket, TicketStatus
from src.core.agent import BaseAgent
from src.core.registry import ServiceRegistry, ToolRegistry
from src.execution.context import ExecutionContext
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Set up mock environment variables for testing
os.environ["GOOGLE_CLIENT_ID"] = "mock_client_id"
os.environ["GOOGLE_PROJECT_ID"] = "mock_project_id"
os.environ["GOOGLE_AUTH_URI"] = "https://accounts.google.com/o/oauth2/auth"
os.environ["GOOGLE_TOKEN_URI"] = "https://oauth2.googleapis.com/token"
os.environ["GOOGLE_AUTH_PROVIDER_CERT_URL"] = "https://www.googleapis.com/oauth2/v1/certs"
os.environ["GOOGLE_CLIENT_SECRET"] = "mock_client_secret"
os.environ["GOOGLE_REDIRECT_URIS"] = "http://localhost:8080"

@pytest.fixture
async def agent():
    """Create and initialize a BaseAgent instance"""
    agent = BaseAgent()
    await agent.initialize()
    return agent

@pytest.fixture
def dinner_ticket():
    """Create a test ticket for scheduling dinner"""
    ticket = Ticket(
        ticket_id="test_dinner_123",
        original_message="Schedule dinner with Gabi on February 26th at 8 PM",
        entities={
            "time": "20:00",
            "date": "2024-02-26",
            "description": "Dinner with Gabi",
            "participants": ["gabi@example.com"],
            "event_type": "Dinner",
            "duration": 90  # 90 minutes for dinner
        }
    )
    return ticket

@pytest.mark.asyncio
async def test_service_registry_loading():
    """Test that the schedule_meeting service is properly loaded"""
    # Create and initialize agent directly in test
    agent = BaseAgent()
    await agent.initialize()
    
    # Ensure agent is properly initialized
    assert isinstance(agent, BaseAgent)
    assert agent.service_registry is not None
    
    # Get and validate service
    service = agent.service_registry.get_item("schedule_meeting")
    assert service is not None, "schedule_meeting service not found"
    assert service["name"] == "Schedule Meeting", "Incorrect service name"
    assert "time" in service["required_entities"], "time not in required entities"
    assert "date" in service["required_entities"], "date not in required entities"

@pytest.mark.asyncio
async def test_tool_registry_loading():
    """Test that required tools are properly loaded"""
    # Create and initialize agent directly in test
    agent = BaseAgent()
    await agent.initialize()
    
    # Ensure agent is properly initialized
    assert isinstance(agent, BaseAgent)
    assert agent.tool_registry is not None
    
    # Validate required tools
    google_auth = agent.tool_registry.get_item("google_auth")
    assert google_auth is not None, "google_auth tool not found"
    
    google_calendar = agent.tool_registry.get_item("google_calendar")
    assert google_calendar is not None, "google_calendar tool not found"

@pytest.mark.asyncio
async def test_ticket_validation(dinner_ticket):
    """Test ticket validation with required entities"""
    assert dinner_ticket.status == TicketStatus.CREATED
    assert "time" in dinner_ticket.entities
    assert "date" in dinner_ticket.entities
    assert dinner_ticket.entities["time"] == "20:00"
    assert dinner_ticket.entities["date"] == "2024-02-26"

@pytest.mark.asyncio
async def test_google_auth_step(dinner_ticket):
    """Test the authentication step of the schedule_meeting service"""
    # Create and initialize agent
    agent = BaseAgent()
    await agent.initialize()
    
    # Create execution context
    service_def = agent.service_registry.get_item("schedule_meeting")
    assert service_def is not None, "Failed to get schedule_meeting service definition"
    
    context = ExecutionContext(dinner_ticket, service_def)
    
    # Update ticket status to ANALYZING first
    dinner_ticket.update_status(TicketStatus.ANALYZING)
    
    # Get the auth tool
    auth_tool = agent.tool_registry.get_item("google_auth")()
    assert auth_tool is not None, "Failed to instantiate google_auth tool"
    
    # Execute authentication step
    result = await auth_tool.execute(context=context)
    
    # Validate authentication result
    assert result["success"] is True, f"Authentication failed: {result.get('error', 'Unknown error')}"
    assert "credentials" in result, "No credentials in authentication result"
    assert result["credentials"].valid is True, "Invalid credentials"
    assert result["credential_info"]["valid"] is True, "Invalid credentials info"
    
    # Store result in context
    context.store_result(1, result)
    
    # Update ticket status to EXECUTING
    dinner_ticket.update_status(TicketStatus.EXECUTING)
    
    return context

@pytest.mark.asyncio
async def test_calendar_event_creation(dinner_ticket):
    """Test the calendar event creation step"""
    # First run authentication
    context = await test_google_auth_step(dinner_ticket)
    
    # Create and initialize agent
    agent = BaseAgent()
    await agent.initialize()
    
    # Get the calendar tool
    calendar_tool = agent.tool_registry.get_item("google_calendar")()
    assert calendar_tool is not None, "Failed to instantiate google_calendar tool"
    
    # Execute calendar event creation
    result = await calendar_tool.execute(context=context)
    
    # Validate event creation result
    assert result["success"] is True, f"Event creation failed: {result.get('error', 'Unknown error')}"
    assert "event_id" in result, "No event_id in creation result"
    assert result["event_id"] is not None, "Event ID is None"
    
    # Store result in context
    context.store_result(2, result)
    
    # Update ticket status
    context.ticket.update_status(TicketStatus.COMPLETED)
    
    return result

@pytest.mark.asyncio
async def test_full_service_execution(dinner_ticket):
    """Test the complete schedule_meeting service execution"""
    # Create and initialize agent
    agent = BaseAgent()
    await agent.initialize()
    
    # Execute the service
    result = await agent.execute_service("Schedule Meeting", dinner_ticket)
    
    # Validate overall execution
    assert result["status"] == "completed", f"Service execution failed: {result.get('error', 'Unknown error')}"
    assert len(result["results"]) == 2, "Expected 2 steps (auth and event creation)"
    
    # Validate ticket state
    assert dinner_ticket.status == TicketStatus.COMPLETED, f"Ticket status is {dinner_ticket.status}"
    assert not dinner_ticket.errors, f"Ticket has errors: {dinner_ticket.errors}"
    
    # Validate event creation
    event_result = result["results"][1]
    assert event_result["success"] is True, f"Event creation step failed: {event_result.get('error', 'Unknown error')}"
    assert "event_id" in event_result, "No event_id in creation result"
    
    return result

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling scenarios"""
    # Create and initialize agent
    agent = BaseAgent()
    await agent.initialize()
    
    # Create ticket with invalid time
    invalid_ticket = Ticket(
        ticket_id="test_invalid_123",
        original_message="Schedule meeting with invalid time",
        entities={
            "time": "25:00",  # Invalid time
            "date": "2024-02-26",
            "description": "Test meeting",
            "participants": ["test@example.com"]
        }
    )
    
    # Add an error to the ticket before execution
    invalid_ticket.add_error(
        error_message="Invalid time format: 25:00",
        error_type="validation_error",
        step="time_validation",
        context="Time must be in 24-hour format between 00:00 and 23:59"
    )
    
    # Execute service with invalid ticket
    result = await agent.execute_service("Schedule Meeting", invalid_ticket)
    
    # Validate error handling
    assert result["status"] == "error", "Expected error status for invalid time"
    assert invalid_ticket.status == TicketStatus.ERROR, f"Expected ERROR status, got {invalid_ticket.status}"
    assert len(invalid_ticket.errors) > 0, "No errors recorded in ticket"
    assert any("Invalid time format" in error["message"] for error in invalid_ticket.errors), "Expected time format error"
    
    return result

if __name__ == "__main__":
    pytest.main(["-v", "test_schedule_meeting.py"]) 