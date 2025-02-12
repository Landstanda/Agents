import pytest
import os
import yaml
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from openai import AsyncOpenAI
from slack_sdk.web.async_client import AsyncWebClient

@pytest.fixture
def mock_openai():
    """Mock OpenAI client with predefined responses."""
    mock_client = MagicMock()
    
    # Mock chat completion response
    mock_completion = AsyncMock()
    mock_completion.choices = [
        MagicMock(
            message=MagicMock(
                content="""
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
                      param1: value1
                success_criteria:
                  - Test completed
                """
            )
        )
    ]
    
    # Set up the chat completions structure
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
    
    return mock_client

@pytest.fixture
def mock_slack():
    """Mock Slack client."""
    mock_client = AsyncMock(spec=AsyncWebClient)
    mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})
    return mock_client

@pytest.fixture
def test_services_file(tmp_path):
    """Create a temporary services file for testing."""
    services = {
        "Test Service": {
            "name": "Test Service",
            "intent": "test_intent",
            "description": "A test service",
            "triggers": ["test this", "run test"],
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
    }
    
    services_file = tmp_path / "services.yaml"
    with open(services_file, "w") as f:
        yaml.safe_dump(services, f)
    
    return services_file

@pytest.fixture
def test_tools_dir(tmp_path):
    """Create a temporary tools directory with test tools."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    
    # Create a test tool file
    test_tool = tools_dir / "test_tool.py"
    with open(test_tool, "w") as f:
        f.write("""
class TestTool:
    \"\"\"A test tool for testing.\"\"\"
    
    async def test_action(self, param1):
        return {"status": "success", "result": f"Test action completed with {param1}"}
""")
    
    return tools_dir 