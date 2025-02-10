import pytest
from src.office.cookbook.cookbook_manager import CookbookManager
from typing import Dict, Any

@pytest.fixture
def cookbook():
    """Initialize cookbook with test recipes."""
    manager = CookbookManager()
    # Add test recipes
    test_recipes = {
        "Document Management": {
            "name": "Document Management",
            "intent": "document",
            "description": "Create and manage documents",
            "steps": [
                {"action": "create_document", "params": {"type": "{doc_type}"}},
                {"action": "add_content", "params": {"content": "{content}"}}
            ],
            "required_entities": ["doc_type"],
            "keywords": ["document", "create", "write", "record"],
            "common_triggers": ["create a document", "write documentation"],
            "success_criteria": ["Document created", "Content added"]
        },
        "Research Report": {
            "name": "Research Report",
            "intent": "research",
            "description": "Research a topic and create a detailed report",
            "steps": [
                {"action": "search_info", "params": {"topic": "{topic}"}},
                {"action": "analyze_results", "params": {"depth": "detailed"}},
                {"action": "create_summary", "params": {"format": "report"}}
            ],
            "required_entities": ["topic"],
            "keywords": ["research", "analyze", "report", "investigate"],
            "common_triggers": ["research about", "analyze topic"],
            "success_criteria": ["Research completed", "Report created"]
        },
        "Meeting Scheduler": {
            "name": "Meeting Scheduler",
            "intent": "schedule_meeting",
            "description": "Schedule a meeting with participants",
            "steps": [
                {"action": "check_availability", "params": {"time": "{time}", "participants": "{participants}"}},
                {"action": "create_meeting", "params": {"time": "{time}", "participants": "{participants}"}}
            ],
            "required_entities": ["time", "participants"],
            "keywords": ["schedule", "meeting", "calendar", "invite"],
            "common_triggers": ["schedule a meeting", "set up a meeting"],
            "success_criteria": ["Meeting scheduled", "Invites sent"]
        }
    }
    manager.recipes = test_recipes
    return manager

@pytest.fixture
def sample_nlp_result():
    return {
        "intent": "schedule_meeting",
        "all_intents": ["scheduling"],
        "entities": {
            "time": "2pm",
            "participants": ["@john"]
        },
        "urgency": 0.3
    }

@pytest.mark.asyncio
async def test_exact_recipe_match(cookbook, sample_nlp_result):
    """Test matching a recipe with exact intent match."""
    recipe = await cookbook.find_matching_recipe(sample_nlp_result)
    assert recipe is not None
    assert recipe["intent"] == "schedule_meeting"
    assert "required_entities" in recipe
    assert "steps" in recipe

@pytest.mark.asyncio
async def test_fuzzy_recipe_match(cookbook):
    """Test matching a recipe with similar but not exact intent."""
    nlp_result = {
        "intent": "create_report",
        "all_intents": ["document"],
        "entities": {},
        "keywords": ["create", "report", "document"]
    }
    recipe = await cookbook.find_matching_recipe(nlp_result)
    assert recipe is not None
    assert recipe["name"] == "Document Management"
    assert "steps" in recipe

@pytest.mark.asyncio
async def test_no_matching_recipe(cookbook):
    """Test behavior when no matching recipe is found."""
    nlp_result = {
        "intent": "unknown_task",
        "all_intents": ["unknown"],
        "entities": {},
        "keywords": ["something", "random"]
    }
    recipe = await cookbook.find_matching_recipe(nlp_result)
    assert recipe is None

@pytest.mark.asyncio
async def test_recipe_with_missing_entities(cookbook):
    """Test matching a recipe when required entities are missing."""
    nlp_result = {
        "intent": "schedule_meeting",
        "all_intents": ["scheduling"],
        "entities": {
            "time": "2pm"
            # Missing 'participants' entity
        },
        "urgency": 0.3
    }
    recipe = await cookbook.find_matching_recipe(nlp_result)
    assert recipe is not None
    assert recipe["intent"] == "schedule_meeting"
    assert "participants" in recipe["required_entities"]

@pytest.mark.asyncio
async def test_multiple_matching_recipes(cookbook):
    """Test behavior when multiple recipes could match the request."""
    nlp_result = {
        "intent": "research",
        "all_intents": ["research", "document"],
        "entities": {},
        "keywords": ["research", "report", "analyze"]
    }
    recipe = await cookbook.find_matching_recipe(nlp_result)
    assert recipe is not None
    # Should choose the most specific match (Research Report over Document Management)
    assert recipe["name"] == "Research Report"

@pytest.mark.asyncio
async def test_recipe_validation(cookbook):
    """Test that recipes have all required fields."""
    for recipe_name in cookbook.list_recipes():
        recipe = cookbook.get_recipe(recipe_name)
        assert "name" in recipe
        assert "intent" in recipe
        assert "steps" in recipe
        assert "required_entities" in recipe
        assert isinstance(recipe["steps"], list)
        assert isinstance(recipe["required_entities"], list) 