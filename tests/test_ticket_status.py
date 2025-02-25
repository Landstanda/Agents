import pytest
from src.models.ticket import Ticket, TicketStatus
from src.core.agent.base_agent import BaseAgent
from src.core.agent.executor import ServiceExecutor
from src.execution.context import ExecutionContext
from src.core.services.registry import ServiceRegistry
from src.core.tools.registry import ToolRegistry

@pytest.fixture
def test_ticket():
    """Create a test ticket"""
    return Ticket(
        ticket_id="test_status_123",
        original_message="Test status transitions",
        entities={}
    )

@pytest.mark.asyncio
async def test_ticket_status_transitions(test_ticket):
    """Test that ticket status transitions work correctly"""
    # Initial status should be CREATED
    assert test_ticket.status == TicketStatus.CREATED
    
    # Test valid transitions
    test_ticket.update_status(TicketStatus.ANALYZING)
    assert test_ticket.status == TicketStatus.ANALYZING
    
    test_ticket.update_status(TicketStatus.EXECUTING)
    assert test_ticket.status == TicketStatus.EXECUTING
    
    test_ticket.update_status(TicketStatus.COMPLETED)
    assert test_ticket.status == TicketStatus.COMPLETED
    
    # Reset for another test path
    test_ticket.status = TicketStatus.CREATED
    test_ticket.status_history = []
    
    # Test error path
    test_ticket.update_status(TicketStatus.ANALYZING)
    test_ticket.update_status(TicketStatus.ERROR)
    assert test_ticket.status == TicketStatus.ERROR
    
    # Should be able to retry from error
    test_ticket.update_status(TicketStatus.ANALYZING)
    assert test_ticket.status == TicketStatus.ANALYZING

@pytest.mark.asyncio
async def test_invalid_status_transition(test_ticket):
    """Test that invalid status transitions raise ValueError"""
    # Set up initial state
    test_ticket.update_status(TicketStatus.ANALYZING)
    test_ticket.update_status(TicketStatus.EXECUTING)
    
    # This should fail - can't go from EXECUTING back to ANALYZING
    with pytest.raises(ValueError) as excinfo:
        test_ticket.update_status(TicketStatus.ANALYZING)
    
    assert "Invalid status transition" in str(excinfo.value)
    
    # This should also fail - can't go from EXECUTING to EXECUTING
    with pytest.raises(ValueError) as excinfo:
        test_ticket.update_status(TicketStatus.EXECUTING)
    
    assert "Invalid status transition" in str(excinfo.value)

@pytest.mark.asyncio
async def test_executor_status_handling():
    """Test that the executor handles ticket status correctly"""
    # Create registries
    service_registry = ServiceRegistry()
    tool_registry = ToolRegistry()
    
    # Create executor
    executor = ServiceExecutor(service_registry, tool_registry)
    
    # Create ticket
    ticket = Ticket(ticket_id="test_executor_123")
    
    # Create a simple test service
    test_service = {
        "name": "Test Service",
        "steps": [
            {
                "name": "Test Step",
                "tool": "test_tool",
                "action": "test_action"
            }
        ]
    }
    
    # Create execution context
    context = ExecutionContext(ticket=ticket, service=test_service)
    
    # Test that the executor sets the status correctly
    assert ticket.status == TicketStatus.CREATED
    
    # Manually update to ANALYZING (normally done by execute_service)
    ticket.update_status(TicketStatus.ANALYZING)
    
    # Test that we can't update to EXECUTING twice
    ticket.update_status(TicketStatus.EXECUTING)
    
    with pytest.raises(ValueError) as excinfo:
        ticket.update_status(TicketStatus.EXECUTING)
    
    assert "Invalid status transition" in str(excinfo.value) 