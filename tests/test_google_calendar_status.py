import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.models.ticket import Ticket, TicketStatus
from src.modules.google_calendar import GoogleCalendarModule
from src.execution.context import ExecutionContext

@pytest.fixture
def calendar_ticket():
    """Create a test ticket for calendar operations"""
    ticket = Ticket(
        ticket_id="test_calendar_123",
        original_message="Schedule a meeting",
        entities={
            "operation": "create_event",
            "time": "3:00 PM",
            "date": "2025-03-01",
            "description": "Test meeting",
            "participants": ["test@example.com"],
            "duration": 60
        }
    )
    return ticket

@pytest.fixture
def mock_context(calendar_ticket):
    """Create a mock execution context"""
    context = MagicMock(spec=ExecutionContext)
    context.ticket = calendar_ticket
    
    # Mock the get_result method to return authentication result
    context.get_result.return_value = {
        "success": True,
        "credentials": MagicMock()  # Mock credentials object
    }
    
    return context

@pytest.mark.asyncio
async def test_calendar_module_status_handling(mock_context):
    """Test that the GoogleCalendarModule handles ticket status correctly"""
    # Create module
    calendar_module = GoogleCalendarModule()
    
    # Mock the _initialize_service method to return a mock service
    with patch.object(calendar_module, '_initialize_service', new_callable=AsyncMock) as mock_init:
        mock_init.return_value = MagicMock()  # Mock service
        
        # Mock the _create_event method to return success
        with patch.object(calendar_module, '_create_event', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                "success": True,
                "event_id": "test_event_123",
                "event_link": "https://calendar.google.com/event?id=test_event_123"
            }
            
            # Execute the module
            result = await calendar_module.execute(mock_context)
            
            # Verify the result
            assert result["success"] is True
            assert "event_id" in result
            
            # The module should NOT have set the ticket status to COMPLETED
            # That should be handled by the executor
            assert mock_context.ticket.status != TicketStatus.COMPLETED

@pytest.mark.asyncio
async def test_calendar_module_error_handling(mock_context):
    """Test that the GoogleCalendarModule handles errors correctly"""
    # Create module
    calendar_module = GoogleCalendarModule()
    
    # Mock the _initialize_service method to return None (failure)
    with patch.object(calendar_module, '_initialize_service', new_callable=AsyncMock) as mock_init:
        mock_init.return_value = None  # Service initialization failed
        
        # Execute the module
        result = await calendar_module.execute(mock_context)
        
        # Verify the result
        assert result["success"] is False
        assert "error" in result
        
        # The module should have set the ticket status to ERROR
        assert mock_context.ticket.status == TicketStatus.ERROR

@pytest.mark.asyncio
async def test_calendar_module_operation_error(mock_context):
    """Test that the GoogleCalendarModule handles operation errors correctly"""
    # Create module
    calendar_module = GoogleCalendarModule()
    
    # Mock the _initialize_service method to return a mock service
    with patch.object(calendar_module, '_initialize_service', new_callable=AsyncMock) as mock_init:
        mock_init.return_value = MagicMock()  # Mock service
        
        # Set an unsupported operation
        mock_context.ticket.entities["operation"] = "unsupported_operation"
        
        # Execute the module
        result = await calendar_module.execute(mock_context)
        
        # Verify the result
        assert result["success"] is False
        assert "Unsupported operation" in result["error"]
        
        # The module should have set the ticket status to ERROR
        assert mock_context.ticket.status == TicketStatus.ERROR 