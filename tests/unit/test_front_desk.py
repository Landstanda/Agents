import pytest
from unittest.mock import MagicMock, AsyncMock
from src.office.reception.front_desk import FrontDesk
import json

@pytest.fixture
def mock_slack_clients(monkeypatch):
    """Mock Slack clients for testing."""
    # Mock WebClient
    mock_web = MagicMock()
    mock_web.users_info.return_value = {
        "user": {
            "id": "U123",
            "real_name": "Test User",
            "is_dm": True
        }
    }
    
    # Mock SocketModeClient
    mock_socket = MagicMock()
    mock_socket.connect = MagicMock()
    
    def mock_init(self):
        self.web_client = mock_web
        self.socket_client = mock_socket
        self.ceo = MagicMock()
        self.nlp = MagicMock()
        self.name = "Sarah"
        self.title = "Front Desk Manager"
    
    monkeypatch.setattr(FrontDesk, "__init__", mock_init)
    return mock_web, mock_socket

@pytest.mark.asyncio
async def test_handle_simple_message(mock_slack_clients):
    """Test handling a simple message with NLP processing."""
    web_client, _ = mock_slack_clients
    front_desk = FrontDesk()
    
    # Mock NLP response
    mock_nlp_response = {
        "status": "success",
        "intents": ["communication"],
        "entities": {"emails": []},
        "urgency": 0.3,
        "temporal_context": {
            "has_deadline": False,
            "timeframe": None,
            "specific_day": None
        },
        "user_context": {
            "user_id": "U123",
            "user_name": "Test User",
            "is_dm": True
        }
    }
    front_desk.nlp.process_message.return_value = mock_nlp_response
    
    # Mock CEO response
    mock_response = {
        "status": "success",
        "decision": "I'll check your emails right away.",
        "confidence": 0.9,
        "requires_consultation": False,
        "matched_recipes": [
            {"name": "Email Processing"}
        ],
        "notes": "Processing emails now"
    }
    front_desk.ceo.consider_request = AsyncMock(return_value=mock_response)
    
    # Test message handling
    message = {
        "user": "U123",
        "channel": "C123",
        "text": "Can you check my emails?",
        "ts": "123.456"
    }
    
    await front_desk.handle_message(message)
    
    # Verify NLP processing was called
    front_desk.nlp.process_message.assert_called_once()
    
    # Verify CEO was called with context
    front_desk.ceo.consider_request.assert_called_once()
    call_args = front_desk.ceo.consider_request.call_args[1]
    assert "nlp_analysis" in call_args["context"]
    
    # Verify Slack message was sent
    web_client.chat_postMessage.assert_called_once()
    call_args = web_client.chat_postMessage.call_args[1]
    assert call_args["channel"] == "C123"
    assert "Test User" in call_args["text"]
    assert "Email Processing" in call_args["text"]

@pytest.mark.asyncio
async def test_handle_urgent_message(mock_slack_clients):
    """Test handling an urgent message."""
    web_client, _ = mock_slack_clients
    front_desk = FrontDesk()
    
    # Mock NLP response for urgent message
    mock_nlp_response = {
        "status": "success",
        "intents": ["document"],
        "entities": {},
        "urgency": 0.9,
        "temporal_context": {
            "has_deadline": True,
            "timeframe": "urgent",
            "specific_day": None
        },
        "user_context": {
            "user_id": "U123",
            "user_name": "Test User",
            "is_dm": True
        }
    }
    front_desk.nlp.process_message.return_value = mock_nlp_response
    
    # Mock CEO response
    mock_response = {
        "status": "success",
        "decision": "I'll prepare the report immediately.",
        "confidence": 0.9,
        "requires_consultation": False,
        "matched_recipes": [
            {"name": "Document Processing"}
        ],
        "notes": "Working on it urgently"
    }
    front_desk.ceo.consider_request = AsyncMock(return_value=mock_response)
    
    # Test message handling
    message = {
        "user": "U123",
        "channel": "C123",
        "text": "URGENT: Need the quarterly report ASAP!",
        "ts": "123.456"
    }
    
    await front_desk.handle_message(message)
    
    # Verify response includes urgency indicators
    web_client.chat_postMessage.assert_called_once()
    call_args = web_client.chat_postMessage.call_args[1]
    assert "urgent matter" in call_args["text"].lower()
    assert "as soon as possible" in call_args["text"].lower()

@pytest.mark.asyncio
async def test_handle_scheduled_message(mock_slack_clients):
    """Test handling a message with specific timing."""
    web_client, _ = mock_slack_clients
    front_desk = FrontDesk()
    
    # Mock NLP response for scheduled message
    mock_nlp_response = {
        "status": "success",
        "intents": ["scheduling"],
        "entities": {},
        "urgency": 0.3,
        "temporal_context": {
            "has_deadline": True,
            "timeframe": None,
            "specific_day": "tuesday"
        },
        "user_context": {
            "user_id": "U123",
            "user_name": "Test User",
            "is_dm": True
        }
    }
    front_desk.nlp.process_message.return_value = mock_nlp_response
    
    # Mock CEO response
    mock_response = {
        "status": "success",
        "decision": "I'll schedule the meeting.",
        "confidence": 0.9,
        "requires_consultation": False,
        "matched_recipes": [
            {"name": "Meeting Scheduler"}
        ],
        "notes": "Checking availability"
    }
    front_desk.ceo.consider_request = AsyncMock(return_value=mock_response)
    
    # Test message handling
    message = {
        "user": "U123",
        "channel": "C123",
        "text": "Schedule a team meeting for Tuesday",
        "ts": "123.456"
    }
    
    await front_desk.handle_message(message)
    
    # Verify response includes timing information
    web_client.chat_postMessage.assert_called_once()
    call_args = web_client.chat_postMessage.call_args[1]
    assert "tuesday" in call_args["text"].lower()

@pytest.mark.asyncio
async def test_nlp_error_handling(mock_slack_clients):
    """Test handling NLP processing errors."""
    web_client, _ = mock_slack_clients
    front_desk = FrontDesk()
    
    # Mock NLP error
    front_desk.nlp.process_message.return_value = {
        "status": "error",
        "error": "NLP processing failed"
    }
    
    # Test message handling
    message = {
        "user": "U123",
        "channel": "C123",
        "text": "This will cause an NLP error",
        "ts": "123.456"
    }
    
    await front_desk.handle_message(message)
    
    # Verify error message was sent
    web_client.chat_postMessage.assert_called_once()
    call_args = web_client.chat_postMessage.call_args[1]
    assert "error" in call_args["text"].lower()
    assert "apologize" in call_args["text"].lower()

@pytest.mark.asyncio
async def test_socket_mode_request(mock_slack_clients):
    """Test processing a socket mode request."""
    _, socket_client = mock_slack_clients
    front_desk = FrontDesk()
    
    # Create mock request
    mock_request = MagicMock()
    mock_request.type = "events_api"
    mock_request.envelope_id = "123"
    mock_request.payload = {
        "event": {
            "type": "message",
            "user": "U123",
            "channel": "C123",
            "text": "Hello",
            "ts": "123.456"
        }
    }
    
    # Mock the async methods
    socket_client.send_socket_mode_response = AsyncMock()
    front_desk.handle_message = AsyncMock()
    
    # Process the request
    await front_desk.process_socket_request(socket_client, mock_request)
    
    # Verify socket response was sent
    socket_client.send_socket_mode_response.assert_called_once()
    response_arg = socket_client.send_socket_mode_response.call_args[0][0]
    assert response_arg.envelope_id == "123"
    
    # Verify handle_message was called with the event
    front_desk.handle_message.assert_called_once_with(mock_request.payload["event"]) 