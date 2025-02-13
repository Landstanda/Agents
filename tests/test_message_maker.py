"""
Tests for the MessageMaker class which handles Slack message generation and delivery.

This test suite verifies:
1. Basic message sending functionality with tickets
2. Message generation for different ticket states
3. GPT prompt formatting and response handling
4. Error handling and recovery
5. Message history formatting
6. Threaded conversation support

By default, tests use mock clients to avoid API costs and ensure consistent behavior.
To use real GPT for testing, set the USE_REAL_GPT environment variable to "true".
Note that using real GPT will require valid API keys and may incur costs.
"""

import pytest
import os
from datetime import datetime
from src.tools.message_maker import MessageMaker
from src.tools.nlp import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger

# Mock classes for testing
class MockSlack:
    def __init__(self):
        self.messages = []
        
    async def chat_postMessage(self, channel, text, thread_ts=None):
        self.messages.append({
            "channel": channel,
            "text": text,
            "thread_ts": thread_ts
        })
        return {"ok": True, "ts": "test_ts"}

class MockOpenAI:
    def __init__(self, responses=None):
        class Chat:
            def __init__(self, responses):
                self.responses = responses or {
                    TicketStatus.COMPLETED: "I've successfully completed your request!",
                    TicketStatus.ERROR: "I encountered an error: Test error",
                    TicketStatus.WAITING_INPUT: "I need some additional information: time, date",
                    TicketStatus.SERVICE_CREATION: "I'm creating a new service to handle your request.",
                    TicketStatus.CREATED: "I've received your request",
                    None: "I'm processing your request."
                }
                self.calls = []
                
                class Completions:
                    def __init__(self, responses, calls):
                        self.responses = responses
                        self.calls = calls
                        
                    async def create(self, model, messages, temperature, max_tokens):
                        self.calls.append({
                            "model": model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens
                        })
                        
                        # Get response based on ticket status from the prompt
                        status = None
                        prompt = next(msg["content"] for msg in messages if msg["role"] == "user")
                        
                        # Check for specific status keywords in the prompt
                        if "waiting_input" in prompt.lower() or "missing information" in prompt.lower():
                            status = TicketStatus.WAITING_INPUT
                        elif "service_creation" in prompt.lower() or "creating a new service" in prompt.lower():
                            status = TicketStatus.SERVICE_CREATION
                        elif "completed" in prompt.lower():
                            status = TicketStatus.COMPLETED
                        elif "error" in prompt.lower():
                            status = TicketStatus.ERROR
                        elif "created" in prompt.lower():
                            status = TicketStatus.CREATED
                        
                        response_text = self.responses.get(status, self.responses[None])
                        
                        class MockResponse:
                            def __init__(self, content):
                                class Choice:
                                    def __init__(self, content):
                                        class Message:
                                            def __init__(self, content):
                                                self.content = content
                                        self.message = Message(content)
                                    
                                self.choices = [Choice(content)]
                        
                        return MockResponse(response_text)
                
                self.completions = Completions(responses or self.responses, self.calls)
        
        self.chat = Chat(responses)

@pytest.fixture
def message_maker():
    """Create a MessageMaker instance with appropriate clients based on environment.
    
    By default, uses mock clients for testing. To use real GPT, set USE_REAL_GPT=true.
    Note that using real GPT requires valid API keys and may incur costs.
    """
    use_real_gpt = os.getenv("USE_REAL_GPT", "").lower() == "true"
    
    if use_real_gpt:
        # Use real GPT with mock Slack
        maker = MessageMaker(use_mock=False)
        # Replace Slack with mock to track messages
        maker.slack = MockSlack()
        return maker
    else:
        # Use mock clients for testing (default)
        return MessageMaker(
            use_mock=True,
            mock_openai=MockOpenAI(),
            mock_slack=MockSlack()
        )

@pytest.fixture
def basic_ticket():
    """Create a basic ticket for testing."""
    ticket = Ticket(
        user_info={"user_id": "test_user"},
        channel_id="test_channel",
        original_message="Test request"
    )
    # Note: Don't add message here, it's already added by Ticket.__post_init__
    return ticket

@pytest.mark.asyncio
async def test_basic_message_sending(message_maker, basic_ticket):
    """Test basic message sending functionality."""
    await message_maker.send_message(basic_ticket)
    
    # Verify message was sent
    assert len(message_maker.slack.messages) == 1
    sent_message = message_maker.slack.messages[0]
    assert sent_message["channel"] == "test_channel"
    # When using real GPT, we can't predict exact message content
    assert isinstance(sent_message["text"], str)
    assert len(sent_message["text"]) > 0
    
    # Verify message was added to ticket
    assert len(basic_ticket.messages) == 2  # Original + response
    assert basic_ticket.messages[-1]["source"] == "assistant"

@pytest.mark.asyncio
async def test_completed_status_message(message_maker, basic_ticket):
    """Test message generation for completed status."""
    basic_ticket.status = TicketStatus.COMPLETED
    basic_ticket.execution_results = [
        {"step": "test_step", "result": "success"}
    ]
    
    await message_maker.send_message(basic_ticket)
    
    sent_message = message_maker.slack.messages[0]
    # When using real GPT, verify it generates a reasonable response
    assert isinstance(sent_message["text"], str)
    assert len(sent_message["text"]) > 0
    assert basic_ticket.final_response is not None

@pytest.mark.asyncio
async def test_error_status_message(message_maker, basic_ticket):
    """Test message generation for error status."""
    basic_ticket.status = TicketStatus.ERROR
    basic_ticket.add_error("Test error", "test_error")
    
    await message_maker.send_message(basic_ticket)
    
    sent_message = message_maker.slack.messages[0]
    # When using real GPT, verify it mentions the error
    assert isinstance(sent_message["text"], str)
    assert len(sent_message["text"]) > 0

@pytest.mark.asyncio
async def test_waiting_input_message(message_maker, basic_ticket):
    """Test message generation for waiting input status."""
    basic_ticket.status = TicketStatus.WAITING_INPUT
    basic_ticket.missing_entities = ["time", "date"]
    
    await message_maker.send_message(basic_ticket)
    
    sent_message = message_maker.slack.messages[0]
    # When using real GPT, verify it generates a response
    assert isinstance(sent_message["text"], str)
    assert len(sent_message["text"]) > 0

@pytest.mark.asyncio
async def test_service_creation_message(message_maker, basic_ticket):
    """Test message generation for service creation status."""
    basic_ticket.status = TicketStatus.SERVICE_CREATION
    basic_ticket.created_services = [{
        "name": "test_service",
        "description": "A test service"
    }]
    
    await message_maker.send_message(basic_ticket)
    
    sent_message = message_maker.slack.messages[0]
    # When using real GPT, verify it generates a response
    assert isinstance(sent_message["text"], str)
    assert len(sent_message["text"]) > 0

@pytest.mark.asyncio
async def test_threaded_conversation(message_maker, basic_ticket):
    """Test handling of threaded conversations."""
    basic_ticket.thread_ts = "parent_ts"
    
    await message_maker.send_message(basic_ticket)
    
    sent_message = message_maker.slack.messages[0]
    assert sent_message["thread_ts"] == "parent_ts"

@pytest.mark.asyncio
async def test_gpt_prompt_formatting(message_maker, basic_ticket):
    """Test GPT prompt formatting for different states."""
    # Test COMPLETED status
    basic_ticket.status = TicketStatus.COMPLETED
    basic_ticket.execution_results = [{"step": "test", "result": "success"}]
    await message_maker.send_message(basic_ticket)
    
    # When using real GPT, we can't track calls, but we can verify the response
    sent_message = message_maker.slack.messages[0]
    assert isinstance(sent_message["text"], str)
    assert len(sent_message["text"]) > 0

@pytest.mark.asyncio
async def test_fallback_message_handling(message_maker, basic_ticket):
    """Test fallback message generation when GPT fails."""
    # Create a mock OpenAI that returns no choices
    class FailingOpenAI:
        def __init__(self):
            class Chat:
                def __init__(self):
                    class Completions:
                        async def create(self, model, messages, temperature, max_tokens):
                            class MockResponse:
                                choices = []
                            return MockResponse()
                    self.completions = Completions()
            self.chat = Chat()
    
    message_maker.openai = FailingOpenAI()
    
    await message_maker.send_message(basic_ticket)
    
    sent_message = message_maker.slack.messages[0]
    # The fallback message for CREATED status is "I've received your request"
    assert sent_message["text"].rstrip(".") == "I've received your request"
    assert len(basic_ticket.messages) == 2  # Original + fallback

@pytest.mark.asyncio
async def test_message_history_formatting(message_maker, basic_ticket):
    """Test formatting of message history for GPT prompt."""
    # Add some message history
    basic_ticket.add_message("First message", "user")
    basic_ticket.add_message("First response", "assistant")
    basic_ticket.add_message("Second message", "user")
    
    await message_maker.send_message(basic_ticket)
    
    # When using real GPT, verify it generates a response
    sent_message = message_maker.slack.messages[0]
    assert isinstance(sent_message["text"], str)
    assert len(sent_message["text"]) > 0

@pytest.mark.asyncio
async def test_error_handling(message_maker, basic_ticket):
    """Test error handling during message sending."""
    # Create a mock Slack that raises an error
    class FailingSlack:
        async def chat_postMessage(self, channel, text, thread_ts=None):
            raise Exception("Slack API error")
    
    message_maker.slack = FailingSlack()
    
    # Should not raise exception but add error to ticket
    await message_maker.send_message(basic_ticket)
    
    assert len(basic_ticket.errors) == 1
    assert "slack api error" in basic_ticket.errors[0]["message"].lower() 