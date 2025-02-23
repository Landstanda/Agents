import pytest
import os
import yaml
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from openai import AsyncOpenAI
from slack_sdk.web.async_client import AsyncWebClient
import sys
import asyncio
import logging
from typing import Dict, Any

# Add src directory to Python path
src_path = str(Path(__file__).parent.parent / 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Add tests directory to Python path
tests_path = str(Path(__file__).parent)
if tests_path not in sys.path:
    sys.path.insert(0, tests_path)

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Test paths
TEST_ROOT = Path(__file__).parent
WORKSPACE_ROOT = TEST_ROOT.parent
TEST_DATA_DIR = TEST_ROOT / 'fixtures'
TEST_SERVICES_FILE = TEST_DATA_DIR / 'test_services.yaml'

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

@pytest.fixture(scope='session')
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope='session')
def test_data_dir():
    """Provide test data directory."""
    return TEST_DATA_DIR

@pytest.fixture(scope='session')
def workspace_root():
    """Provide workspace root directory."""
    return WORKSPACE_ROOT

@pytest.fixture(scope='session')
def test_services_file():
    """Provide test services file path."""
    return TEST_SERVICES_FILE

@pytest.fixture(autouse=True)
async def setup_teardown():
    """Setup and teardown for each test."""
    # Setup
    logging.info("Setting up test environment")
    
    yield
    
    # Teardown
    logging.info("Cleaning up test environment")

@pytest.fixture
def mock_tool_response() -> Dict[str, Any]:
    """Provide a mock tool response."""
    return {
        'success': True,
        'data': {
            'result': 'test_result',
            'metadata': {
                'timestamp': '2024-02-22T12:00:00Z'
            }
        }
    }

@pytest.fixture
def mock_service_response() -> Dict[str, Any]:
    """Provide a mock service response."""
    return {
        'status': 'success',
        'results': [
            {
                'step': 'step1',
                'success': True,
                'data': {'key': 'value1'}
            },
            {
                'step': 'step2',
                'success': True,
                'data': {'key': 'value2'}
            }
        ]
    }

@pytest.fixture
def mock_error_response() -> Dict[str, Any]:
    """Provide a mock error response."""
    return {
        'status': 'error',
        'error': 'Test error message',
        'error_type': 'test_error',
        'step': 'failed_step'
    }

# Add test-specific environment variables
@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv('TEST_MODE', 'true')
    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
    
# Configure pytest-asyncio
def pytest_configure(config):
    """Configure pytest-asyncio for async tests."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    ) 