import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock, PropertyMock
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from src.main import OfficeAssistant
from src.core.orchestrator import RequestOrchestrator
from src.utils.flow_logger import FlowLogger

@pytest.fixture
def slack_token():
    return "xoxb-test-token"

@pytest.fixture
def app_token():
    return "xapp-test-token"

@pytest.fixture
def web_client():
    client = AsyncMock(spec=AsyncWebClient)
    client.auth_test = AsyncMock(return_value={"user_id": "U123BOT"})
    client.ssl = None
    return client

@pytest.fixture
def socket_client():
    client = AsyncMock(spec=SocketModeClient)
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.send_socket_mode_response = AsyncMock()
    client.socket_mode_request_listeners = []
    
    # Mock the apps_connections_open property
    type(client).apps_connections_open = PropertyMock(return_value="wss://test.slack.com/link")
    
    # Mock the aiohttp_client_session
    client.aiohttp_client_session = AsyncMock()
    client.aiohttp_client_session.ws_connect = AsyncMock()
    
    return client

@pytest.fixture
def flow_logger():
    logger = AsyncMock(spec=FlowLogger)
    logger.setup = AsyncMock()
    logger.log_event = AsyncMock()
    logger.error = AsyncMock()
    logger.info = AsyncMock()
    logger.debug = AsyncMock()
    logger.warning = AsyncMock()
    return logger

@pytest.fixture
def orchestrator():
    orchestrator = AsyncMock(spec=RequestOrchestrator)
    orchestrator.initialize = AsyncMock()
    orchestrator.process_request = AsyncMock()
    orchestrator.service_analyzer = AsyncMock()
    return orchestrator

@pytest.fixture
async def assistant(slack_token, app_token, web_client, socket_client, flow_logger, orchestrator):
    """Create a test assistant instance"""
    with patch('src.main.AsyncWebClient', return_value=web_client), \
         patch('src.main.SocketModeClient', return_value=socket_client), \
         patch('src.main.FlowLogger', return_value=flow_logger), \
         patch('src.main.RequestOrchestrator', return_value=orchestrator):
        assistant = OfficeAssistant(slack_token, app_token)
        assistant.web_client = web_client
        assistant.socket_client = socket_client
        assistant.flow_logger = flow_logger
        assistant.orchestrator = orchestrator
        assistant.bot_user_id = "U123BOT"
        await assistant.setup()
        return assistant

@pytest.mark.asyncio
async def test_initialization(assistant, web_client, socket_client, flow_logger, orchestrator):
    """Test assistant initialization"""
    # Await the assistant fixture
    assistant_instance = await assistant
    
    # Verify component initialization
    assert assistant_instance.web_client == web_client
    assert assistant_instance.socket_client == socket_client
    assert assistant_instance.flow_logger == flow_logger
    assert assistant_instance.orchestrator == orchestrator

@pytest.mark.asyncio
async def test_start_and_stop(assistant, socket_client):
    """Test assistant startup and shutdown"""
    # Await the assistant fixture
    assistant_instance = await assistant
    
    # Mock the setup method to avoid connection issues
    with patch.object(assistant_instance, 'setup', AsyncMock()) as mock_setup:
        # Start the assistant
        await assistant_instance.start()
        mock_setup.assert_called_once()
        socket_client.connect.assert_called_once()
        
        # Stop the assistant
        await assistant_instance.stop()
        socket_client.disconnect.assert_called_once()

@pytest.mark.asyncio
async def test_handle_socket_mode_request(assistant, socket_client, orchestrator):
    """Test handling of socket mode requests"""
    # Await the assistant fixture
    assistant_instance = await assistant
    
    # Setup test data
    req = MagicMock(spec=SocketModeRequest)
    req.envelope_id = "test-envelope"
    req.payload = {
        "event": {
            "type": "app_mention",
            "user": "U123USER",
            "text": "<@U123BOT> Schedule a meeting",
            "channel": "C456",
            "ts": "1234567890.123456"
        }
    }

    # Handle request
    await assistant_instance.handle_socket_mode_request(socket_client, req)
    
    # Verify acknowledgment was sent
    assert socket_client.send_socket_mode_response.call_count == 1
    response_arg = socket_client.send_socket_mode_response.call_args[0][0]
    assert isinstance(response_arg, SocketModeResponse)
    assert response_arg.envelope_id == req.envelope_id
    
    # Verify event was processed
    orchestrator.process_request.assert_called_once()

@pytest.mark.asyncio
async def test_process_event(assistant, orchestrator):
    """Test event processing"""
    # Await the assistant fixture
    assistant_instance = await assistant
    
    # Setup test event
    event = {
        "type": "app_mention",
        "user": "U123USER",
        "text": "<@U123BOT> Schedule a meeting",
        "channel": "C456",
        "ts": "1234567890.123456"
    }

    # Process event
    await assistant_instance.process_event(event)
    
    # Verify orchestrator was called with correct parameters
    orchestrator.process_request.assert_called_once_with(
        message="Schedule a meeting",
        user_info={
            "user_id": "U123USER",
            "channel_id": "C456",
            "thread_ts": None,
            "ts": "1234567890.123456"
        },
        channel_id="C456",
        thread_ts=None
    )

@pytest.mark.asyncio
async def test_process_event_invalid_type(assistant, orchestrator):
    """Test processing of invalid event types"""
    # Await the assistant fixture
    assistant_instance = await assistant
    
    # Setup invalid event
    event = {
        "type": "message",
        "user": "U123USER",
        "text": "Hello",
        "channel": "C456"
    }

    # Process event
    await assistant_instance.process_event(event)
    
    # Verify orchestrator was not called
    orchestrator.process_request.assert_not_called()

@pytest.mark.asyncio
async def test_process_event_bot_message(assistant, orchestrator):
    """Test processing of bot messages"""
    # Await the assistant fixture
    assistant_instance = await assistant
    
    # Setup bot message event
    event = {
        "type": "app_mention",
        "user": "U123BOT",  # Same as bot user ID
        "text": "<@U123BOT> Hello",
        "channel": "C456"
    }

    # Process event
    await assistant_instance.process_event(event)
    
    # Verify orchestrator was not called
    orchestrator.process_request.assert_not_called()

@pytest.mark.asyncio
async def test_error_handling(assistant, orchestrator):
    """Test error handling during event processing"""
    # Await the assistant fixture
    assistant_instance = await assistant
    
    # Setup test event
    event = {
        "type": "app_mention",
        "user": "U123USER",
        "text": "<@U123BOT> Schedule a meeting",
        "channel": "C456",
        "ts": "1234567890.123456"
    }

    # Configure orchestrator to raise an exception
    orchestrator.process_request.side_effect = Exception("Test error")

    # Process event (should not raise exception)
    await assistant_instance.process_event(event)
    
    # Verify error was logged
    assistant_instance.flow_logger.log_event.assert_called_with(
        "OfficeAssistant",
        "event_processing_error",
        {"error": "Test error"}
    ) 