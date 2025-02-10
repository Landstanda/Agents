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

def test_basic_intent_extraction(nlp, sample_user_info):
    """Test extraction of basic intents from messages."""
    # Test email intent
    message = "Can you send an email to the team?"
    result = nlp.process_message(message, sample_user_info)
    assert "communication" in result["intents"]
    
    # Test scheduling intent
    message = "Please schedule a meeting for next week"
    result = nlp.process_message(message, sample_user_info)
    assert "scheduling" in result["intents"]
    
    # Test multiple intents
    message = "Research AI trends and prepare a report"
    result = nlp.process_message(message, sample_user_info)
    assert "research" in result["intents"]
    assert "document" in result["intents"]

def test_entity_extraction(nlp, sample_user_info):
    """Test extraction of entities from messages."""
    message = "Send an email to john@example.com by 12/25/2024"
    result = nlp.process_message(message, sample_user_info)
    
    assert "john@example.com" in result["entities"]["emails"]
    assert "12/25/2024" in result["entities"]["dates"]

def test_urgency_detection(nlp, sample_user_info):
    """Test urgency level detection."""
    # Test high urgency
    message = "URGENT: Need this report ASAP!"
    result = nlp.process_message(message, sample_user_info)
    assert result["urgency"] > 0.7
    
    # Test medium urgency
    message = "Please complete this by tomorrow"
    result = nlp.process_message(message, sample_user_info)
    assert result["urgency"] >= 0.3  # Base medium urgency
    assert result["urgency"] <= 0.7  # Not high urgency
    
    # Test low urgency
    message = "When you have time, could you look at this?"
    result = nlp.process_message(message, sample_user_info)
    assert result["urgency"] <= 0.3
    
    # Test multiple urgency indicators
    message = "URGENT DEADLINE: Need report ASAP!!!"
    result = nlp.process_message(message, sample_user_info)
    assert result["urgency"] > 0.8  # Should be very high urgency

def test_temporal_context(nlp, sample_user_info):
    """Test extraction of temporal context."""
    # Test specific day
    message = "Schedule the meeting for Tuesday"
    result = nlp.process_message(message, sample_user_info)
    assert result["temporal_context"]["specific_day"] == "tuesday"
    
    # Test timeframe
    message = "Need this done by next week"
    result = nlp.process_message(message, sample_user_info)
    assert result["temporal_context"]["timeframe"] == "next_week"
    
    # Test urgency timeframe
    message = "This is urgent, need it right away"
    result = nlp.process_message(message, sample_user_info)
    assert result["temporal_context"]["timeframe"] == "urgent"

def test_user_context(nlp, sample_user_info):
    """Test user context information."""
    message = "Hello there"
    result = nlp.process_message(message, sample_user_info)
    
    assert result["user_context"]["user_id"] == "U123"
    assert result["user_context"]["user_name"] == "John Doe"
    assert result["user_context"]["is_dm"] == True
    assert "timestamp" in result["user_context"]

def test_error_handling(nlp):
    """Test error handling with invalid inputs."""
    # Test with None message
    result = nlp.process_message(None, {})
    assert result["status"] == "error"
    
    # Test with invalid user_info
    result = nlp.process_message("Hello", None)
    assert result["status"] == "error" 