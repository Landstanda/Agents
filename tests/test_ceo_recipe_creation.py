import pytest
from unittest.mock import Mock, patch, mock_open
import yaml
from datetime import datetime
import os
from dotenv import load_dotenv
from src.office.executive.ceo import CEO
from src.office.cookbook.cookbook_manager import CookbookManager
from src.office.task.task_manager import TaskManager

# Load environment variables
load_dotenv()

@pytest.fixture
def cookbook_manager():
    return Mock(spec=CookbookManager)

@pytest.fixture
def task_manager():
    return Mock(spec=TaskManager)

@pytest.fixture
def ceo(cookbook_manager, task_manager):
    return CEO(cookbook_manager=cookbook_manager, task_manager=task_manager)

@pytest.fixture
def mock_ingredients():
    return {
        "communication": {
            "email": [
                {
                    "name": "read_email",
                    "description": "Read and process incoming emails",
                    "capabilities": ["Filter emails", "Extract information"]
                }
            ]
        }
    }

@pytest.mark.asyncio
async def test_ceo_initialization(ceo):
    """Test CEO initializes with correct configuration"""
    status = ceo.get_status()
    assert status["name"] == "Michael"
    assert status["title"] == "CEO"
    assert status["status"] == "online"
    assert isinstance(status["ingredients_loaded"], bool)

@pytest.mark.asyncio
async def test_ceo_loads_ingredients(ceo, mock_ingredients):
    """Test CEO can load ingredients file"""
    mock_file = mock_open(read_data=yaml.dump(mock_ingredients))
    with patch("pathlib.Path.exists", return_value=True), \
         patch("builtins.open", mock_file):
        ingredients = ceo._load_ingredients()
        assert ingredients == mock_ingredients
        assert "communication" in ingredients
        assert "email" in ingredients["communication"]

@pytest.mark.asyncio
async def test_ceo_handles_existing_recipe(ceo, cookbook_manager):
    """Test CEO correctly handles requests with existing recipes"""
    # Mock cookbook response for existing recipe
    cookbook_manager.get_recipe.return_value = {
        "status": "success",
        "recipe": {
            "name": "Email Reader",
            "intent": "email_read"
        }
    }
    
    response = await ceo.consider_request(
        "Check my emails",
        context={"nlp_result": {"intent": "email_read"}}
    )
    
    assert response["status"] == "success"
    assert "existing recipe" in response["notes"]
    assert response["confidence"] > 0.8
    assert not response["requires_consultation"]

@pytest.mark.asyncio
async def test_ceo_creates_new_recipe_basic(ceo, cookbook_manager):
    """Test CEO can create a simple recipe with minimal complexity."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not found")
    
    cookbook_manager.get_recipe.return_value = {
        "status": "not_found",
        "recipe": None
    }
    cookbook_manager.add_recipe.return_value = True
    
    response = await ceo.consider_request(
        "Send a daily email summary to my team",
        context={"nlp_result": {"intent": "send_summary"}}
    )
    
    assert response["status"] == "success"
    assert response["recipe"] is not None
    
    # Basic structure validation
    recipe = response["recipe"]
    assert isinstance(recipe, dict)
    assert all(key in recipe for key in [
        "name", "description", "intent", "steps",
        "common_triggers", "required_entities", "success_criteria"
    ])

@pytest.mark.asyncio
async def test_ceo_recipe_steps_validation(ceo, cookbook_manager):
    """Test that created recipe steps are valid and use existing ingredients."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not found")
    
    cookbook_manager.get_recipe.return_value = {
        "status": "not_found",
        "recipe": None
    }
    
    response = await ceo.consider_request(
        "Send a daily email summary to my team",
        context={"nlp_result": {"intent": "send_summary"}}
    )
    
    assert response["status"] == "success"
    recipe = response["recipe"]
    
    # Validate steps structure
    assert isinstance(recipe["steps"], list)
    assert len(recipe["steps"]) > 0
    
    # Validate each step
    for step in recipe["steps"]:
        assert isinstance(step, dict)
        assert "action" in step
        assert "params" in step
        assert isinstance(step["params"], dict)

@pytest.mark.asyncio
async def test_ceo_recipe_metadata(ceo, cookbook_manager):
    """Test that created recipes have correct metadata."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not found")
    
    cookbook_manager.get_recipe.return_value = {
        "status": "not_found",
        "recipe": None
    }
    
    response = await ceo.consider_request(
        "Send a daily email summary to my team",
        context={"nlp_result": {"intent": "send_summary"}}
    )
    
    assert response["status"] == "success"
    recipe = response["recipe"]
    
    # Validate metadata
    assert "created_at" in recipe
    assert "created_by" in recipe
    assert recipe["created_by"] == "ceo"
    assert "version" in recipe
    assert recipe["version"] == "1.0"

@pytest.mark.asyncio
async def test_ceo_recipe_format(ceo, cookbook_manager):
    """Test that created recipes have the correct format for all fields."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not found")
    
    cookbook_manager.get_recipe.return_value = {
        "status": "not_found",
        "recipe": None
    }
    
    response = await ceo.consider_request(
        "Send a daily email summary to my team",
        context={"nlp_result": {"intent": "send_summary"}}
    )
    
    assert response["status"] == "success"
    recipe = response["recipe"]
    
    # Validate field formats
    assert isinstance(recipe["name"], str)
    assert isinstance(recipe["description"], str)
    assert isinstance(recipe["intent"], str)
    assert isinstance(recipe["common_triggers"], list)
    assert all(isinstance(trigger, str) for trigger in recipe["common_triggers"])
    assert isinstance(recipe["required_entities"], list)
    assert all(isinstance(entity, str) for entity in recipe["required_entities"])
    assert isinstance(recipe["success_criteria"], list)
    assert all(isinstance(criterion, str) for criterion in recipe["success_criteria"])

@pytest.mark.asyncio
async def test_ceo_creates_complex_recipe(ceo, cookbook_manager):
    """Test CEO can create complex recipes involving multiple capabilities."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not found")
    
    cookbook_manager.get_recipe.return_value = {
        "status": "not_found",
        "recipe": None
    }
    cookbook_manager.add_recipe.return_value = True
    
    response = await ceo.consider_request(
        "Create a monthly report summarizing all my email communications, calendar events, and project progress from Trello, then share it with my team on Slack",
        context={"nlp_result": {"intent": "create_monthly_summary"}}
    )
    
    assert response["status"] == "success"
    recipe = response["recipe"]
    
    # Validate complex recipe structure
    assert len(recipe["steps"]) >= 4  # Should have multiple steps
    assert any("email" in str(step).lower() for step in recipe["steps"])
    assert any("calendar" in str(step).lower() for step in recipe["steps"])
    assert any("trello" in str(step).lower() for step in recipe["steps"])
    assert any("slack" in str(step).lower() for step in recipe["steps"])

@pytest.mark.asyncio
async def test_ceo_handles_recipe_creation_failure(ceo, cookbook_manager):
    """Test CEO handles recipe creation failures gracefully."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not found")
    
    cookbook_manager.get_recipe.return_value = {
        "status": "not_found",
        "recipe": None
    }
    
    # Test with an impossible/nonsensical request
    response = await ceo.consider_request(
        "Make my computer fly to the moon",
        context={"nlp_result": {"intent": "unknown"}}
    )
    
    assert response["status"] == "error"
    assert response["confidence"] == 0.0
    assert response["requires_consultation"]
    assert "couldn't figure out" in response["decision"].lower()

@pytest.mark.asyncio
async def test_ceo_updates_request_tracker(ceo, cookbook_manager):
    """Test CEO properly updates request tracker with actual recipe creation."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not found")
    
    cookbook_manager.get_recipe.return_value = {
        "status": "not_found",
        "recipe": None
    }
    
    # Create mock request
    mock_request = Mock()
    mock_request.status = "new"
    mock_request.recipe = None
    
    response = await ceo.consider_request(
        "Summarize my weekly meetings",
        context={"nlp_result": {"intent": "create_summary"}},
        request=mock_request
    )
    
    assert response["status"] == "success"
    assert mock_request.status == "processing"
    assert mock_request.recipe is not None
    assert isinstance(mock_request.recipe, dict)
    assert "steps" in mock_request.recipe 