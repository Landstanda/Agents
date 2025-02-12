import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from src.office.reception.front_desk import FrontDesk

@pytest.mark.asyncio
async def test_basic_greeting():
    """Test handling of a basic greeting message."""
    # Mock components
    web_client = AsyncMock()
    web_client.users_info = AsyncMock(return_value={"ok": True, "user": {"real_name": "Test User"}})
    web_client.chat_postMessage = AsyncMock(return_value={"ok": True})
    
    nlp = AsyncMock()
    nlp.process_message = AsyncMock(return_value={
        "intent": None,
        "entities": {},
        "keywords": ["hi"],
        "urgency": 0.1
    })
    
    cookbook = AsyncMock()
    cookbook.find_matching_recipe = AsyncMock(return_value=None)
    
    ceo = AsyncMock()
    ceo.consider_request = AsyncMock(return_value={
        "status": "success",
        "decision": "I'll help with a friendly greeting",
        "confidence": 0.9,
        "notes": "Simple greeting"
    })
    
    # Create FrontDesk instance
    front_desk = FrontDesk(
        web_client=web_client,
        nlp=nlp,
        cookbook=cookbook,
        ceo=ceo,
        bot_id="U123"
    )
    
    # Test message
    message = {
        "type": "message",
        "channel": "C123",
        "user": "U456",
        "text": "<@U123> hi!",
        "ts": "1234567890.123"
    }
    
    # Process message
    await front_desk.handle_message(message)
    
    # Verify flow
    nlp.process_message.assert_called_once()
    cookbook.find_matching_recipe.assert_called_once()
    ceo.consider_request.assert_called_once()
    assert web_client.chat_postMessage.call_count == 2  # Acknowledgment + Response

@pytest.mark.asyncio
async def test_schedule_meeting():
    """Test handling of a meeting scheduling request."""
    # Mock components
    web_client = AsyncMock()
    web_client.users_info = AsyncMock(return_value={"ok": True, "user": {"real_name": "Test User"}})
    web_client.chat_postMessage = AsyncMock(return_value={"ok": True})
    
    nlp = AsyncMock()
    nlp.process_message = AsyncMock(return_value={
        "intent": "schedule_meeting",
        "entities": {
            "time": "2:00 p.m. today"
        },
        "keywords": ["schedule", "meeting"],
        "urgency": 0.3
    })
    
    cookbook = AsyncMock()
    cookbook.find_matching_recipe = AsyncMock(return_value={
        "name": "Schedule Meeting",
        "intent": "schedule_meeting",
        "required_entities": ["time", "participants"],
        "steps": []
    })
    
    task_manager = AsyncMock()
    task_manager.execute_recipe = AsyncMock(return_value={
        "status": "success",
        "details": "Meeting scheduled"
    })
    
    # Create FrontDesk instance
    front_desk = FrontDesk(
        web_client=web_client,
        nlp=nlp,
        cookbook=cookbook,
        task_manager=task_manager,
        bot_id="U123"
    )
    
    # Test message
    message = {
        "type": "message",
        "channel": "C123",
        "user": "U456",
        "text": "<@U123> schedule a meeting for 2:00 p.m. today",
        "ts": "1234567890.123"
    }
    
    # Process message
    await front_desk.handle_message(message)
    
    # Verify flow
    nlp.process_message.assert_called_once()
    cookbook.find_matching_recipe.assert_called_once()
    assert web_client.chat_postMessage.call_count >= 1  # Should ask for missing participants

@pytest.mark.asyncio
async def test_user_info_failure():
    """Test handling when user info fetch fails."""
    # Mock components with failing users_info
    web_client = AsyncMock()
    web_client.users_info = AsyncMock(side_effect=Exception("Missing scope"))
    web_client.chat_postMessage = AsyncMock(return_value={"ok": True})
    
    nlp = AsyncMock()
    nlp.process_message = AsyncMock(return_value={
        "intent": None,
        "entities": {},
        "keywords": ["hi"],
        "urgency": 0.1
    })
    
    cookbook = AsyncMock()
    cookbook.find_matching_recipe = AsyncMock(return_value=None)
    
    # Create FrontDesk instance
    front_desk = FrontDesk(
        web_client=web_client,
        nlp=nlp,
        cookbook=cookbook,
        bot_id="U123"
    )
    
    # Test message
    message = {
        "type": "message",
        "channel": "C123",
        "user": "U456",
        "text": "<@U123> hi!",
        "ts": "1234567890.123"
    }
    
    # Process message
    await front_desk.handle_message(message)
    
    # Verify flow continues despite user info failure
    nlp.process_message.assert_called_once()
    cookbook.find_matching_recipe.assert_called_once()
    assert web_client.chat_postMessage.call_count >= 1 

@pytest.mark.asyncio
async def test_gpt_response():
    """Test GPT response generation and handling."""
    # Mock OpenAI client
    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(content="I understand you want to schedule a meeting. I'll help you with that!"))]
    ))
    
    # Create FrontDesk instance with mocked OpenAI
    front_desk = FrontDesk(
        openai_client=openai_client,
        bot_id="U123"
    )
    
    # Test basic GPT response
    response = await front_desk.get_gpt_response("Help me schedule a meeting")
    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0
    
    # Verify GPT was called with correct parameters
    openai_client.chat.completions.create.assert_called_once()
    call_args = openai_client.chat.completions.create.call_args[1]
    assert call_args["model"] == "gpt-3.5-turbo"
    assert len(call_args["messages"]) == 2
    assert call_args["messages"][0]["role"] == "system"
    assert call_args["messages"][1]["role"] == "user"
    
    # Test GPT error handling with fallback responses
    openai_client.chat.completions.create.reset_mock()
    openai_client.chat.completions.create.side_effect = Exception("API Error")
    
    # Test meeting-related fallback
    response = await front_desk.get_gpt_response("schedule a meeting")
    assert "meeting" in response.lower()
    assert "understand" in response.lower()  # Should include "I understand" in meeting response
    
    # Test email-related fallback
    response = await front_desk.get_gpt_response("check my emails")
    assert "email" in response.lower()
    assert "understand" in response.lower()  # Should include "I understand" in email response
    
    # Test greeting fallback
    response = await front_desk.get_gpt_response("hi there")
    assert any(word in response.lower() for word in ["hi", "hello"])
    
    # Test generic fallback
    response = await front_desk.get_gpt_response("do something random")
    assert response is not None
    assert any(phrase in response.lower() for phrase in ["how can i help", "hello"])  # Check for common greeting phrases

@pytest.mark.asyncio
async def test_contextual_responses():
    """Test generation of contextual responses for different scenarios."""
    # Mock components
    openai_client = AsyncMock()
    openai_client.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(content="I'll help you with that!"))]
    ))
    
    web_client = AsyncMock()
    web_client.users_info = AsyncMock(return_value={"ok": True, "user": {"real_name": "Test User"}})
    web_client.chat_postMessage = AsyncMock(return_value={"ok": True})
    
    nlp = AsyncMock()
    cookbook = AsyncMock()
    
    # Create FrontDesk instance
    front_desk = FrontDesk(
        web_client=web_client,
        openai_client=openai_client,
        nlp=nlp,
        cookbook=cookbook,
        bot_id="U123"
    )
    
    # Test missing information prompt
    nlp.process_message.return_value = {
        "intent": "schedule_meeting",
        "entities": {"time": "2pm"},
        "keywords": ["schedule", "meeting"]
    }
    
    cookbook.find_matching_recipe.return_value = {
        "name": "Schedule Meeting",
        "intent": "schedule_meeting",
        "required_entities": ["time", "participants"],
        "steps": []
    }
    
    message = {
        "type": "message",
        "channel": "C123",
        "user": "U456",
        "text": "<@U123> schedule a meeting at 2pm",
        "ts": "1234567890.123"
    }
    
    # Process message
    await front_desk.handle_message(message)
    
    # Verify GPT was called with appropriate context
    assert openai_client.chat.completions.create.call_count > 0
    prompt_calls = [call[1]["messages"][1]["content"] for call in openai_client.chat.completions.create.call_args_list]
    
    # Check that at least one prompt mentions missing participants
    assert any("participants" in prompt for prompt in prompt_calls)
    
    # Verify response was sent to Slack
    assert web_client.chat_postMessage.call_count >= 1 