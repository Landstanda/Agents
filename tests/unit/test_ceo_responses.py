import pytest
import json
from src.office.executive.ceo import CEO

@pytest.fixture
def ceo():
    """Create a CEO instance for testing."""
    return CEO()

@pytest.mark.asyncio
async def test_ceo_email_request(ceo):
    """Test CEO's response to an email-related request"""
    message = "Can you check my emails and let me know if there are any urgent messages?"
    response = await ceo.consider_request(message)
    
    print("\nCEO Response to email request:", json.dumps(response, indent=2))
    assert response["status"] == "success"
    assert isinstance(response["decision"], str)
    assert isinstance(response["confidence"], float)
    assert isinstance(response["requires_consultation"], bool)

@pytest.mark.asyncio
async def test_ceo_research_request(ceo):
    """Test CEO's response to a research request"""
    message = "I need to research the latest trends in AI technology for our next project"
    response = await ceo.consider_request(message)
    
    print("\nCEO Response to research request:", json.dumps(response, indent=2))
    assert response["status"] == "success"
    assert isinstance(response["decision"], str)
    assert isinstance(response["confidence"], float)
    assert isinstance(response["requires_consultation"], bool)

@pytest.mark.asyncio
async def test_ceo_complex_request(ceo):
    """Test CEO's response to a complex multi-part request"""
    message = """I need help with three things:
    1. Schedule a team meeting for next week
    2. Prepare a summary of our Q4 sales data
    3. Send an update to our investors
    """
    response = await ceo.consider_request(message)
    
    print("\nCEO Response to complex request:", json.dumps(response, indent=2))
    assert response["status"] == "success"
    assert isinstance(response["decision"], str)
    assert isinstance(response["confidence"], float)
    assert isinstance(response["requires_consultation"], bool)

@pytest.mark.asyncio
async def test_ceo_invalid_request(ceo):
    """Test CEO's response to an invalid request"""
    message = None
    response = await ceo.consider_request(message)
    
    print("\nCEO Response to invalid request:", json.dumps(response, indent=2))
    assert response["status"] == "error"
    assert response["decision"] is None
    assert response["confidence"] == 0.0
    assert not response["requires_consultation"] 