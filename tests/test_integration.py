import pytest
import asyncio
from pathlib import Path
import yaml
import json
import shutil
import os
from dotenv import load_dotenv
from unittest.mock import MagicMock, patch
from src.tools.nlp import NLPAnalyzer, Ticket, TicketStatus
from src.tools.service_maker import ServiceMaker
from src.tools.agent import Agent
from src.tools.message_maker import MessageMaker
import logging

# Load environment variables from .env file
load_dotenv()

# Check required environment variables
required_env_vars = ['OPENAI_API_KEY', 'SLACK_BOT_TOKEN']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    pytest.skip(f"Missing required environment variables: {', '.join(missing_vars)}", allow_module_level=True)

@pytest.fixture(scope="session", autouse=True)
def check_env_vars():
    """Ensure all required environment variables are set."""
    missing = [var for var in required_env_vars if not os.getenv(var)]
    if missing:
        pytest.fail(f"Missing required environment variables: {', '.join(missing)}")

@pytest.fixture
def sample_capabilities():
    """Sample capabilities for testing."""
    return {
        "direct_capabilities": {
            "calendar_management": {
                "module": "google_calendar",
                "description": "Calendar operations and scheduling"
            },
            "email_management": {
                "modules": ["email_reader", "email_sender"],
                "description": "Email operations"
            }
        },
        "module_suites": {
            "calendar": {
                "capabilities": [
                    "event_scheduling",
                    "availability_checking"
                ]
            }
        },
        "task_chains": {
            "schedule_meeting": {
                "steps": [
                    "check_availability",
                    "create_event",
                    "send_invites"
                ]
            }
        }
    }

@pytest.fixture
def sample_module_capabilities():
    """Sample module capabilities for testing."""
    return {
        "modules": {
            "calendar": {
                "operations": {
                    "check_availability": {
                        "required_params": ["time", "date"]
                    },
                    "create_event": {
                        "required_params": ["summary", "start_time", "end_time"]
                    }
                }
            },
            "email": {
                "operations": {
                    "send_email": {
                        "required_params": ["to", "subject", "body"]
                    }
                }
            }
        }
    }

@pytest.fixture
def sample_services():
    """Sample services for testing."""
    return {
        "schedule_meeting": {
            "name": "schedule_meeting",
            "description": "Schedule a meeting with specified participants",
            "intent": "schedule_meeting",
            "triggers": [
                "schedule a meeting",
                "set up a meeting",
                "arrange a meeting"
            ],
            "required_entities": [
                "participants",
                "time",
                "date"
            ],
            "steps": [
                {
                    "tool": "calendar",
                    "action": "check_availability",
                    "params": {
                        "time": "{time}",
                        "date": "{date}"
                    }
                }
            ]
        }
    }

@pytest.fixture
def mock_calendar_module():
    """Create a mock calendar module."""
    calendar_code = '''
class Calendar:
    async def check_availability(self, time, date):
        return {"available": True, "conflicts": []}
        
    async def create_event(self, summary, start_time, end_time, **kwargs):
        return {
            "event_id": "test_event_123",
            "status": "created",
            "details": {
                "summary": summary,
                "start": start_time,
                "end": end_time
            }
        }
'''
    return ("calendar.py", calendar_code)

@pytest.fixture
def mock_email_module():
    """Create a mock email module."""
    email_code = '''
class Email:
    async def send_email(self, to, subject, body):
        return {
            "status": "sent",
            "message_id": "test_email_123",
            "recipients": to
        }
'''
    return ("email.py", email_code)

@pytest.fixture(scope="function")
async def test_paths(tmp_path, sample_services, sample_capabilities, 
                    sample_module_capabilities, mock_calendar_module,
                    mock_email_module):
    """Set up test files and mock modules."""
    # Create test directories
    test_dir = tmp_path / "tests" / "fixtures"
    test_dir.mkdir(parents=True)
    
    # Create all necessary files
    files = {
        'services.yaml': sample_services,
        'capabilities_index.yaml': sample_capabilities,
        'module_capabilities.yaml': sample_module_capabilities,
        'executions.yaml': {}
    }
    
    created_files = {}
    for filename, content in files.items():
        file_path = test_dir / filename
        with open(file_path, 'w') as f:
            yaml.safe_dump(content, f)
        created_files[filename] = file_path
    
    # Create and populate modules directory
    modules_dir = test_dir / "modules"
    modules_dir.mkdir(exist_ok=True)
    
    # Write mock modules
    mock_modules = [mock_calendar_module, mock_email_module]
    for module_name, module_code in mock_modules:
        module_path = modules_dir / module_name
        with open(module_path, 'w') as f:
            f.write(module_code)
    
    return {
        'test_dir': test_dir,
        'files': created_files,
        'modules_dir': modules_dir
    }

@pytest.fixture
def mock_slack_client():
    """Create a mock Slack client."""
    class MockSlackClient:
        async def chat_postMessage(self, channel, text, thread_ts=None):
            return {
                'ok': True,
                'message': {
                    'text': text,
                    'ts': '1234567890.123456'
                }
            }
    return MockSlackClient()

@pytest.fixture(scope="function")
async def test_env(test_paths, mock_slack_client):
    """Create test environment with all necessary components."""
    paths = await test_paths
    
    # Create instances
    analyzer = await NLPAnalyzer.create(
        services_path=str(paths['test_dir'] / "services.yaml")
    )
    
    maker = ServiceMaker(
        services_path=str(paths['test_dir'] / "services.yaml"),
        capabilities_path=str(paths['test_dir'] / "capabilities_index.yaml"),
        module_capabilities_path=str(paths['test_dir'] / "module_capabilities.yaml"),
        executions_path=str(paths['test_dir'] / "executions.yaml"),
        modules_path=str(paths['test_dir'] / "modules")
    )
    # Using real OpenAI client
    
    agent_instance = Agent(
        executions_path=str(paths['test_dir'] / "executions.yaml"),
        services_path=str(paths['test_dir'] / "services.yaml"),
        tools_path=str(paths['test_dir'] / "modules")
    )
    
    message_maker = MessageMaker(use_mock=False)
    message_maker.slack = mock_slack_client
    # Using real OpenAI client for message_maker
    
    return {
        'analyzer': analyzer,
        'maker': maker,
        'agent': agent_instance,
        'message_maker': message_maker,
        'using_mock': False
    }

@pytest.fixture
async def nlp_analyzer(test_paths):
    """Create NLPAnalyzer instance with test configurations."""
    paths = await test_paths
    analyzer = await NLPAnalyzer.create(
        services_path=str(paths['test_dir'] / "services.yaml")
    )
    return analyzer

@pytest.fixture
async def service_maker(test_paths):
    """Create ServiceMaker instance with test configurations."""
    paths = await test_paths
    maker = ServiceMaker(
        services_path=str(paths['test_dir'] / "services.yaml"),
        capabilities_path=str(paths['test_dir'] / "capabilities_index.yaml"),
        module_capabilities_path=str(paths['test_dir'] / "module_capabilities.yaml"),
        executions_path=str(paths['test_dir'] / "executions.yaml"),
        modules_path=str(paths['test_dir'] / "modules")
    )
    return maker

@pytest.fixture
async def agent(test_paths):
    """Create Agent instance with test configurations."""
    paths = await test_paths
    agent_instance = Agent(
        executions_path=str(paths['test_dir'] / "executions.yaml"),
        services_path=str(paths['test_dir'] / "services.yaml"),
        tools_path=str(paths['test_dir'] / "modules")
    )
    return agent_instance

@pytest.fixture
def message_maker():
    """Create MessageMaker instance."""
    return MessageMaker()

@pytest.mark.asyncio
async def test_end_to_end_existing_service(test_env):
    """Test end-to-end flow with an existing service."""
    env = await test_env
    
    # Simulate incoming Slack message
    message = "Schedule a meeting with John tomorrow at 2pm"
    user_info = {"id": "test-user", "name": "Test User"}
    
    try:
        # Step 1: Create and analyze ticket
        ticket = await env['analyzer'].analyze_message(message, user_info)
        assert ticket.status in [TicketStatus.EXECUTING, TicketStatus.ANALYZING]
        
        # Step 2: Try to match with existing service
        ticket = await env['maker'].handle_new_request(ticket)
        assert ticket.service is not None
        
        # Step 3: Execute the service
        execution_result = await env['agent'].execute_service(ticket)
        assert execution_result['status'] == 'success'
        
        # Step 4: Generate response
        await env['message_maker'].send_message(ticket)
        assert len(ticket.messages) > 1
        
    except Exception as e:
        pytest.fail(f"End-to-end test failed: {str(e)}")

@pytest.mark.asyncio
async def test_end_to_end_new_service(test_env, caplog):
    """Test end-to-end flow with a new service creation."""
    env = await test_env
    
    # Set log level to INFO to capture detailed logs
    caplog.set_level(logging.INFO)
    
    # Simulate incoming Slack message for a novel request
    message = "Monitor my website uptime and notify me if it goes down"
    user_info = {"id": "test-user", "name": "Test User"}
    
    try:
        # Step 1: Create and analyze ticket
        ticket = await env['analyzer'].analyze_message(message, user_info)
        assert ticket.status == TicketStatus.SERVICE_CREATION
        
        # Step 2: Create new service
        ticket = await env['maker'].handle_new_request(ticket)
        
        # Print captured logs
        print("\nService Creation Logs:")
        for record in caplog.records:
            if record.levelname in ['INFO', 'ERROR']:
                print(f"{record.levelname}: {record.message}")
        
        assert ticket.status == TicketStatus.EXECUTING
        assert len(ticket.created_services) > 0
        
        # Step 3: Execute the new service
        execution_result = await env['agent'].execute_service(ticket)
        assert execution_result['status'] == 'success'
        
        # Step 4: Generate response
        await env['message_maker'].send_message(ticket)
        assert len(ticket.messages) > 1
        
    except Exception as e:
        # Print logs even on failure
        print("\nService Creation Logs (on failure):")
        for record in caplog.records:
            if record.levelname in ['INFO', 'ERROR']:
                print(f"{record.levelname}: {record.message}")
        pytest.fail(f"End-to-end test failed: {str(e)}")

@pytest.mark.asyncio
async def test_end_to_end_error_recovery(test_env):
    """Test end-to-end flow with error recovery."""
    env = await test_env
    
    # Simulate incoming Slack message
    message = "Send an email to team@company.com"
    user_info = {"id": "test-user", "name": "Test User"}
    
    try:
        # Step 1: Create and analyze ticket
        ticket = await env['analyzer'].analyze_message(message, user_info)
        
        # Step 2: Create new service (since it doesn't exist)
        ticket = await env['maker'].handle_new_request(ticket)
        
        # Step 3: Simulate a failure in execution
        execution_result = {
            'status': 'error',
            'error': 'SMTP connection failed',
            'partial_results': [
                {
                    'status': 'success',
                    'tool': 'email',
                    'action': 'validate_email',
                    'result': {'valid': True}
                }
            ]
        }
        
        # Step 4: Attempt recovery
        ticket = await env['maker'].handle_service_failure(ticket, execution_result)
        assert ticket.status == TicketStatus.EXECUTING
        
        # Step 5: Execute recovery service
        recovery_result = await env['agent'].execute_service(ticket)
        assert recovery_result['status'] == 'success'
        
        # Step 6: Generate response
        await env['message_maker'].send_message(ticket)
        assert len(ticket.messages) > 1
        
    except Exception as e:
        pytest.fail(f"End-to-end test failed: {str(e)}")

@pytest.mark.asyncio
async def test_end_to_end_missing_info(test_env):
    """Test end-to-end flow with missing information handling."""
    env = await test_env
    
    # Simulate incoming Slack message with missing info
    message = "Schedule a meeting"
    user_info = {"id": "test-user", "name": "Test User"}
    
    try:
        # Step 1: Create and analyze ticket
        ticket = await env['analyzer'].analyze_message(message, user_info)
        assert ticket.status == TicketStatus.WAITING_INPUT
        assert len(ticket.missing_entities) > 0
        
        # Step 2: Generate response requesting missing info
        await env['message_maker'].send_message(ticket)
        assert len(ticket.messages) > 1
        
        # Step 3: Simulate user providing missing info
        follow_up_message = "tomorrow at 2pm with John"
        updated_ticket = await env['analyzer'].analyze_message(follow_up_message, user_info, ticket)
        assert len(updated_ticket.missing_entities) < len(ticket.missing_entities)
        
    except Exception as e:
        pytest.fail(f"End-to-end test failed: {str(e)}") 