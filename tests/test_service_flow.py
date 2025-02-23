import asyncio
import logging
from src.tools.agent import Agent
from src.models import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import yaml
import os
from pathlib import Path
from src.core.success_evaluator import SuccessEvaluator

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture
def mock_service_def():
    """Create a mock service definition"""
    return {
        "schedule_meeting": {
            "name": "Schedule Meeting",
            "description": "Schedule a meeting using Google Calendar",
            "required_entities": ["time", "date"],
            "optional_entities": ["event_type", "location", "participants", "duration"],
            "steps": [
                {
                    "name": "Authenticate",
                    "tool": "google_auth",
                    "action": "execute",
                    "params": {},
                    "success_criteria": {
                        "type": "all",
                        "conditions": [
                            "response['success'] == True",
                            "response['credentials'] is not None",
                            "response['credentials']['valid'] == True"
                        ],
                        "on_success": {
                            "next_step": "create_event"
                        },
                        "on_failure": {
                            "action": "retry",
                            "max_attempts": 3,
                            "delay_seconds": 1
                        }
                    }
                },
                {
                    "name": "Create Event",
                    "tool": "google_calendar",
                    "action": "create_event",
                    "params": {
                        "operation": "create_event",
                        "summary": "{event_type if event_type else 'Test'} Meeting",
                        "description": "Scheduled via AI Secretary",
                        "start_time": "{date}T{time}:00",
                        "end_time": "{date}T{time[:2]}:{str(int(time[3:5]) + 60 if ':' in time else '00')}:00",
                        "timezone": "America/Los_Angeles",
                        "location": "{location if location else 'Virtual Meeting'}",
                        "attendees": "{participants if participants else []}"
                    },
                    "success_criteria": {
                        "type": "all",
                        "conditions": [
                            "response['success'] == True",
                            "response['event_id'] is not None"
                        ],
                        "on_success": {
                            "next_step": "complete"
                        },
                        "on_failure": {
                            "action": "retry",
                            "max_attempts": 2
                        }
                    }
                }
            ]
        }
    }

@pytest.fixture
def mock_credentials():
    """Create mock Google credentials"""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.expired = False
    mock_creds.refresh_token = True
    mock_creds.token = "test_token"
    mock_creds.token_uri = "test_uri"
    mock_creds.client_id = "test_client_id"
    mock_creds.scopes = ["test_scope"]
    return mock_creds

@pytest.fixture
def ticket():
    """Create a test ticket"""
    ticket = Ticket(
        user_info={"user_id": "test_user", "channel_id": "test_channel"},
        original_message="Schedule a meeting at 2pm tomorrow",
        service="schedule_meeting",
        entities={
            "time": "14:00",
            "date": "2024-02-23",
            "event_type": "Test"  # Add event type
        }
    )
    return ticket

@pytest.mark.asyncio
async def test_complete_service_flow(ticket, mock_service_def, mock_credentials):
    """Test the complete service execution flow"""
    # Mock service file loading
    with patch('src.tools.agent.Agent._load_service_definitions') as mock_load_services, \
         patch('src.tools.agent.Agent.load_services') as mock_load:
        mock_load_services.return_value = mock_service_def
        mock_load.return_value = mock_service_def
        
        # Create agent
        agent = Agent()
        agent.services = mock_service_def  # Set services directly
        await agent.initialize()
        
        # Verify services were loaded
        assert "schedule_meeting" in agent.services, "Service not loaded"
        
        # Mock Google Auth module with detailed response structure
        with patch('src.modules.google_auth.GoogleAuthModule.execute') as mock_auth:
            auth_response = {
                "success": True,
                "credentials": {
                    "valid": True,
                    "expired": False,
                    "has_refresh_token": True,
                    "token": "test_token",
                    "scopes": ["test_scope"],
                    "token_uri": "test_uri",
                    "client_id": "test_client_id"
                }
            }
            mock_auth.return_value = auth_response
            
            # Log expected auth response
            logger.debug(f"Mock auth response structure: {auth_response}")
            
            # Mock Calendar module with detailed response
            with patch('src.modules.google_calendar.GoogleCalendarModule.execute') as mock_calendar:
                calendar_response = {
                    "success": True,
                    "event_id": "test_event_123",
                    "event_details": {
                        "summary": "Test Meeting",
                        "start": {"dateTime": f"{ticket.entities['date']}T{ticket.entities['time']}:00"},
                        "end": {"dateTime": f"{ticket.entities['date']}T{ticket.entities['time']}:00"}
                    }
                }
                mock_calendar.return_value = calendar_response
                
                # Log expected calendar response
                logger.debug(f"Mock calendar response structure: {calendar_response}")
                
                # Execute service
                result = await agent.execute_service(ticket)
                
                # Log actual result
                logger.debug(f"Service execution result: {result}")
                logger.debug(f"Ticket step results: {ticket.step_results}")
                
                # Detailed validation of the execution flow
                assert result["status"] == "success", f"Service failed with result: {result}"
                assert ticket.status == TicketStatus.COMPLETED, f"Unexpected ticket status: {ticket.status}"
                
                # Verify auth step results
                assert "Authenticate" in ticket.step_results, "Missing authentication step results"
                auth_result = ticket.step_results["Authenticate"]
                assert auth_result["success"] is True, f"Auth step failed: {auth_result}"
                assert "credentials" in auth_result, "Missing credentials in auth result"
                assert auth_result["credentials"]["valid"] is True, "Invalid credentials"
                
                # Verify calendar step results
                assert "Create Event" in ticket.step_results, "Missing calendar step results"
                calendar_result = ticket.step_results["Create Event"]
                assert calendar_result["success"] is True, f"Calendar step failed: {calendar_result}"
                assert "event_id" in calendar_result, "Missing event_id in calendar result"
                
                # Verify no errors occurred
                assert not ticket.errors, f"Unexpected errors in ticket: {ticket.errors}"

@pytest.mark.asyncio
async def test_service_auth_failure(ticket, mock_service_def):
    """Test service execution with authentication failure"""
    # Mock service file
    with patch('pathlib.Path.exists', return_value=True):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(mock_service_def)
            
            # Create agent
            agent = Agent()
            await agent.initialize()
            
            # Mock Google Auth module with failure
            with patch('src.modules.google_auth.GoogleAuthModule.execute') as mock_auth:
                mock_auth.return_value = {
                    "success": False,
                    "error": "Authentication failed"
                }
                
                # Execute service
                result = await agent.execute_service(ticket)
                
                # Verify failure handling
                assert result["status"] == "error"
                assert "Authentication failed" in result["error"]
                assert ticket.status == TicketStatus.ERROR
                assert any("Authentication failed" in error["message"] for error in ticket.errors)

@pytest.mark.asyncio
async def test_service_missing_entities(ticket, mock_service_def):
    """Test service execution with missing required entities"""
    # Remove required entities from ticket
    ticket.entities = {}
    
    # Mock service file
    with patch('pathlib.Path.exists', return_value=True):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(mock_service_def)
            
            # Create agent
            agent = Agent()
            await agent.initialize()
            
            # Execute service
            result = await agent.execute_service(ticket)
            
            # Verify entity validation
            assert result["status"] == "error"
            assert "missing_entities" in result
            assert set(result["missing_entities"]) == {"time", "date"}
            assert ticket.status == TicketStatus.WAITING_INPUT

@pytest.mark.asyncio
async def test_response_structure_validation(ticket, mock_service_def):
    """Test the validation of response structure against success criteria"""
    # Get auth step success criteria from service definition
    auth_step = mock_service_def["schedule_meeting"]["steps"][0]
    success_criteria = auth_step["success_criteria"]
    
    # Initialize success evaluator
    evaluator = SuccessEvaluator()
    
    # Create test response
    test_response = {
        "success": True,
        "credentials": {
            "valid": True,
            "expired": False,
            "has_refresh_token": True,
            "scopes": ["https://www.googleapis.com/auth/calendar"]
        }
    }
    
    # Log test data
    logger.debug(f"Test response structure: {test_response}")
    logger.debug(f"Success criteria: {success_criteria}")
    
    # Evaluate success criteria
    result = evaluator.evaluate(success_criteria, test_response)
    
    # Log evaluation result
    logger.debug(f"Evaluation result: {result}")
    
    # Validate evaluation result
    assert result["success"] is True, f"Success evaluation failed: {result}"
    assert result["next_step"] == "create_event", f"Unexpected next step: {result['next_step']}"
    
    # Test with invalid response structure
    invalid_response = {
        "success": True,
        "credentials": None
    }
    
    # Log invalid test data
    logger.debug(f"Invalid response structure: {invalid_response}")
    
    # Evaluate invalid response
    invalid_result = evaluator.evaluate(success_criteria, invalid_response)
    
    # Log invalid evaluation result
    logger.debug(f"Invalid evaluation result: {invalid_result}")
    
    # Validate failure handling
    assert invalid_result["success"] is False, "Invalid response should fail evaluation"
    assert invalid_result["action"] == "retry", "Invalid response should trigger retry"

@pytest.mark.asyncio
async def test_event_type_parameter_handling(ticket, mock_service_def):
    """Test handling of event type parameter in calendar event creation"""
    # Create agent
    agent = Agent()
    await agent.initialize()
    
    # Update ticket with event type
    ticket.entities["event_type"] = "Dinner"  # Add event type explicitly
    
    # Mock auth module
    with patch('src.modules.google_auth.GoogleAuthModule.execute') as mock_auth:
        auth_response = {
            "success": True,
            "credentials": {
                "valid": True,
                "expired": False,
                "has_refresh_token": True,
                "scopes": ["https://www.googleapis.com/auth/calendar"]
            }
        }
        mock_auth.return_value = auth_response
        
        # Mock calendar module
        with patch('src.modules.google_calendar.GoogleCalendarModule.execute') as mock_calendar:
            # Log the parameters being used
            logger.debug(f"Ticket entities: {ticket.entities}")
            
            calendar_response = {
                "success": True,
                "event_id": "test_event_123",
                "event_details": {
                    "summary": f"{ticket.entities['event_type']} Meeting",
                    "start": {"dateTime": f"{ticket.entities['date']}T{ticket.entities['time']}:00"},
                    "end": {"dateTime": f"{ticket.entities['date']}T{ticket.entities['time']}:00"}
                }
            }
            mock_calendar.return_value = calendar_response
            
            # Execute service
            result = await agent.execute_service(ticket)
            
            # Log execution details
            logger.debug(f"Service execution result: {result}")
            logger.debug(f"Ticket step results: {ticket.step_results}")
            
            # Verify successful execution
            assert result["status"] == "success", f"Service failed with result: {result}"
            assert ticket.status == TicketStatus.COMPLETED, f"Unexpected ticket status: {ticket.status}"
            
            # Verify calendar event creation
            assert "Create Event" in ticket.step_results, "Missing calendar step results"
            calendar_result = ticket.step_results["Create Event"]
            assert calendar_result["success"] is True, f"Calendar step failed: {calendar_result}"
            assert "event_id" in calendar_result, "Missing event_id in calendar result"
            
            # Verify event summary includes event type
            event_details = calendar_result["event_details"]
            assert "summary" in event_details, "Missing event summary"
            assert ticket.entities["event_type"] in event_details["summary"], "Event type not in summary"

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 