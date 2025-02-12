import pytest
import os
import yaml
from src.tools.nlp import NLPAnalyzer

@pytest.fixture
def nlp_analyzer(tmp_path):
    """Create NLPAnalyzer with test services."""
    services_file = tmp_path / "services.yaml"
    services = {
        "test_service": {
            "name": "Test Service",
            "description": "A test service",
            "intent": "test_intent",
            "triggers": ["test this", "run test"],
            "required_entities": [],  # No required entities for basic test
            "steps": [
                {
                    "tool": "test_tool",
                    "action": "test_action",
                    "params": {"param1": "default"}
                }
            ],
            "success_criteria": ["Test completed"]
        }
    }
    
    # Create services file
    with open(services_file, "w") as f:
        yaml.safe_dump(services, f)
    
    # Create NLPAnalyzer instance
    analyzer = NLPAnalyzer(str(services_file))
    
    # Manually set up lexicon for testing
    analyzer.services_lexicon = {
        "test this": "test_service",
        "run test": "test_service"
    }
    
    return analyzer

@pytest.mark.asyncio
async def test_analyze_message_exact_match(nlp_analyzer):
    """Test analyzing a message with exact intent match."""
    message = "test this"
    user_info = {"id": "U123", "real_name": "Test User"}
    
    result = nlp_analyzer.analyze_message(message, user_info)
    
    assert result["status"] == "matched"
    assert result["service"] == "test_service"
    assert "test_intent" in result["intent"]

@pytest.mark.asyncio
async def test_analyze_message_no_match(nlp_analyzer):
    """Test analyzing a message with no intent match."""
    message = "something completely different"
    user_info = {"id": "U123", "real_name": "Test User"}
    
    result = nlp_analyzer.analyze_message(message, user_info)
    
    assert result["status"] == "unknown"

@pytest.mark.asyncio
async def test_analyze_message_with_entities(nlp_analyzer):
    """Test analyzing a message with entities."""
    message = "test this with test_param=test_value"
    user_info = {"id": "U123", "real_name": "Test User"}
    
    result = nlp_analyzer.analyze_message(message, user_info)
    
    assert result["status"] == "matched"
    assert result["service"] == "test_service"
    assert result["entities"].get("test_param") == "test_value" 