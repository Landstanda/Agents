import pytest
from src.office.reception.nlp_processor import NLPProcessor

@pytest.fixture
def nlp():
    return NLPProcessor()

@pytest.fixture
def sample_user_info():
    return {
        "id": "U123",
        "real_name": "John Doe",
        "is_dm": True
    }

@pytest.mark.asyncio
async def test_basic_intent_extraction(nlp, sample_user_info):
    """Test extraction of basic intents from messages."""
    # Test email intent
    message = "Can you send an email to the team?"
    result = await nlp.process_message(message, sample_user_info)
    assert "email_send" in result["all_intents"]
    
    # Test scheduling intent
    message = "Please schedule a meeting for next week"
    result = await nlp.process_message(message, sample_user_info)
    assert "scheduling" in result["all_intents"]
    
    # Test multiple intents
    message = "Research AI trends and prepare a report"
    result = await nlp.process_message(message, sample_user_info)
    assert "research" in result["all_intents"]
    assert "document" in result["all_intents"]

@pytest.mark.asyncio
async def test_entity_extraction(nlp, sample_user_info):
    """Test extraction of entities from messages."""
    message = "Send an email to john@example.com by 12/25/2024"
    result = await nlp.process_message(message, sample_user_info)
    
    assert "john@example.com" in result["entities"]["emails"]
    assert "12/25/2024" in result["entities"]["dates"]

@pytest.mark.asyncio
async def test_urgency_detection(nlp, sample_user_info):
    """Test urgency level detection."""
    # Test high urgency
    message = "URGENT: Need this report ASAP!"
    result = await nlp.process_message(message, sample_user_info)
    assert result["urgency"] > 0.7
    
    # Test medium urgency
    message = "Please complete this by tomorrow"
    result = await nlp.process_message(message, sample_user_info)
    assert result["urgency"] >= 0.3  # Base medium urgency
    assert result["urgency"] <= 0.7  # Not high urgency
    
    # Test low urgency
    message = "When you have time, could you look at this?"
    result = await nlp.process_message(message, sample_user_info)
    assert result["urgency"] <= 0.3
    
    # Test multiple urgency indicators
    message = "URGENT DEADLINE: Need report ASAP!!!"
    result = await nlp.process_message(message, sample_user_info)
    assert result["urgency"] > 0.8  # Should be very high urgency

@pytest.mark.asyncio
async def test_temporal_context(nlp, sample_user_info):
    """Test extraction of temporal context."""
    # Test specific day
    message = "Schedule the meeting for Tuesday"
    result = await nlp.process_message(message, sample_user_info)
    assert result["temporal_context"]["specific_day"] == "tuesday"
    
    # Test timeframe
    message = "Need this done by next week"
    result = await nlp.process_message(message, sample_user_info)
    assert result["temporal_context"]["timeframe"] == "next_week"
    
    # Test urgency timeframe
    message = "This is urgent, need it right away"
    result = await nlp.process_message(message, sample_user_info)
    assert result["temporal_context"]["timeframe"] == "urgent"

@pytest.mark.asyncio
async def test_user_context(nlp, sample_user_info):
    """Test user context information."""
    message = "Hello there"
    result = await nlp.process_message(message, sample_user_info)
    
    assert result["user_context"]["user_id"] == "U123"
    assert result["user_context"]["user_name"] == "John Doe"
    assert result["user_context"]["is_dm"] == True
    assert "timestamp" in result["user_context"]

@pytest.mark.asyncio
async def test_error_handling(nlp):
    """Test error handling with invalid inputs."""
    # Test with None message
    result = await nlp.process_message(None, {})
    assert result["status"] == "error"
    
    # Test with invalid user_info
    result = await nlp.process_message("Hello", None)
    assert result["status"] == "error"

@pytest.mark.asyncio
async def test_basic_greeting_processing():
    """Test that basic greetings are processed efficiently."""
    nlp = NLPProcessor()
    user_info = {"id": "U123", "real_name": "Test User"}
    
    # Test various greetings
    greetings = ["hi", "hello", "hey there", "good morning"]
    for greeting in greetings:
        result = await nlp.process_message(greeting, user_info)
        assert result["intent"] == "greeting"
        assert result["urgency"] == 0.1  # Greetings should have low urgency
        assert not any(entities for entities in result["entities"].values())  # All entity lists should be empty

@pytest.mark.asyncio
async def test_multiple_intents():
    """Test detection of multiple intents in a single message."""
    nlp = NLPProcessor()
    user_info = {"id": "U123", "real_name": "Test User"}
    
    message = "Schedule a meeting and send an email about it"
    result = await nlp.process_message(message, user_info)
    assert len(result["all_intents"]) >= 2
    assert "scheduling" in result["all_intents"]
    assert "email_send" in result["all_intents"] 