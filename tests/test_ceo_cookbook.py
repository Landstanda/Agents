import pytest
import json
from src.office.executive.ceo import CEO

@pytest.fixture
def ceo():
    """Create a CEO instance for testing."""
    return CEO()

@pytest.mark.asyncio
async def test_ceo_exact_recipe_match(ceo):
    """Test CEO's response when there's an exact recipe match."""
    message = "Can you check my emails for any urgent messages?"
    response = await ceo.consider_request(message)
    
    print("\nCEO Response to exact recipe match:", json.dumps(response, indent=2))
    assert response["status"] == "success"
    assert len(response["matched_recipes"]) > 0
    assert response["confidence"] > 0.7  # Should be high confidence for exact match
    assert "email" in str(response["decision"]).lower()

@pytest.mark.asyncio
async def test_ceo_multiple_recipe_match(ceo):
    """Test CEO's response when multiple recipes might apply."""
    message = "Please check my emails and schedule a team meeting for next Tuesday"
    response = await ceo.consider_request(message)
    
    print("\nCEO Response to multiple recipe match:", json.dumps(response, indent=2))
    assert response["status"] == "success"
    assert len(response["matched_recipes"]) > 1
    assert response["requires_consultation"]  # Should need consultation for complex tasks
    assert isinstance(response["required_ingredients"], list)
    assert any("email" in ingredient.lower() for ingredient in response["required_ingredients"])
    assert any("schedule" in ingredient.lower() for ingredient in response["required_ingredients"])

@pytest.mark.asyncio
async def test_ceo_no_recipe_match(ceo):
    """Test CEO's response when no existing recipe matches."""
    message = "Can you make me a sandwich?"  # Something not in our recipes
    response = await ceo.consider_request(message)
    
    print("\nCEO Response to no recipe match:", json.dumps(response, indent=2))
    assert response["status"] == "success"
    assert response["confidence"] < 0.5  # Should have low confidence
    assert isinstance(response["decision"], str)
    assert len(response.get("matched_recipes", [])) == 0

@pytest.mark.asyncio
async def test_ceo_recipe_combination(ceo):
    """Test CEO's ability to combine recipes for complex requests."""
    message = "Research AI trends and prepare a report for our investors"
    response = await ceo.consider_request(message)
    
    print("\nCEO Response to recipe combination:", json.dumps(response, indent=2))
    assert response["status"] == "success"
    assert len(response["matched_recipes"]) >= 2  # Should match research and document recipes
    assert len(response["required_ingredients"]) >= 3  # Should need multiple ingredients
    assert isinstance(response["decision"], str)
    assert "research" in str(response["decision"]).lower()
    assert "report" in str(response["decision"]).lower() 