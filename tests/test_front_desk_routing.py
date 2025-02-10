import pytest
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from src.office.reception.front_desk import FrontDesk

# Set up logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture(autouse=True)
def setup_logging(caplog):
    """Set up logging for all tests."""
    caplog.set_level(logging.INFO)
    
    # Create a handler that logs to the caplog
    class CaplogHandler(logging.Handler):
        def emit(self, record):
            caplog.handler.emit(record)
    
    # Add the handler to all loggers
    root_logger = logging.getLogger()
    handler = CaplogHandler()
    root_logger.addHandler(handler)
    
    yield
    
    # Clean up
    root_logger.removeHandler(handler)

@pytest.fixture
def front_desk(
    mock_slack_web_client,
    mock_slack_socket_client,
    mock_openai_client,
    setup_logging
):
    """Create a FrontDesk instance with mocked dependencies."""
    nlp = MagicMock()
    nlp.process_message = AsyncMock()
    
    cookbook = MagicMock()
    cookbook.find_matching_recipe = AsyncMock()
    
    task_manager = MagicMock()
    task_manager.execute_recipe = AsyncMock()
    
    ceo = MagicMock()
    ceo.consider_request = AsyncMock()
    
    web_client = MagicMock()
    web_client.chat_postMessage = AsyncMock()
    web_client.users_info = AsyncMock(return_value={"user": {"real_name": "Test User"}})
    
    fd = FrontDesk(
        web_client=web_client,
        socket_client=mock_slack_socket_client,
        nlp=nlp,
        cookbook=cookbook,
        task_manager=task_manager,
        ceo=ceo,
        bot_id="U123"
    )
    
    return fd

@pytest.mark.asyncio
async def test_known_task_routing(
    front_desk,
    sample_slack_message,
    sample_nlp_result,
    sample_recipes,
    caplog
):
    """Test that known tasks are routed directly to TaskManager."""
    # Configure mocks for this test
    front_desk.nlp.process_message.return_value = sample_nlp_result
    front_desk.cookbook.find_matching_recipe.return_value = sample_recipes["schedule_meeting"]
    front_desk.task_manager.execute_recipe.return_value = {
        "status": "success",
        "details": "Meeting scheduled successfully"
    }
    front_desk.web_client.chat_postMessage.return_value = {"ok": True}

    # Execute
    await front_desk.handle_message(sample_slack_message)

    # Verify
    assert front_desk.nlp.process_message.call_count == 1
    assert front_desk.cookbook.find_matching_recipe.call_count == 1
    assert front_desk.task_manager.execute_recipe.call_count == 1
    assert "Found existing recipe: Schedule Meeting" in caplog.text

@pytest.mark.asyncio
async def test_unknown_task_routing(
    front_desk,
    sample_slack_message,
    sample_nlp_result,
    caplog
):
    """Test that unknown tasks are routed to CEO."""
    # Configure mocks for this test
    front_desk.nlp.process_message.return_value = sample_nlp_result
    front_desk.cookbook.find_matching_recipe.return_value = None
    front_desk.ceo.consider_request.return_value = {
        "status": "success",
        "decision": "I'll help create a new process for this.",
        "new_recipe": {
            "name": "New Task",
            "intent": "new_task",
            "steps": []
        }
    }
    front_desk.web_client.chat_postMessage.return_value = {"ok": True}

    # Execute
    await front_desk.handle_message(sample_slack_message)

    # Verify
    assert front_desk.nlp.process_message.call_count == 1
    assert front_desk.cookbook.find_matching_recipe.call_count == 1
    assert front_desk.ceo.consider_request.call_count == 1
    assert "No matching recipe found" in caplog.text

@pytest.mark.asyncio
async def test_recipe_matching_with_entities(
    front_desk,
    sample_recipes,
    caplog
):
    """Test that recipe matching considers required entities."""
    # Create test message
    message = {
        "type": "message",
        "channel": "C123",
        "user": "U456",
        "text": "<@U123> schedule a meeting",
        "ts": "1234567890.123"
    }

    # Configure mocks
    nlp_result = {
        "intent": "schedule_meeting",
        "entities": {},  # Missing required entities
        "keywords": ["schedule", "meeting"],
        "urgency": 0.3
    }

    front_desk.nlp.process_message.return_value = nlp_result
    front_desk.cookbook.find_matching_recipe.return_value = None
    front_desk.ceo.consider_request.return_value = {
        "status": "success",
        "decision": "I need more information to schedule the meeting."
    }
    front_desk.web_client.chat_postMessage.return_value = {"ok": True}

    # Execute
    await front_desk.handle_message(message)

    # Verify
    assert front_desk.cookbook.find_matching_recipe.call_count == 1
    assert front_desk.ceo.consider_request.call_count == 1
    assert "No matching recipe found" in caplog.text

@pytest.mark.asyncio
async def test_error_handling(
    front_desk,
    sample_slack_message,
    sample_nlp_result,
    sample_recipes,
    caplog
):
    """Test error handling during task execution."""
    # Configure mocks
    front_desk.nlp.process_message.return_value = sample_nlp_result
    front_desk.cookbook.find_matching_recipe.return_value = sample_recipes["schedule_meeting"]
    front_desk.task_manager.execute_recipe.return_value = {
        "status": "error",
        "error": "Failed to schedule meeting: Calendar API unavailable"
    }
    front_desk.web_client.chat_postMessage.return_value = {"ok": True}

    # Execute
    await front_desk.handle_message(sample_slack_message)

    # Verify
    assert front_desk.task_manager.execute_recipe.call_count == 1
    assert "Error: Failed to schedule meeting" in caplog.text 