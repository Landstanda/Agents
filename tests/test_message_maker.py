"""
Tests for the MessageMaker class which handles Slack message generation and delivery.

This test suite verifies:
1. Basic message sending functionality
2. Message formatting with parameters
3. Integration with NLP analyzer
4. Integration with Agent
5. GPT response generation
6. Logging functionality

Each test uses mocked dependencies to isolate the MessageMaker functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.tools.message_maker import MessageMaker
from src.tools.nlp import NLPAnalyzer
from src.tools.agent import Agent
from src.tools.service_maker import ServiceMaker
from src.utils.flow_logger import FlowLogger
from slack_sdk.web.async_client import AsyncWebClient
from openai import AsyncOpenAI

# Fixtures
@pytest.fixture
def flow_logger():
    """Create a FlowLogger instance for testing."""
    return FlowLogger()

@pytest.fixture
def mock_web_client():
    """Create a mock Slack web client with mocked postMessage method."""
    client = AsyncMock(spec=AsyncWebClient)
    client.chat_postMessage = AsyncMock(return_value={"ok": True})
    return client

@pytest.fixture
def mock_openai():
    """
    Create a mock OpenAI client with the necessary structure:
    - client.chat.completions.create() returns a mocked GPT response
    """
    mock_completion = AsyncMock()
    mock_completion.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test GPT response"))]
    ))
    
    mock_chat = MagicMock()
    mock_chat.completions = mock_completion
    
    client = AsyncMock()
    client.chat = mock_chat
    return client

@pytest.fixture
def message_maker(mock_web_client, flow_logger, mock_openai):
    """
    Create a MessageMaker instance with mocked dependencies:
    - mock_web_client for Slack communication
    - flow_logger for logging
    - mock_openai for GPT responses
    """
    maker = MessageMaker(web_client=mock_web_client, flow_logger=flow_logger)
    maker.openai = mock_openai
    return maker

# Tests
@pytest.mark.asyncio
async def test_message_maker_basic_send(message_maker, mock_web_client):
    """
    Test basic message sending functionality.
    Verifies that a simple text message is correctly sent to Slack.
    """
    await message_maker.send_message(
        channel="test_channel",
        text="Hello, world!"
    )
    
    mock_web_client.chat_postMessage.assert_called_once_with(
        channel="test_channel",
        text="Hello, world!",
        blocks=None
    )

@pytest.mark.asyncio
async def test_message_maker_format_response(message_maker, mock_web_client):
    """
    Test message formatting with parameters.
    Verifies that messages with placeholders are correctly formatted before sending.
    """
    await message_maker.send_message(
        channel="test_channel",
        text={
            "text": "Meeting scheduled for {time} on {date}",
            "params": {
                "time": "2:00 PM",
                "date": "tomorrow"
            }
        }
    )
    
    mock_web_client.chat_postMessage.assert_called_once_with(
        channel="test_channel",
        text="Meeting scheduled for 2:00 PM on tomorrow",
        blocks=None
    )

@pytest.mark.asyncio
async def test_message_maker_with_nlp(message_maker, mock_web_client, flow_logger):
    """
    Test integration with NLP analyzer.
    Verifies that:
    1. NLP analysis results are correctly handled
    2. Appropriate responses are generated for incomplete requests
    3. Messages are properly sent based on NLP results
    """
    with patch('src.tools.nlp.NLPAnalyzer.create') as mock_create:
        mock_nlp = AsyncMock(spec=NLPAnalyzer)
        mock_nlp.analyze_message = AsyncMock(return_value={
            "status": "incomplete",
            "missing_entities": ["time", "date"],
            "entities": {}
        })
        mock_create.return_value = mock_nlp
        
        nlp = await NLPAnalyzer.create(flow_logger=flow_logger)
        
        # Process a message
        result = await nlp.analyze_message(
            "schedule a meeting tomorrow at 2pm",
            {"user_id": "U123"}
        )
        
        # Send response based on NLP result
        if result.get("status") == "incomplete":
            missing = result.get("missing_entities", [])
            response = {
                "text": f"I need more information about: {', '.join(missing)}",
                "params": {}
            }
        else:
            response = {
                "text": "I'll help you schedule that meeting!",
                "params": {}
            }
        
        await message_maker.send_message(
            channel="test_channel",
            text=response
        )
        
        mock_web_client.chat_postMessage.assert_called_once()

@pytest.mark.asyncio
async def test_message_maker_with_agent(message_maker, mock_web_client, flow_logger):
    """
    Test integration with Agent.
    Verifies that:
    1. Agent service execution results are correctly handled
    2. Messages are properly formatted and sent based on agent responses
    """
    with patch('src.tools.agent.Agent.load_services') as mock_load:
        mock_load.return_value = None
        
        agent = Agent(flow_logger=flow_logger)
        await agent.load_services()
        
        # Mock execute_service
        agent.execute_service = AsyncMock(return_value={
            "text": "I can help you with scheduling meetings and more!",
            "params": {}
        })
        
        # Execute a service
        result = await agent.execute_service({
            "service": "help",
            "intent": "help",
            "entities": {}
        })
        
        await message_maker.send_message(
            channel="test_channel",
            text=result
        )
        
        mock_web_client.chat_postMessage.assert_called_once()

@pytest.mark.asyncio
async def test_message_maker_gpt_response(message_maker, mock_web_client, mock_openai):
    """
    Test GPT response generation and sending.
    Verifies that:
    1. GPT responses are correctly generated
    2. Generated responses are properly sent to Slack
    """
    prompt = "Generate a friendly response for: schedule a meeting"
    response = await message_maker.get_gpt_response(prompt)
    
    await message_maker.send_message(
        channel="test_channel",
        text=response
    )
    
    mock_openai.chat.completions.create.assert_called_once()
    mock_web_client.chat_postMessage.assert_called_once()

@pytest.mark.asyncio
async def test_message_maker_logging(message_maker, flow_logger):
    """
    Test logging functionality.
    Verifies that the flow logger is properly initialized and available.
    Note: In a production environment, we would also verify log file contents.
    """
    await message_maker.send_message(
        channel="test_channel",
        text="Test message"
    )
    
    assert message_maker.flow_logger is not None 