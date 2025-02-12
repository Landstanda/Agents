import pytest
import os
from pathlib import Path
import yaml
from src.tools.service_maker import ServiceMaker

@pytest.fixture
def service_maker(mock_openai, test_tools_dir, tmp_path):
    """Create a ServiceMaker instance with mocked dependencies."""
    services_file = tmp_path / "services.yaml"
    maker = ServiceMaker(services_path=str(services_file), tools_path=str(test_tools_dir))
    maker.openai = mock_openai
    return maker

@pytest.mark.asyncio
async def test_create_service_success(service_maker):
    """Test successful service creation."""
    # Update mock response to return valid YAML
    service_maker.openai.chat.completions.create.return_value.choices[0].message.content = """
name: Test Service
description: A test service
intent: test_intent
triggers:
  - test this
  - run test
required_entities:
  - test_param
steps:
  - tool: test_tool
    action: test_action
    params:
      param1: "{test_param}"
success_criteria:
  - Test completed successfully
"""
    
    request = "test this with param1"
    context = {
        "nlp_result": {
            "intent": "test_intent",
            "entities": {
                "test_param": "test_value"
            }
        }
    }
    
    result = await service_maker.create_service(request, context)
    
    assert result["status"] == "success"
    assert result["service"]["name"] == "Test Service"
    assert result["service"]["intent"] == "test_intent"
    assert len(result["service"]["steps"]) > 0
    assert result["service"]["steps"][0]["tool"] == "test_tool"

@pytest.mark.asyncio
async def test_create_service_gpt_failure(service_maker):
    """Test handling GPT failure."""
    service_maker.openai.chat.completions.create.side_effect = Exception("GPT error")
    
    request = "test request"
    context = {}
    
    result = await service_maker.create_service(request, context)
    
    assert result["status"] == "error"
    assert "GPT error" in result["error"]

@pytest.mark.asyncio
async def test_create_service_invalid_yaml(service_maker):
    """Test handling invalid YAML from GPT."""
    # Make GPT return invalid YAML
    service_maker.openai.chat.completions.create.return_value.choices[0].message.content = """
    invalid:
      - yaml:
        content
    """
    
    request = "test request"
    context = {}
    
    result = await service_maker.create_service(request, context)
    
    assert result["status"] == "error"
    assert "YAML" in result["error"]

@pytest.mark.asyncio
async def test_create_service_missing_fields(service_maker):
    """Test handling service with missing required fields."""
    # Make GPT return incomplete service
    service_maker.openai.chat.completions.create.return_value.choices[0].message.content = """
name: Test Service
description: A test service
# Missing required fields: intent, triggers, steps
"""
    
    request = "test request"
    context = {}
    
    result = await service_maker.create_service(request, context)
    
    assert result["status"] == "error"
    assert "missing required fields" in result["error"].lower()

@pytest.mark.asyncio
async def test_save_service(service_maker):
    """Test saving a service to file."""
    service = {
        "name": "Test Service",
        "description": "A test service",
        "intent": "test_intent",
        "triggers": ["test this"],
        "required_entities": ["test_param"],
        "steps": [
            {
                "tool": "test_tool",
                "action": "test_action",
                "params": {"param1": "value1"}
            }
        ],
        "success_criteria": ["Test completed"]
    }
    
    await service_maker._save_service(service)
    
    # Verify service was saved
    assert service_maker.services_path.exists()
    with open(service_maker.services_path) as f:
        saved_services = yaml.safe_load(f)
    
    assert "Test Service" in saved_services
    assert saved_services["Test Service"] == service 