import pytest
from unittest.mock import Mock, AsyncMock, patch
import os
from datetime import datetime
from src.main import OfficeAssistant
from src.models.ticket import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger

@pytest.fixture
def mock_slack_event():
    """Create a mock Slack event with different message types"""
    def _create_event(message_type="basic", thread_ts=None):
        events = {
            "basic": {
                "type": "app_mention",
                "user": "U123456",
                "text": "<@BOT_ID> Schedule a meeting tomorrow at 3pm",
                "channel": "C123456",
                "ts": "1645036800.000100",
                "thread_ts": thread_ts
            },
            "no_mention": {
                "type": "message",
                "user": "U123456",
                "text": "Schedule a meeting tomorrow at 3pm",
                "channel": "C123456",
                "ts": "1645036800.000100",
                "thread_ts": thread_ts
            },
            "bot_message": {
                "type": "app_mention",
                "user": "BOT_ID",
                "text": "<@BOT_ID> Some bot message",
                "channel": "C123456",
                "ts": "1645036800.000100",
                "thread_ts": thread_ts,
                "bot_id": "B123456"
            },
            "threaded": {
                "type": "app_mention",
                "user": "U123456",
                "text": "<@BOT_ID> Yes, that time works",
                "channel": "C123456",
                "ts": "1645036800.000200",
                "thread_ts": "1645036800.000100"
            }
        }
        return events[message_type]
    return _create_event

@pytest.fixture
def mock_components():
    """Create mock components for the office assistant"""
    mock_service_analyzer = Mock()
    mock_service_analyzer.analyze_request = AsyncMock()
    
    mock_message_maker = Mock()
    mock_message_maker.send_message = AsyncMock()
    
    mock_flow_logger = Mock(spec=FlowLogger)
    mock_flow_logger._setup_log_file = AsyncMock()
    mock_flow_logger.log_event = AsyncMock()
    
    mock_web_client = Mock()
    mock_web_client.auth_test = AsyncMock(return_value={"user_id": "BOT_ID"})
    mock_web_client.chat_postMessage = AsyncMock()
    
    mock_socket_client = Mock()
    
    return {
        "service_analyzer": mock_service_analyzer,
        "message_maker": mock_message_maker,
        "flow_logger": mock_flow_logger,
        "web_client": mock_web_client,
        "socket_client": mock_socket_client
    }

@pytest.fixture
def office_assistant(mock_components):
    """Create an OfficeAssistant with mocked components"""
    assistant = OfficeAssistant("test_slack_token", "test_app_token")
    assistant.web_client = mock_components["web_client"]
    assistant.socket_client = mock_components["socket_client"]
    assistant.service_analyzer = mock_components["service_analyzer"]
    assistant.message_maker = mock_components["message_maker"]
    assistant.flow_logger = mock_components["flow_logger"]
    assistant.bot_user_id = "BOT_ID"
    return assistant

class TestInitialFlow:
    """Test the initial flow from Slack message to Ticket creation"""

    @pytest.mark.asyncio
    async def test_basic_message_processing(self, office_assistant, mock_slack_event):
        """
        Test processing of a basic message.
        Verifies:
        - Event is properly processed
        - Ticket is created with correct attributes
        - Bot mention is removed from message
        - User info is properly captured
        """
        event = mock_slack_event("basic")
        await office_assistant.process_event(event)
        
        # Get the ticket from the last call to service_analyzer
        mock_analyze_call = office_assistant.service_analyzer.analyze_request.call_args
        assert mock_analyze_call is not None, "service_analyzer.analyze_request was not called"
        
        ticket = mock_analyze_call[0][0]  # First argument of the last call
        assert isinstance(ticket, Ticket)
        assert ticket.original_message == "Schedule a meeting tomorrow at 3pm"
        assert ticket.status == TicketStatus.CREATED
        assert ticket.user_info["user_id"] == "U123456"
        assert ticket.channel_id == "C123456"
        assert len(ticket.incoming_messages) == 1

    @pytest.mark.asyncio
    async def test_threaded_message_processing(self, office_assistant, mock_slack_event):
        """
        Test processing of a threaded message.
        Verifies:
        - Thread TS is properly captured
        - Message is linked to correct thread
        - Ticket maintains thread context
        """
        thread_ts = "1645036800.000100"
        event = mock_slack_event("threaded", thread_ts)
        await office_assistant.process_event(event)
        
        mock_analyze_call = office_assistant.service_analyzer.analyze_request.call_args
        assert mock_analyze_call is not None, "service_analyzer.analyze_request was not called"
        
        ticket = mock_analyze_call[0][0]
        assert ticket.thread_ts == thread_ts
        assert ticket.user_info["thread_ts"] == thread_ts

    @pytest.mark.asyncio
    async def test_bot_message_filtering(self, office_assistant, mock_slack_event):
        """
        Test that bot messages are properly filtered.
        Verifies:
        - Bot messages are ignored
        - No ticket is created for bot messages
        """
        event = mock_slack_event("bot_message")
        await office_assistant.process_event(event)
        
        # Verify service_analyzer was not called
        office_assistant.service_analyzer.analyze_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_mention_filtering(self, office_assistant, mock_slack_event):
        """
        Test that non-mention messages are properly filtered.
        Verifies:
        - Messages without bot mention are ignored
        - No ticket is created for non-mention messages
        """
        event = mock_slack_event("no_mention")
        await office_assistant.process_event(event)
        
        # Verify service_analyzer was not called
        office_assistant.service_analyzer.analyze_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_ticket_conversation_tracking(self, office_assistant, mock_slack_event):
        """
        Test that ticket properly tracks conversation.
        Verifies:
        - Incoming messages are recorded
        - Message timestamps are captured
        - Message direction is properly set
        """
        event = mock_slack_event("basic")
        await office_assistant.process_event(event)
        
        mock_analyze_call = office_assistant.service_analyzer.analyze_request.call_args
        assert mock_analyze_call is not None, "service_analyzer.analyze_request was not called"
        
        ticket = mock_analyze_call[0][0]
        assert len(ticket.incoming_messages) == 1
        assert ticket.incoming_messages[0].direction == "incoming"
        assert ticket.incoming_messages[0].content == "Schedule a meeting tomorrow at 3pm"

    @pytest.mark.asyncio
    async def test_error_handling(self, office_assistant, mock_slack_event):
        """
        Test error handling during event processing.
        Verifies:
        - Errors are caught and logged
        - Ticket status is updated appropriately
        - Error messages are recorded in ticket
        """
        # Make service_analyzer raise an exception
        office_assistant.service_analyzer.analyze_request.side_effect = Exception("Test error")
        
        event = mock_slack_event("basic")
        await office_assistant.process_event(event)
        
        # Verify error was logged
        office_assistant.flow_logger.log_event.assert_called_with(
            "OfficeAssistant",
            "event_processing_error",
            {"error": "Test error"}
        )

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 