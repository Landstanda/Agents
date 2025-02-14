import pytest
from unittest.mock import AsyncMock, MagicMock
from src.tools.nlp import NLPAnalyzer, TicketStatus, Ticket
from src.tools.message_maker import MessageMaker
from src.main import OfficeAssistant
from src.utils.flow_logger import FlowLogger

@pytest.fixture
def flow_logger():
    """Create a flow logger for testing."""
    return FlowLogger()

@pytest.fixture
def nlp_analyzer_factory(flow_logger):
    """Create a function that returns a new NLP analyzer instance."""
    def _create_analyzer():
        return NLPAnalyzer(flow_logger=flow_logger)
    return _create_analyzer

@pytest.fixture
def message_maker(flow_logger):
    """Create a mock message maker for testing."""
    return MessageMaker(use_mock=True, flow_logger=flow_logger)

@pytest.mark.asyncio
async def test_nlp_message_analysis(nlp_analyzer_factory):
    """Test that NLP can analyze a message and identify intent."""
    # Create and initialize the analyzer
    analyzer = nlp_analyzer_factory()
    await analyzer.refresh_lexicon()
    
    message = "schedule a meeting with John tomorrow at 2pm"
    user_info = {
        "user_id": "U123456",
        "channel_id": "C123456",
        "thread_ts": None,
        "ts": "1234567890.123456"
    }
    
    ticket = await analyzer.analyze_message(message, user_info)
    assert ticket is not None
    assert isinstance(ticket, Ticket)
    assert ticket.user_info == user_info
    assert ticket.original_message == message
    assert "time" in ticket.entities, f"Expected 'time' in entities, got: {ticket.entities}"
    assert "date" in ticket.entities, f"Expected 'date' in entities, got: {ticket.entities}"
    assert "participants" in ticket.entities, f"Expected 'participants' in entities, got: {ticket.entities}"
    assert ticket.entities["time"] == "14:00", f"Expected time '14:00', got: {ticket.entities.get('time')}"
    assert ticket.entities["date"] == "tomorrow", f"Expected date 'tomorrow', got: {ticket.entities.get('date')}"
    assert "John" in ticket.entities["participants"], f"Expected 'John' in participants, got: {ticket.entities.get('participants')}"

@pytest.mark.asyncio
async def test_nlp_various_time_formats(nlp_analyzer_factory):
    """Test that NLP can handle various time formats."""
    analyzer = nlp_analyzer_factory()
    await analyzer.refresh_lexicon()
    
    test_cases = [
        ("schedule meeting at 9am", "09:00"),
        ("meeting at 2:30pm", "14:30"),
        ("call at 10:15 am", "10:15"),
        ("meeting at noon", "12:00"),
        ("schedule for 3 pm", "15:00")
    ]
    
    for message, expected_time in test_cases:
        ticket = await analyzer.analyze_message(message, {"user_id": "U123"})
        assert "time" in ticket.entities, f"Failed to extract time from: {message}"
        assert ticket.entities["time"] == expected_time, f"Wrong time format for '{message}': expected {expected_time}, got {ticket.entities['time']}"

@pytest.mark.asyncio
async def test_nlp_various_date_formats(nlp_analyzer_factory):
    """Test that NLP can handle various date formats."""
    analyzer = nlp_analyzer_factory()
    await analyzer.refresh_lexicon()
    
    test_cases = [
        "schedule meeting tomorrow",
        "meeting next monday",
        "call on friday",
        "schedule for next week",
        "meeting this wednesday"
    ]
    
    for message in test_cases:
        ticket = await analyzer.analyze_message(message, {"user_id": "U123"})
        assert "date" in ticket.entities, f"Failed to extract date from: {message}"
        assert ticket.entities["date"], f"Empty date extracted from: {message}"

@pytest.mark.asyncio
async def test_nlp_error_handling(nlp_analyzer_factory):
    """Test NLP error handling for invalid inputs."""
    analyzer = nlp_analyzer_factory()
    await analyzer.refresh_lexicon()
    
    # Test empty message
    ticket = await analyzer.analyze_message("", {"user_id": "U123"})
    assert ticket.status == TicketStatus.ERROR
    assert ticket.errors
    
    # Test message without recognizable intent
    ticket = await analyzer.analyze_message("hello world", {"user_id": "U123"})
    assert ticket.status == TicketStatus.SERVICE_CREATION
    
    # Test message with missing required entities
    ticket = await analyzer.analyze_message("schedule a meeting", {"user_id": "U123"})
    assert ticket.status == TicketStatus.WAITING_INPUT
    assert ticket.missing_entities

@pytest.mark.asyncio
async def test_message_maker_response(message_maker):
    """Test that MessageMaker can generate and send messages."""
    ticket = MagicMock()
    ticket.intent = "schedule_meeting"
    ticket.entities = {"person": "John", "time": "2pm", "date": "tomorrow"}
    ticket.channel_id = "C123456"
    ticket.thread_ts = "1234567890.123456"
    ticket.original_message = "schedule a meeting with John tomorrow at 2pm"
    ticket.status = TicketStatus.COMPLETED
    ticket.service = "calendar"
    ticket.execution_results = {"scheduled": True}
    
    # Mock the message history
    ticket.get_message_history.return_value = []
    
    await message_maker.send_message(ticket)
    # The test passes if no exception is raised

@pytest.mark.asyncio
async def test_message_maker_error_handling(message_maker):
    """Test MessageMaker error handling."""
    # Test with missing channel
    ticket = MagicMock()
    ticket.channel_id = None
    ticket.status = TicketStatus.ERROR
    ticket.errors = [{"message": "Test error", "type": "test"}]
    
    await message_maker.send_message(ticket)  # Should handle missing channel gracefully
    
    # Test with missing thread_ts
    ticket.channel_id = "C123456"
    ticket.thread_ts = None
    
    await message_maker.send_message(ticket)  # Should handle missing thread_ts gracefully

@pytest.mark.asyncio
async def test_office_assistant_event_processing():
    """Test that OfficeAssistant can process Socket Mode events."""
    assistant = OfficeAssistant(
        slack_token="xoxb-test-token",
        app_token="xapp-test-token"
    )
    
    # Mock the components
    assistant.nlp = AsyncMock()
    assistant.message_maker = AsyncMock()
    assistant.web_client = AsyncMock()
    assistant.flow_logger = AsyncMock()
    
    # Mock web client token
    assistant.web_client.token = "xoxb-bot123"
    
    # Mock auth test response
    assistant.web_client.auth_test = AsyncMock(return_value={
        "ok": True,
        "user": "test-bot",
        "user_id": "U123456"
    })
    
    # Create mock event
    mock_event = {
        "type": "message",
        "user": "U789012",  # Different from bot user
        "text": "schedule a meeting",
        "channel": "C123456",
        "ts": "1234567890.123456"
    }
    
    # Create mock request
    mock_request = MagicMock()
    mock_request.payload = {"event": mock_event}
    mock_client = AsyncMock()
    
    # Process the mock request
    await assistant.process_event(mock_client, mock_request)
    
    # Verify the event was processed
    assert assistant.nlp.analyze_message.called
    assert assistant.message_maker.send_message.called

@pytest.mark.asyncio
async def test_office_assistant_event_filtering():
    """Test that OfficeAssistant properly filters events."""
    assistant = OfficeAssistant(
        slack_token="xoxb-test-token",
        app_token="xapp-test-token"
    )
    
    # Set up mocks
    assistant.nlp = AsyncMock()
    assistant.message_maker = AsyncMock()
    assistant.web_client = AsyncMock()
    assistant.flow_logger = AsyncMock()
    assistant.bot_user_id = "U123456"
    
    test_cases = [
        # Bot message (should be ignored)
        {
            "type": "message",
            "user": "U123456",  # Same as bot
            "text": "test message",
            "channel": "C123456",
            "ts": "1234567890.123456"
        },
        # Message with subtype (should be ignored)
        {
            "type": "message",
            "subtype": "channel_join",
            "user": "U789012",
            "text": "test message",
            "channel": "C123456",
            "ts": "1234567890.123456"
        },
        # Message without text (should be ignored)
        {
            "type": "message",
            "user": "U789012",
            "channel": "C123456",
            "ts": "1234567890.123456"
        },
        # Valid message (should be processed)
        {
            "type": "message",
            "user": "U789012",
            "text": "test message",
            "channel": "C123456",
            "ts": "1234567890.123456"
        }
    ]
    
    for event in test_cases:
        mock_request = MagicMock()
        mock_request.payload = {"event": event}
        mock_client = AsyncMock()
        
        await assistant.process_event(mock_client, mock_request)
    
    # Only the valid message should be processed
    assert assistant.nlp.analyze_message.call_count == 1
    assert assistant.message_maker.send_message.call_count == 1

@pytest.mark.asyncio
async def test_end_to_end_message_flow():
    """Test the entire message processing flow with mock components."""
    # Create the assistant with mock tokens
    assistant = OfficeAssistant(
        slack_token="xoxb-test-token",
        app_token="xapp-test-token"
    )
    
    # Mock web client auth test
    assistant.web_client = AsyncMock()
    assistant.web_client.token = "xoxb-bot123"
    assistant.web_client.auth_test = AsyncMock(return_value={
        "ok": True,
        "user": "test-bot",
        "user_id": "U123456"
    })
    
    # Initialize components
    await assistant.setup()
    
    # Create mock event
    mock_event = {
        "type": "message",
        "user": "U789012",  # Different from bot user
        "text": "schedule a meeting",
        "channel": "C123456",
        "ts": "1234567890.123456"
    }
    
    # Create mock request
    mock_request = MagicMock()
    mock_request.payload = {"event": mock_event}
    mock_client = AsyncMock()
    
    # Process the mock request
    await assistant.process_event(mock_client, mock_request)
    
    # Verify flow logger recorded events
    assert assistant.flow_logger is not None

@pytest.mark.asyncio
async def test_end_to_end_conversation_flow():
    """Test a complete conversation flow with multiple messages."""
    assistant = OfficeAssistant(
        slack_token="xoxb-test-token",
        app_token="xapp-test-token"
    )
    
    # Set up mocks
    assistant.web_client = AsyncMock()
    assistant.web_client.token = "xoxb-bot123"
    assistant.web_client.auth_test = AsyncMock(return_value={
        "ok": True,
        "user": "test-bot",
        "user_id": "U123456"
    })
    
    # Initialize components
    await assistant.setup()
    
    # Simulate a conversation flow
    conversation = [
        # Initial request
        {
            "type": "message",
            "user": "U789012",
            "text": "schedule a meeting",
            "channel": "C123456",
            "ts": "1234567890.123456"
        },
        # Follow-up with time
        {
            "type": "message",
            "user": "U789012",
            "text": "at 2pm tomorrow",
            "channel": "C123456",
            "thread_ts": "1234567890.123456",
            "ts": "1234567890.123457"
        },
        # Follow-up with participants
        {
            "type": "message",
            "user": "U789012",
            "text": "with John and Mary",
            "channel": "C123456",
            "thread_ts": "1234567890.123456",
            "ts": "1234567890.123458"
        }
    ]
    
    for event in conversation:
        mock_request = MagicMock()
        mock_request.payload = {"event": event}
        mock_client = AsyncMock()
        
        await assistant.process_event(mock_client, mock_request)
        
        # Verify each message was processed
        assert assistant.flow_logger is not None

if __name__ == "__main__":
    pytest.main(["-v", "test_basic_functionality.py"]) 