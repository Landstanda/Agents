import pytest
import asyncio
import yaml
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

@pytest.fixture
def mock_slack_web_client():
    """Mock Slack Web Client."""
    client = AsyncMock()
    client.auth_test = AsyncMock(return_value={"user_id": "U123", "user": "test-bot"})
    client.users_info = AsyncMock(return_value={"user": {"real_name": "Test User"}})
    client.chat_postMessage = AsyncMock()
    return client

@pytest.fixture
def mock_slack_socket_client():
    """Mock Slack Socket Client."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.close = AsyncMock()
    return client

@pytest.fixture
def sample_recipes():
    """Load sample recipes for testing."""
    recipes_path = Path("src/office/cookbook/recipes.yaml")
    with open(recipes_path, 'r') as f:
        return yaml.safe_load(f)

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="Test response"))]
        )
    )
    return client

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def sample_slack_message():
    """Create a sample Slack message."""
    return {
        "type": "message",
        "channel": "C123",
        "user": "U456",
        "text": "<@U123> schedule a meeting with @john tomorrow at 2pm",
        "ts": "1234567890.123"
    }

@pytest.fixture
def sample_nlp_result():
    """Create a sample NLP processing result."""
    return {
        "intent": "schedule_meeting",
        "entities": {
            "time": "tomorrow at 2pm",
            "participants": ["@john"]
        },
        "keywords": ["schedule", "meeting"],
        "urgency": 0.3
    } 