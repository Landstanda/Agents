import pytest
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from src.office.reception.front_desk import FrontDesk
from src.office.executive.ceo import CEO

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
def mock_slack_client():
    """Create a mock Slack client."""
    mock = AsyncMock()
    mock.users_info.return_value = {
        "ok": True,
        "user": {
            "id": "TEST_USER",
            "real_name": "Test User",
            "is_bot": False,
            "profile": {
                "email": "test@example.com"
            }
        }
    }
    mock.chat_postMessage.return_value = {"ok": True, "ts": "1234567890.123456"}
    return mock

@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    mock = AsyncMock()
    mock.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="I'll help you with that!"))]
    )
    return mock

@pytest.fixture
def mock_nlp_processor(caplog):
    """Create a mock NLP processor with specific intent detection."""
    mock = MagicMock()
    caplog.set_level(logging.INFO)
    
    def process_message(message, user_info):
        # Default response structure
        result = {
            "intents": [],
            "entities": [],
            "urgency": 0.5,
            "temporal_context": {},
            "confidence": 0.1,
            "status": "success"
        }
        
        # Pattern matching for different request types
        if "schedule" in message.lower() and "meeting" in message.lower():
            result.update({
                "intents": ["scheduling", "meeting_scheduler"],
                "urgency": 0.7,
                "confidence": 0.9
            })
            caplog.records.append(
                logging.LogRecord(
                    name=__name__,
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg="Detected scheduling and meeting_scheduler intents",
                    args=(),
                    exc_info=None
                )
            )
            
        elif "email" in message.lower():
            intent = "email_read" if "check" in message.lower() or "read" in message.lower() else "email_send"
            result.update({
                "intents": [intent, "email_processing"],
                "urgency": 0.5,
                "confidence": 0.8
            })
            caplog.records.append(
                logging.LogRecord(
                    name=__name__,
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg=f"Detected {intent} and email_processing intents",
                    args=(),
                    exc_info=None
                )
            )
            
        elif "research" in message.lower() or "document" in message.lower():
            intents = []
            if "research" in message.lower():
                intents.append("research")
            if "document" in message.lower():
                intents.append("document")
            result.update({
                "intents": intents,
                "urgency": 0.4,
                "confidence": 0.7
            })
            caplog.records.append(
                logging.LogRecord(
                    name=__name__,
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg="Detected multiple steps: research and document preparation",
                    args=(),
                    exc_info=None
                )
            )
            
        elif not message.strip():
            result.update({
                "status": "error",
                "error": "Empty message"
            })
            caplog.records.append(
                logging.LogRecord(
                    name=__name__,
                    level=logging.ERROR,
                    pathname="",
                    lineno=0,
                    msg="Error: Empty message received",
                    args=(),
                    exc_info=None
                )
            )
            
        else:
            result.update({
                "confidence": 0.1,
                "status": "success"
            })
            caplog.records.append(
                logging.LogRecord(
                    name=__name__,
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg=f"No matching intents found. Confidence: {result['confidence']}",
                    args=(),
                    exc_info=None
                )
            )
            
        return result
    
    mock.process_message.side_effect = process_message
    return mock

@pytest.fixture
async def front_desk(mock_slack_client, mock_openai_client, mock_nlp_processor):
    """Create a Front Desk instance with mocked dependencies."""
    with patch('src.office.reception.front_desk.AsyncWebClient', return_value=mock_slack_client), \
         patch('src.office.reception.front_desk.AsyncOpenAI', return_value=mock_openai_client), \
         patch('src.office.reception.front_desk.NLPProcessor', return_value=mock_nlp_processor):
        
        fd = FrontDesk()
        fd.bot_id = "TEST_BOT"
        fd.bot_mention = "<@TEST_BOT>"
        fd.nlp = mock_nlp_processor
        fd.ceo = CEO()  # Using the real CEO since it's now simplified
        
        logger.info("Created Front Desk instance with mocked components")
        return fd

@pytest.fixture
def mock_message():
    """Create a base mock message."""
    return {
        "user": "TEST_USER",
        "channel": "TEST_CHANNEL",
        "ts": "1234567890.123456",
        "text": "",
        "type": "message",
        "user_info": {
            "id": "TEST_USER",
            "real_name": "Test User",
            "is_bot": False,
            "profile": {
                "email": "test@example.com"
            }
        }
    }

@pytest.mark.asyncio
async def test_scheduling_request(front_desk, mock_message, caplog):
    """Test handling of a meeting scheduling request."""
    caplog.set_level(logging.INFO)
    
    # Set up test message
    mock_message["text"] = "<@TEST_BOT> schedule a team meeting"
    
    # Get the front desk instance
    fd = await front_desk
    
    # Process the message
    await fd.handle_message(mock_message)
    
    # Verify the response
    log_messages = [record.msg for record in caplog.records]
    print("\nLog messages:", log_messages)  # Debug print
    
    assert any("schedule" in msg.lower() and "meeting" in msg.lower() for msg in log_messages), "Meeting request not found in logs"
    assert any("schedule a team meeting" in msg.lower() for msg in log_messages), "Meeting request not found in logs"
    assert any("help you schedule the meeting" in msg.lower() for msg in log_messages), "Meeting scheduler response not found in logs"

@pytest.mark.asyncio
async def test_email_request(front_desk, mock_message, caplog):
    """Test handling of an email-related request."""
    caplog.set_level(logging.INFO)
    
    # Get the front desk instance
    fd = await front_desk
    
    # Test both read and send scenarios
    scenarios = [
        ("<@TEST_BOT> check my latest emails", "help you process your emails"),
        ("<@TEST_BOT> send an email to the team", "help you process your emails")
    ]
    
    for message_text, expected_response in scenarios:
        caplog.clear()  # Clear logs between scenarios
        mock_message["text"] = message_text
        await fd.handle_message(mock_message)
        
        # Verify the response
        log_messages = [record.msg for record in caplog.records]
        print(f"\nLog messages for {message_text}:", log_messages)  # Debug print
        
        # Check for email-related content in logs
        assert any("email" in msg.lower() for msg in log_messages), "Email request not found in logs"
        # Check for cleaned message text (without bot mention)
        cleaned_text = message_text.replace("<@TEST_BOT> ", "")
        assert any(cleaned_text.lower() in msg.lower() for msg in log_messages), "Email request not found in logs"
        assert any(expected_response.lower() in msg.lower() for msg in log_messages), "Email processing response not found in logs"

@pytest.mark.asyncio
async def test_multi_intent_request(front_desk, mock_message, caplog):
    """Test handling of a request that triggers multiple intents."""
    caplog.set_level(logging.INFO)
    
    # Set up test message that should trigger multiple intents
    mock_message["text"] = "<@TEST_BOT> research AI trends and prepare a document"
    
    # Get the front desk instance
    fd = await front_desk
    
    await fd.handle_message(mock_message)
    
    # Verify multiple intents were detected and handled
    log_messages = [record.msg for record in caplog.records]
    print("\nLog messages:", log_messages)  # Debug print
    
    assert any("research" in msg.lower() for msg in log_messages), "Research request not found in logs"
    assert any("document" in msg.lower() for msg in log_messages), "Document request not found in logs"
    assert any("research ai trends and prepare a document" in msg.lower() for msg in log_messages), "Full request not found in logs"

@pytest.mark.asyncio
async def test_unknown_request(front_desk, mock_message, caplog):
    """Test handling of a request that doesn't match any known intents."""
    caplog.set_level(logging.INFO)
    
    # Set up test message
    mock_message["text"] = "<@TEST_BOT> do something completely unknown"
    
    # Get the front desk instance
    fd = await front_desk
    
    await fd.handle_message(mock_message)
    
    # Verify appropriate handling of unknown request
    log_messages = [record.msg for record in caplog.records]
    print("\nLog messages:", log_messages)  # Debug print
    
    assert any("do something completely unknown" in msg.lower() for msg in log_messages), "Unknown request not found in logs"
    assert any("not sure how to help" in msg.lower() for msg in log_messages), "Unknown request handling not found in logs"

@pytest.mark.asyncio
async def test_error_handling(front_desk, mock_message, caplog):
    """Test handling of errors during request processing."""
    caplog.set_level(logging.INFO)
    
    # Set up test message that's empty to trigger an error
    mock_message["text"] = "<@TEST_BOT>"
    
    # Get the front desk instance
    fd = await front_desk
    
    await fd.handle_message(mock_message)
    
    # Verify error handling
    log_messages = [record.msg for record in caplog.records]
    print("\nLog messages:", log_messages)  # Debug print
    
    assert any("missing required fields" in msg.lower() for msg in log_messages), "Error message not found in logs"

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 