import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from slack_bolt.async_app import AsyncApp
from src.main import OfficeAssistant

@pytest.fixture
def mock_env():
    """Set up environment variables for testing."""
    os.environ["SLACK_BOT_TOKEN"] = "xoxb-test-token"
    os.environ["SLACK_APP_TOKEN"] = "xapp-test-token"
    yield
    del os.environ["SLACK_BOT_TOKEN"]
    del os.environ["SLACK_APP_TOKEN"]

@pytest.fixture
def mock_components():
    """Mock all components."""
    nlp = AsyncMock()
    agent = AsyncMock()
    message_maker = MagicMock()
    service_maker = AsyncMock()
    
    # Set up specific mock behaviors
    message_maker.send_message = AsyncMock()
    
    return {
        'nlp': nlp,
        'agent': agent,
        'message_maker': message_maker,
        'service_maker': service_maker
    }

@pytest.fixture
async def assistant(mock_env, mock_components):
    """Create an OfficeAssistant instance for testing."""
    assistant = OfficeAssistant()
    await assistant.setup()
    with patch('src.tools.nlp.NLPAnalyzer.create', return_value=mock_components['nlp']), \
         patch('src.tools.agent.Agent.create', return_value=mock_components['agent']), \
         patch('src.tools.message_maker.MessageMaker', return_value=mock_components['message_maker']), \
         patch('src.tools.service_maker.ServiceMaker.create', return_value=mock_components['service_maker']):
        
        await assistant.initialize()
        yield assistant, mock_components
    await assistant.stop()

@pytest.mark.asyncio
async def test_message_handling(assistant):
    """Test handling of a regular message."""
    # Mock the say function
    say = AsyncMock()
    
    # Create a test message event
    event = {
        "type": "message",
        "user": "U123456",
        "channel": "C123456",
        "text": "schedule a meeting with John tomorrow at 2pm"
    }
    
    # Mock user info response
    with patch.object(assistant.web_client, "users_info") as mock_users_info:
        mock_users_info.return_value = {
            "user": {
                "id": "U123456",
                "name": "testuser",
                "real_name": "Test User"
            }
        }
        
        # Call the message handler
        await assistant.app.listeners[0].callback(event, say)
        
        # Verify say was called
        say.assert_called_once()
        
        # Get the call arguments
        call_args = say.call_args[1]
        
        # Verify the response format
        assert "text" in call_args
        assert "blocks" in call_args
        assert isinstance(call_args["blocks"], list)

@pytest.mark.asyncio
async def test_error_handling(assistant):
    """Test handling of errors during message processing."""
    # Mock the say function
    say = AsyncMock()
    
    # Create a test message event that will cause an error
    event = {
        "type": "message",
        "user": "U123456",
        "channel": "C123456",
        "text": ""  # Empty message should cause an error
    }
    
    # Mock user info response
    with patch.object(assistant.web_client, "users_info") as mock_users_info:
        mock_users_info.return_value = {
            "user": {
                "id": "U123456",
                "name": "testuser",
                "real_name": "Test User"
            }
        }
        
        # Call the message handler
        await assistant.app.listeners[0].callback(event, say)
        
        # Verify say was called with an error message
        say.assert_called_once()
        
        # Get the call arguments
        call_args = say.call_args[1]
        
        # Verify the error response format
        assert "text" in call_args
        assert "blocks" in call_args
        assert isinstance(call_args["blocks"], list)
        assert ":warning:" in str(call_args["blocks"])

@pytest.mark.asyncio
async def test_incomplete_request(assistant):
    """Test handling of requests with missing required information."""
    # Mock the say function
    say = AsyncMock()
    
    # Create a test message event with missing information
    event = {
        "type": "message",
        "user": "U123456",
        "channel": "C123456",
        "text": "schedule a meeting"  # Missing time and participants
    }
    
    # Mock user info response
    with patch.object(assistant.web_client, "users_info") as mock_users_info:
        mock_users_info.return_value = {
            "user": {
                "id": "U123456",
                "name": "testuser",
                "real_name": "Test User"
            }
        }
        
        # Call the message handler
        await assistant.app.listeners[0].callback(event, say)
        
        # Verify say was called
        say.assert_called_once()
        
        # Get the call arguments
        call_args = say.call_args[1]
        
        # Verify the response asks for missing information
        assert "text" in call_args
        assert "blocks" in call_args
        assert isinstance(call_args["blocks"], list)
        assert "need more information" in call_args["text"].lower()

@pytest.mark.asyncio
async def test_matched_message_handling(assistant):
    """Test handling of messages that match a known service."""
    assistant_instance, mock_components = assistant
    
    # Create test message
    message = {
        'text': 'schedule a meeting',
        'user': 'U123456',
        'channel': 'C123456',
        'team': 'T123456'
    }
    
    # Mock NLP analysis
    mock_components['nlp'].analyze_message.return_value = {
        'status': 'matched',
        'service': 'schedule_meeting',
        'entities': {'time': '2pm', 'date': 'tomorrow'}
    }
    
    # Mock service execution
    mock_components['agent'].execute_service.return_value = {
        'status': 'success',
        'result': 'Meeting scheduled'
    }
    
    # Handle message
    await assistant_instance.handle_message(message, AsyncMock())
    
    # Verify message was analyzed
    mock_components['nlp'].analyze_message.assert_called_once_with(
        'schedule a meeting',
        {
            'user_id': 'U123456',
            'channel_id': 'C123456',
            'team_id': 'T123456'
        }
    )
    
    # Verify service was executed
    mock_components['agent'].execute_service.assert_called_once()
    
    # Verify response was sent
    mock_components['message_maker'].send_message.assert_called_once()

@pytest.mark.asyncio
async def test_unknown_message_handling(assistant):
    """Test handling of unknown messages."""
    assistant_instance, mock_components = assistant
    
    # Create test message
    message = {
        'text': 'do something new',
        'user': 'U123456',
        'channel': 'C123456',
        'team': 'T123456'
    }
    
    # Mock NLP analysis
    mock_components['nlp'].analyze_message.return_value = {
        'status': 'unknown',
        'message': 'do something new'
    }
    
    # Mock service creation
    mock_components['service_maker'].create_service.return_value = {
        'status': 'success',
        'service': {
            'name': 'new_service',
            'description': 'A new service'
        }
    }
    
    # Handle message
    await assistant_instance.handle_message(message, AsyncMock())
    
    # Verify service creation was attempted
    mock_components['service_maker'].create_service.assert_called_once()
    
    # Verify success message was sent
    mock_components['message_maker'].send_message.assert_called_once_with(
        'C123456',
        {
            'type': 'service_creation',
            'details': {
                'service': {
                    'name': 'new_service',
                    'description': 'A new service'
                }
            }
        }
    ) 