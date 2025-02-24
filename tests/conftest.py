import pytest
import os
import yaml
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from openai import AsyncOpenAI
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
import sys
import asyncio
import logging
from typing import Dict, Any
from src.core.orchestrator import RequestOrchestrator
from src.utils.flow_logger import FlowLogger
from src.models import Ticket, TicketStatus

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

# Add at the top of the file, after imports
pytest_plugins = ('pytest_asyncio',)

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

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
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

@pytest.fixture
def web_client():
    """Create a mock web client"""
    mock = AsyncMock()
    mock.ssl = None
    return mock

@pytest.fixture
def socket_client():
    """Create a mock socket client"""
    mock = AsyncMock()
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    mock.send_socket_mode_response = AsyncMock()
    return mock

@pytest.fixture
def flow_logger():
    """Create a mock flow logger"""
    mock = AsyncMock()
    mock.setup = AsyncMock()
    mock.log_event = AsyncMock()
    mock.info = AsyncMock()
    mock.error = AsyncMock()
    mock.debug = AsyncMock()
    mock.warning = AsyncMock()
    return mock

@pytest.fixture
def service_analyzer():
    """Create a mock service analyzer"""
    mock = AsyncMock()
    mock.analyze_request = AsyncMock()
    mock.initialize = AsyncMock()
    mock.info = AsyncMock()
    mock.error = AsyncMock()
    return mock

@pytest.fixture
def service_agent():
    """Create a mock service agent"""
    mock = AsyncMock()
    mock.execute_service = AsyncMock()
    mock.initialize = AsyncMock()
    mock.info = AsyncMock()
    mock.error = AsyncMock()
    return mock

@pytest.fixture
def message_maker():
    """Create a mock message maker"""
    mock = AsyncMock()
    mock.create_success_message = AsyncMock()
    mock.create_error_message = AsyncMock()
    mock.create_input_request_message = AsyncMock()
    mock.send_message = AsyncMock()
    mock.send_error_message = AsyncMock()
    mock.info = AsyncMock()
    mock.error = AsyncMock()
    return mock

@pytest.fixture
async def orchestrator(service_agent, service_analyzer, message_maker, flow_logger):
    """Create a test orchestrator instance"""
    orchestrator_instance = RequestOrchestrator(flow_logger=flow_logger)
    
    # Set components directly
    orchestrator_instance.agent = service_agent
    orchestrator_instance.service_analyzer = service_analyzer
    orchestrator_instance.message_maker = message_maker
    
    # Initialize
    await orchestrator_instance.initialize()
    yield orchestrator_instance

@pytest.fixture
def slack_token():
    """Provide a test Slack bot token"""
    return "xoxb-test-token"

@pytest.fixture
def app_token():
    """Provide a test Slack app token"""
    return "xapp-test-token"

@pytest.fixture
async def assistant(slack_token, app_token, web_client, socket_client, flow_logger, orchestrator):
    """Create a test assistant instance"""
    assistant_instance = OfficeAssistant(
        slack_token=slack_token,
        app_token=app_token
    )
    assistant_instance.web_client = web_client
    assistant_instance.socket_client = socket_client
    assistant_instance.flow_logger = flow_logger
    assistant_instance.orchestrator = orchestrator
    assistant_instance.bot_user_id = "U123BOT"
    
    await assistant_instance.setup()
    yield assistant_instance
    await assistant_instance.stop()

def _update_ticket_for_test(ticket: Ticket, status: TicketStatus) -> Ticket:
    """Helper function to update ticket status for testing"""
    ticket.status = status
    return ticket 