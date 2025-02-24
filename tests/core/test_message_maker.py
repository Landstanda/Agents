import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.tools.message_maker import MessageMaker
from src.models import Ticket, TicketStatus, Message
from src.utils.flow_logger import FlowLogger

@pytest.fixture
def flow_logger():
    """Create a mock flow logger"""
    logger = AsyncMock(spec=FlowLogger)
    logger.log_event = AsyncMock()
    return logger

@pytest.fixture
def mock_openai():
    """Create a mock OpenAI client"""
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test response"))]
    ))
    return client

@pytest.fixture
def mock_slack():
    """Create a mock Slack client"""
    client = AsyncMock()
    client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "1234567890.123"})
    return client

@pytest.fixture
def message_maker(flow_logger, mock_openai, mock_slack):
    """Create a MessageMaker instance with mocked dependencies"""
    return MessageMaker(
        use_mock=True,
        mock_openai=mock_openai,
        mock_slack=mock_slack,
        flow_logger=flow_logger
    )

@pytest.fixture
def basic_ticket():
    """Create a basic ticket for testing"""
    ticket = Ticket(
        original_message="test message",
        user_info={"user_id": "U123"},
        channel_id="C456",
        thread_ts="1234567890.123"
    )
    return ticket

@pytest.mark.asyncio
class TestMessageMaker:
    """Tests for the MessageMaker class"""
    
    async def test_initialization(self, message_maker):
        """Test basic message maker initialization"""
        assert message_maker.flow_logger is not None
        assert message_maker.slack is not None
        assert message_maker.openai is not None
    
    async def test_send_basic_message(self, message_maker, basic_ticket):
        """Test sending a basic message"""
        await message_maker.send_message(basic_ticket)
        
        message_maker.slack.chat_postMessage.assert_called_once_with(
            channel=basic_ticket.channel_id,
            text="Test response",
            thread_ts=basic_ticket.thread_ts
        )
        assert len(basic_ticket.messages) == 2  # Original + response
        assert basic_ticket.messages[0].content == "test message"
        assert basic_ticket.messages[1].content == "Test response"
    
    async def test_send_error_status_message(self, message_maker, basic_ticket):
        """Test sending a message for error status"""
        basic_ticket.status = TicketStatus.ERROR
        basic_ticket.add_error("Test error", "test_error")
        
        await message_maker.send_message(basic_ticket)
        
        message_maker.slack.chat_postMessage.assert_called_once()
        call_args = message_maker.slack.chat_postMessage.call_args[1]
        assert call_args["channel"] == basic_ticket.channel_id
        assert call_args["thread_ts"] == basic_ticket.thread_ts
    
    async def test_send_success_message(self, message_maker, basic_ticket):
        """Test sending a success message"""
        basic_ticket.status = TicketStatus.COMPLETED
        basic_ticket.execution_results = [{"status": "success", "result": "test result"}]
        
        await message_maker.send_message(basic_ticket)
        
        message_maker.slack.chat_postMessage.assert_called_once()
        call_args = message_maker.slack.chat_postMessage.call_args[1]
        assert call_args["channel"] == basic_ticket.channel_id
        assert call_args["thread_ts"] == basic_ticket.thread_ts
        assert basic_ticket.final_response is not None
    
    async def test_send_waiting_message(self, message_maker, basic_ticket):
        """Test sending a waiting for input message"""
        basic_ticket.status = TicketStatus.WAITING_INPUT
        basic_ticket.missing_entities = ["time", "date"]
        
        await message_maker.send_message(basic_ticket)
        
        message_maker.slack.chat_postMessage.assert_called_once()
        call_args = message_maker.slack.chat_postMessage.call_args[1]
        assert call_args["channel"] == basic_ticket.channel_id
        assert call_args["thread_ts"] == basic_ticket.thread_ts
    
    async def test_gpt_failure_handling(self, message_maker, basic_ticket, mock_openai):
        """Test handling of GPT API failures"""
        # Simulate GPT failure
        mock_openai.chat.completions.create.side_effect = Exception("GPT API error")
        
        await message_maker.send_message(basic_ticket)
        
        # Should send fallback message
        message_maker.slack.chat_postMessage.assert_called_once()
        call_args = message_maker.slack.chat_postMessage.call_args[1]
        assert "i'm processing your request" in call_args["text"].lower()
        
        # Should log error
        message_maker.flow_logger.log_event.assert_called_with(
            "MessageMaker",
            "error",
            {"error": "GPT API error"}
        )
    
    async def test_slack_failure_handling(self, message_maker, basic_ticket):
        """Test handling of Slack API failures"""
        # Simulate Slack API error
        message_maker.slack.chat_postMessage.side_effect = Exception("Slack API error")
        
        await message_maker.send_message(basic_ticket)
        
        # Should log error
        message_maker.flow_logger.log_event.assert_called_with(
            "MessageMaker",
            "error",
            {"error": "Slack API error"}
        )
    
    async def test_message_history_formatting(self, message_maker, basic_ticket):
        """Test message history formatting"""
        # Add some messages
        messages = [
            ("Hello", "incoming"),
            ("Hi there", "assistant"),
            ("Help me", "incoming"),
            ("Sure", "assistant"),
            ("Thanks", "incoming")
        ]
        for content, direction in messages:
            basic_ticket.add_message(content, direction)
        
        # Get formatted history
        history = message_maker._format_message_history(basic_ticket)
        
        # Should only include last 5 messages
        assert len(history.split("\n")) == 5
        assert "Thanks" in history
    
    async def test_service_creation_message(self, message_maker, basic_ticket):
        """Test sending service creation message"""
        basic_ticket.status = TicketStatus.SERVICE_CREATION
        basic_ticket.created_services = ["test_service"]
        
        await message_maker.send_message(basic_ticket)
        
        message_maker.slack.chat_postMessage.assert_called_once()
        call_args = message_maker.slack.chat_postMessage.call_args[1]
        assert call_args["channel"] == basic_ticket.channel_id
        assert call_args["thread_ts"] == basic_ticket.thread_ts
    
    async def test_executing_status_message(self, message_maker, basic_ticket):
        """Test sending executing status message"""
        basic_ticket.status = TicketStatus.EXECUTING
        basic_ticket.steps_executed = [
            {"step": 1, "action": "test", "result": "success"},
            {"step": 2, "action": "verify", "result": "pending"}
        ]
        
        await message_maker.send_message(basic_ticket)
        
        message_maker.slack.chat_postMessage.assert_called_once()
        call_args = message_maker.slack.chat_postMessage.call_args[1]
        assert call_args["channel"] == basic_ticket.channel_id
        assert call_args["thread_ts"] == basic_ticket.thread_ts 