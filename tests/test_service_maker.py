import pytest
import asyncio
from pathlib import Path
import yaml
import json
import shutil
from unittest.mock import MagicMock, patch
from src.tools.service_maker import ServiceMaker
from src.tools.nlp import Ticket, TicketStatus

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
async def setup_test_files(tmp_path, sample_services, sample_capabilities, sample_module_capabilities):
    """Set up test files with sample data."""
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
    
    # Create modules directory
    modules_dir = test_dir / "modules"
    modules_dir.mkdir(exist_ok=True)
    
    # Return the result directly
    return {
        'test_dir': test_dir,
        'files': created_files,
        'modules_dir': modules_dir
    }

@pytest.fixture
async def service_maker(setup_test_files):
    """Create a ServiceMaker instance with test configurations."""
    files = await setup_test_files
    test_dir = files['test_dir']
    
    # Create and return the ServiceMaker instance
    maker = ServiceMaker(
        services_path=str(test_dir / "services.yaml"),
        capabilities_path=str(test_dir / "capabilities_index.yaml"),
        module_capabilities_path=str(test_dir / "module_capabilities.yaml"),
        executions_path=str(test_dir / "executions.yaml"),
        modules_path=str(test_dir / "modules")
    )
    return maker

@pytest.fixture
def test_ticket():
    """Create a test ticket."""
    ticket = Ticket(
        original_message="Schedule a meeting with John tomorrow at 2pm",
        channel_id="test-channel",
        user_info={"id": "test-user", "name": "Test User"}
    )
    return ticket

@pytest.mark.asyncio
async def test_service_matching_live_gpt(service_maker, test_ticket):
    """Test live GPT service matching functionality."""
    maker = await service_maker
    
    # Test with a message that should match existing service
    test_ticket.original_message = "Schedule a meeting with John tomorrow at 2pm"
    
    try:
        match_result = await maker._try_service_match(test_ticket)
        
        # Verify response structure
        assert isinstance(match_result, dict)
        assert 'matched' in match_result
        assert 'explanation' in match_result
        
        if match_result['matched']:
            assert 'service_name' in match_result
            assert 'confidence' in match_result
            assert 0 <= match_result['confidence'] <= 1
            
        print(f"Match result: {json.dumps(match_result, indent=2)}")
        
    except Exception as e:
        pytest.fail(f"Live GPT service matching failed: {str(e)}")

@pytest.mark.asyncio
async def test_service_creation_live_gpt(service_maker, test_ticket):
    """Test live GPT service creation functionality."""
    maker = await service_maker
    
    # Test with a novel request
    test_ticket.original_message = "Monitor my website uptime and notify me if it goes down"
    
    try:
        result_ticket = await maker._create_new_service(test_ticket)
        
        # Verify ticket updates
        assert result_ticket.status in [TicketStatus.EXECUTING, TicketStatus.ERROR]
        
        if result_ticket.status == TicketStatus.EXECUTING:
            # Verify created service structure
            assert len(result_ticket.created_services) > 0
            new_service = result_ticket.created_services[-1]
            
            required_fields = ["name", "description", "intent", "triggers", "steps"]
            for field in required_fields:
                assert field in new_service
                
            # Verify steps structure
            for step in new_service['steps']:
                assert 'tool' in step
                assert 'action' in step
                assert 'params' in step
                
            print(f"Created service: {json.dumps(new_service, indent=2)}")
            
    except Exception as e:
        pytest.fail(f"Live GPT service creation failed: {str(e)}")

@pytest.mark.asyncio
async def test_service_recovery_live_gpt(service_maker, test_ticket):
    """Test live GPT service recovery functionality."""
    maker = await service_maker
    
    # Test with a failed service execution
    test_ticket.original_message = "Send an email to team@company.com"
    failure_info = {
        "failed_step": "send_email",
        "error": "SMTP connection failed",
        "successful_steps": [
            {
                "name": "validate_email",
                "result": {"status": "success"}
            }
        ]
    }
    
    try:
        result_ticket = await maker.handle_service_failure(test_ticket, failure_info)
        
        # Verify ticket updates
        assert result_ticket.status in [TicketStatus.EXECUTING, TicketStatus.ERROR]
        
        if result_ticket.status == TicketStatus.EXECUTING:
            # Verify recovery service structure
            assert len(result_ticket.created_services) > 0
            recovery_service = result_ticket.created_services[-1]
            
            required_fields = ["name", "description", "intent", "triggers", "steps"]
            for field in required_fields:
                assert field in recovery_service
                
            # Verify the recovery service has alternative steps
            steps = recovery_service['steps']
            assert len(steps) > 0
            
            print(f"Recovery service: {json.dumps(recovery_service, indent=2)}")
            
    except Exception as e:
        pytest.fail(f"Live GPT service recovery failed: {str(e)}")

@pytest.mark.asyncio
async def test_end_to_end_request_handling(service_maker, test_ticket):
    """Test complete request handling flow."""
    maker = await service_maker
    
    # Test with a completely new request
    test_ticket.original_message = "Create a weekly report of my Google Analytics data"
    
    try:
        # First, try to match with existing services
        match_result = await maker._try_service_match(test_ticket)
        
        if not match_result['matched']:
            # If no match, try to create new service
            result_ticket = await maker._create_new_service(test_ticket)
            
            if result_ticket.status == TicketStatus.EXECUTING:
                new_service = result_ticket.created_services[-1]
                print(f"New service created: {json.dumps(new_service, indent=2)}")
                
                # Verify service structure and content
                assert 'steps' in new_service
                assert len(new_service['steps']) > 0
                
                # Check if steps use available tools
                for step in new_service['steps']:
                    assert step['tool'] in maker.module_capabilities.get('modules', {})
                    
    except Exception as e:
        pytest.fail(f"End-to-end request handling failed: {str(e)}")

@pytest.mark.asyncio
async def test_service_validation(service_maker):
    """Test service validation functionality."""
    maker = await service_maker
    
    # Test valid service
    valid_service = {
        "name": "test_service",
        "description": "Test service",
        "intent": "test",
        "triggers": ["test trigger"],
        "steps": [
            {
                "tool": "calendar",
                "action": "check_availability",
                "params": {
                    "time": "{time}"
                }
            }
        ]
    }
    
    assert maker._validate_service(valid_service)
    
    # Test invalid service (missing required fields)
    invalid_service = {
        "name": "test_service",
        "description": "Test service"
    }
    
    assert not maker._validate_service(invalid_service)

@pytest.mark.asyncio
async def test_prompt_generation(service_maker, test_ticket):
    """Test prompt generation for different scenarios."""
    maker = await service_maker
    
    # Test matching prompt
    matching_prompt = maker._create_matching_prompt(test_ticket)
    assert test_ticket.original_message in matching_prompt
    assert "Available services" in matching_prompt
    
    # Test creation prompt
    creation_prompt = maker._create_service_prompt(test_ticket)
    assert test_ticket.original_message in creation_prompt
    assert "Available capabilities and patterns" in creation_prompt
    assert "Available module specifications" in creation_prompt
    
    # Test recovery prompt
    failure_info = {"error": "Test error"}
    recovery_prompt = maker._create_recovery_prompt(test_ticket, failure_info)
    assert test_ticket.original_message in recovery_prompt
    assert "Failed service execution" in recovery_prompt
    assert "Create an alternative service" in recovery_prompt 