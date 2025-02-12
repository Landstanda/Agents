import pytest
from src.office.executive.ceo import CEO

@pytest.fixture
def ceo():
    return CEO()

@pytest.mark.asyncio
async def test_ceo_initialization(ceo):
    """Test that CEO initializes correctly"""
    status = ceo.get_status()
    assert status["name"] == "Michael"
    assert status["title"] == "CEO"
    assert status["status"] == "online"
    assert status["ready"] is True

@pytest.mark.asyncio
async def test_ceo_consider_request(ceo):
    """Test that CEO can process a basic request"""
    message = "Can you help me with my email?"
    response = await ceo.consider_request(message)
    
    assert response["status"] == "success"
    assert "received the request" in response["decision"]
    assert response["confidence"] > 0
    assert isinstance(response["requires_consultation"], bool)
    assert response["notes"] is not None

@pytest.mark.asyncio
async def test_ceo_error_handling(ceo):
    """Test CEO's error handling"""
    # Force an error by passing None
    response = await ceo.consider_request(None)
    
    assert response["status"] == "error"
    assert response["decision"] is None
    assert response["confidence"] == 0.0
    assert "Error occurred" in response["notes"] 