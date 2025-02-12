import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.office.reception.front_desk import FrontDesk
from src.office.reception.nlp_processor import NLPProcessor
from src.office.cookbook.cookbook_manager import CookbookManager
from src.office.task.task_manager import TaskManager
from src.office.executive.ceo import CEO

@pytest.fixture
async def setup_components():
    """Set up test components with mocked Slack clients."""
    # Mock Slack clients
    web_client = MagicMock()
    socket_client = MagicMock()
    
    # Configure async mock methods
    async def mock_chat_post(*args, **kwargs):
        return {"ok": True, "ts": "123.456"}
    
    async def mock_users_info(*args, **kwargs):
        return {
            "ok": True,
            "user": {
                "id": "U123",
                "real_name": "Test User",
                "is_bot": False
            }
        }
    
    web_client.chat_postMessage.side_effect = mock_chat_post
    web_client.users_info.side_effect = mock_users_info
    
    # Create real components
    nlp = NLPProcessor()
    cookbook = CookbookManager()
    task_manager = TaskManager()
    ceo = CEO(cookbook_manager=cookbook, task_manager=task_manager)
    
    # Create front desk with mocked clients
    front_desk = FrontDesk(
        web_client=web_client,
        socket_client=socket_client,
        nlp=nlp,
        cookbook=cookbook,
        task_manager=task_manager,
        ceo=ceo
    )
    
    return {
        "front_desk": front_desk,
        "nlp": nlp,
        "cookbook": cookbook,
        "task_manager": task_manager,
        "ceo": ceo,
        "web_client": web_client
    }

@pytest.mark.asyncio
async def test_conversational_message_handling(setup_components):
    """Test handling of conversational messages."""
    components = await setup_components
    front_desk = components["front_desk"]
    web_client = components["web_client"]
    
    # Test greeting
    message = {
        "channel": "C123",
        "user": "U123",
        "text": "Hi there!",
        "ts": "123.456"
    }
    
    await front_desk.handle_message(message)
    
    # Verify no request was created and GPT response was sent
    assert web_client.chat_postMessage.called
    call_args = web_client.chat_postMessage.call_args[1]
    assert call_args["channel"] == "C123"
    assert isinstance(call_args["text"], str)
    assert len(front_desk.request_tracker.active_requests) == 0

@pytest.mark.asyncio
async def test_task_message_handling(setup_components):
    """Test handling of task-related messages."""
    components = await setup_components
    front_desk = components["front_desk"]
    web_client = components["web_client"]
    
    # Test meeting scheduling request
    message = {
        "channel": "C123",
        "user": "U123",
        "text": "schedule a meeting with Bob tomorrow at 2pm",
        "ts": "123.456"
    }
    
    await front_desk.handle_message(message)
    
    # Verify request was created
    assert len(front_desk.request_tracker.active_requests) == 1
    request = front_desk.request_tracker.get_active_request("C123", "U123")
    assert request is not None
    assert request.intent == "schedule_meeting"
    
    # Verify entities were extracted
    assert "participants" in request.entities
    assert "time" in request.entities
    assert "Bob" in request.entities["participants"]

@pytest.mark.asyncio
async def test_followup_response_handling(setup_components):
    """Test handling of follow-up responses to requests waiting for info."""
    components = await setup_components
    front_desk = components["front_desk"]
    web_client = components["web_client"]
    
    # First message missing some info
    message1 = {
        "channel": "C123",
        "user": "U123",
        "text": "schedule a meeting tomorrow",
        "ts": "123.456"
    }
    
    await front_desk.handle_message(message1)
    
    # Verify request was created and waiting for info
    request = front_desk.request_tracker.get_active_request("C123", "U123")
    assert request is not None
    assert request.status == "waiting_for_info"
    
    # Follow-up message with missing info
    message2 = {
        "channel": "C123",
        "user": "U123",
        "text": "with Bob at 2pm",
        "ts": "123.457"
    }
    
    web_client.chat_postMessage.reset_mock()
    await front_desk.handle_message(message2)
    
    # Verify request was updated with new info
    request = front_desk.request_tracker.get_active_request("C123", "U123")
    assert "participants" in request.entities
    assert "time" in request.entities
    assert "Bob" in request.entities["participants"]

@pytest.mark.asyncio
async def test_unknown_intent_handling(setup_components):
    """Test handling of messages with unknown intents."""
    components = await setup_components
    front_desk = components["front_desk"]
    web_client = components["web_client"]
    
    message = {
        "channel": "C123",
        "user": "U123",
        "text": "what is the meaning of life?",
        "ts": "123.456"
    }
    
    await front_desk.handle_message(message)
    
    # Verify no request was created and GPT response was sent
    assert web_client.chat_postMessage.called
    call_args = web_client.chat_postMessage.call_args[1]
    assert call_args["channel"] == "C123"
    assert isinstance(call_args["text"], str)
    assert len(front_desk.request_tracker.active_requests) == 0

@pytest.mark.asyncio
async def test_error_handling(setup_components):
    """Test handling of errors during message processing."""
    components = await setup_components
    front_desk = components["front_desk"]
    web_client = components["web_client"]
    
    # Force an error by providing invalid message format
    message = {
        "channel": "C123",
        "user": "U123",
        "text": None,  # This should cause an error
        "ts": "123.456"
    }
    
    await front_desk.handle_message(message)
    
    # Verify error message was sent
    assert web_client.chat_postMessage.called
    call_args = web_client.chat_postMessage.call_args[1]
    assert call_args["channel"] == "C123"
    assert "error" in call_args["text"].lower() or "apologize" in call_args["text"].lower()

@pytest.mark.asyncio
async def test_nlp_intent_classification(setup_components):
    """Test NLP processor's intent classification."""
    components = await setup_components
    nlp = components["nlp"]
    
    # Test conversational intents
    result = await nlp.process_message("hello there", {"id": "U123", "real_name": "Test User"})
    assert result["intent_type"] == "conversational"
    assert result["intent"] == "greeting"
    assert result["confidence"] >= 0.9
    
    # Test task intents
    result = await nlp.process_message("schedule a meeting", {"id": "U123", "real_name": "Test User"})
    assert result["intent_type"] == "task"
    assert result["intent"] == "schedule_meeting"
    assert result["confidence"] >= 0.7
    
    # Test unknown intent
    result = await nlp.process_message("random text", {"id": "U123", "real_name": "Test User"})
    assert result["intent"] is None or result["confidence"] < 0.5

@pytest.mark.asyncio
async def test_entity_extraction(setup_components):
    """Test entity extraction from messages."""
    components = await setup_components
    nlp = components["nlp"]
    
    # Test time and participant extraction
    result = await nlp.process_message(
        "schedule meeting with Bob and Alice tomorrow at 2pm",
        {"id": "U123", "real_name": "Test User"}
    )
    
    assert "participants" in result["entities"]
    assert len(result["entities"]["participants"]) == 2
    assert "Bob" in result["entities"]["participants"]
    assert "Alice" in result["entities"]["participants"]
    assert "time" in result["entities"]
    assert result["entities"]["time"] == "14:00"  # Check machine-processable time
    assert "display_time" in result["entities"]
    assert "tomorrow at 2" in result["entities"]["display_time"]  # Check display time contains the core time
    assert "pm" in result["entities"]["display_time"].lower()  # Check it has PM indicator
    
    # Test different time formats
    time_tests = [
        ("schedule meeting at 3pm", "15:00", "3:00pm"),
        ("schedule meeting tomorrow morning", "morning", "morning"),
        ("schedule meeting at 11am", "11:00", "11:00am"),
        ("schedule meeting for 2:30pm", "14:30", "2:30pm"),
        ("schedule meeting today afternoon", "afternoon", "afternoon")
    ]
    
    for test_text, expected_time, expected_display in time_tests:
        result = await nlp.process_message(test_text, {"id": "U123", "real_name": "Test User"})
        assert result["entities"]["time"] is not None, f"Failed to extract time from: {test_text}"
        assert result["entities"]["time"] == expected_time, f"Wrong time format for: {test_text}"
        assert result["entities"]["display_time"] == expected_display, f"Wrong display time for: {test_text}"
    
    # Test email extraction
    result = await nlp.process_message(
        "send email to test@example.com",
        {"id": "U123", "real_name": "Test User"}
    )
    
    assert "emails" in result["entities"]
    assert "test@example.com" in result["entities"]["emails"]

@pytest.mark.asyncio
async def test_conversation_state_management(setup_components):
    """Test conversation state management across multiple messages."""
    components = await setup_components
    nlp = components["nlp"]
    
    channel_id = "C123"
    user_info = {"id": "U123", "real_name": "Test User"}
    
    # First message
    result1 = await nlp.process_message("schedule a meeting", user_info, channel_id)
    assert result1["intent"] == "schedule_meeting"
    
    # Follow-up message
    result2 = await nlp.process_message("with Bob", user_info, channel_id)
    assert "participants" in result2["entities"]
    assert "Bob" in result2["entities"]["participants"]
    
    # Verify state is maintained
    state = nlp._get_conversation_state(channel_id)
    assert state is not None
    assert state["last_intent"] == "schedule_meeting" 