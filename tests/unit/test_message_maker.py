import pytest
import os
from src.tools.message_maker import MessageMaker

@pytest.fixture
def message_maker(mock_openai, mock_slack, monkeypatch):
    """Create a MessageMaker instance with mocked dependencies."""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    
    maker = MessageMaker()
    maker.openai = mock_openai
    maker.slack = mock_slack
    return maker

@pytest.mark.asyncio
async def test_send_message_info_request(message_maker):
    """Test sending an info request message."""
    context = {
        "type": "info_request",
        "details": {
            "missing_info": ["time", "participants"],
            "service": "schedule_meeting"
        }
    }
    
    await message_maker.send_message("C123", context)
    
    # Verify GPT was called with correct prompt
    message_maker.openai.chat.completions.create.assert_called_once()
    call_args = message_maker.openai.chat.completions.create.call_args[1]
    assert "missing information" in call_args["messages"][1]["content"].lower()
    
    # Verify Slack message was sent
    message_maker.slack.chat_postMessage.assert_called_once()

@pytest.mark.asyncio
async def test_send_message_completion(message_maker):
    """Test sending a completion message."""
    context = {
        "type": "completion",
        "details": {
            "service": "schedule_meeting",
            "results": {"meeting_id": "123", "time": "2pm"}
        }
    }
    
    await message_maker.send_message("C123", context)
    
    message_maker.openai.chat.completions.create.assert_called_once()
    message_maker.slack.chat_postMessage.assert_called_once()

@pytest.mark.asyncio
async def test_send_message_error(message_maker):
    """Test sending an error message."""
    context = {
        "type": "error",
        "details": {
            "error": "Something went wrong"
        }
    }
    
    await message_maker.send_message("C123", context)
    
    message_maker.openai.chat.completions.create.assert_called_once()
    message_maker.slack.chat_postMessage.assert_called_once()

@pytest.mark.asyncio
async def test_send_message_gpt_failure(message_maker):
    """Test handling GPT failure gracefully."""
    # Make GPT fail
    message_maker.openai.chat.completions.create.side_effect = Exception("GPT error")
    
    context = {
        "type": "info_request",
        "details": {
            "missing_info": ["time"],
            "message": "When would you like to schedule the meeting?"
        }
    }
    
    await message_maker.send_message("C123", context)
    
    # Should send fallback message
    message_maker.slack.chat_postMessage.assert_called_once_with(
        channel="C123",
        text=context["details"]["message"],
        thread_ts=None
    )

@pytest.mark.asyncio
async def test_send_message_with_thread(message_maker):
    """Test sending a message in a thread."""
    context = {
        "type": "completion",
        "details": {
            "service": "test_service",
            "results": {"status": "done"}
        }
    }
    
    thread_ts = "1234.5678"
    await message_maker.send_message("C123", context, thread_ts)
    
    call_args = message_maker.slack.chat_postMessage.call_args[1]
    assert call_args["thread_ts"] == thread_ts 