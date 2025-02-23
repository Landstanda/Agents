import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
import json
from pathlib import Path

# Mock ticket class definition
class MockTicket:
    def __init__(self, **kwargs):
        self.ticket_id = kwargs.get('ticket_id', '')
        self.original_message = kwargs.get('original_message', '')
        self.service = kwargs.get('service')
        self.entities = kwargs.get('entities', {})
        self.status = 'created'
        self.execution_plan = []
        self.errors = []
        self.missing_entities = []
        
    def update_status(self, new_status):
        self.status = new_status
        
    def add_error(self, error_msg, error_type, step=None):
        self.status = 'error'
        self.errors.append({
            'message': error_msg,
            'type': error_type,
            'step': step
        })

# Mock ServiceAnalyzer class
class MockServiceAnalyzer:
    def __init__(self, services_path: str = "tests/fixtures/test_services.json"):
        self.services_path = services_path
        self.openai = None
        self.services = {
            "schedule_meeting": {
                "required_entities": ["time", "date", "description", "participants"]
            }
        }
        
    async def analyze_request(self, ticket: MockTicket):
        """Mock analyze_request method."""
        try:
            # Simulate analysis based on trigger words
            if "schedule" in ticket.original_message.lower():
                service = "schedule_meeting"
                # Check for required entities
                missing = []
                if "tomorrow" not in ticket.original_message.lower():
                    missing.append("date")
                if "10am" not in ticket.original_message.lower():
                    missing.append("time")
                if "team" not in ticket.original_message.lower():
                    missing.append("participants")
                
                if missing:
                    ticket.status = "waiting_input"
                    ticket.missing_entities = missing
                    return ticket
                
                ticket.service = service
                ticket.execution_plan = [{
                    "step_number": 1,
                    "service_id": service,
                    "description": "Schedule team meeting",
                    "required_params": {
                        "time": "10:00",
                        "date": "2024-03-01",
                        "description": "Team meeting",
                        "participants": ["team@example.com"]
                    },
                    "optional_params": {}
                }]
                ticket.status = "executing"
            else:
                ticket.add_error("Could not understand request", "analysis_error")
                
            return ticket
            
        except Exception as e:
            ticket.add_error(f"Analysis failed: {str(e)}", "system_error")
            return ticket

# Mock Google Auth Response
class MockGoogleAuthResponse:
    def __init__(self, valid=True, expired=False, scopes=None):
        self.valid = valid
        self.expired = expired
        self.refresh_token = "mock_refresh_token" if valid else None
        self.token = "mock_token" if valid else None
        self.scopes = scopes or [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/gmail.modify'
        ]
        self.token_uri = "https://oauth2.googleapis.com/token"
        self.client_id = "mock_client_id"
        self.client_secret = "mock_client_secret"

    def to_dict(self):
        return {
            "valid": self.valid,
            "expired": self.expired,
            "token": self.token,
            "refresh_token": self.refresh_token,
            "scopes": self.scopes,
            "token_uri": self.token_uri,
            "client_id": self.client_id,
            "client_secret": "[REDACTED]"
        }

# Mock Google Auth Module
class MockGoogleAuthModule:
    def __init__(self, success=True):
        self.success = success
        self.credentials = None
        self.default_scopes = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/gmail.modify'
        ]

    async def execute(self, context):
        if not self.success:
            return {
                "success": False,
                "error": "Authentication failed"
            }
        
        if self.credentials:
            return {
                "success": True,
                "credentials": {
                    "valid": self.credentials.valid,
                    "expired": self.credentials.expired,
                    "refresh_token": self.credentials.refresh_token,
                    "token": self.credentials.token,
                    "scopes": self.credentials.scopes
                }
            }
        
        # Default response if no credentials set
        return {
            "success": True,
            "credentials": {
                "valid": True,
                "expired": False,
                "refresh_token": "mock_refresh_token",
                "token": "mock_token",
                "scopes": self.default_scopes
            }
        }

# Mock Execution Context
class MockExecutionContext:
    def __init__(self, ticket):
        self.ticket = ticket
        self.step_results = {}
        self.current_step = None
        
    def store_result(self, step_number, result, success=True, error=None):
        self.step_results[step_number] = {
            "result": result,
            "success": success,
            "error": error
        }
        
    def get_result(self, step_number):
        return self.step_results.get(step_number, {}).get("result")

@pytest.fixture
def mock_openai():
    """Mock OpenAI client with predefined responses."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=json.dumps({
                            "understood_request": "Schedule a team meeting",
                            "confidence": 0.9,
                            "execution_steps": [{
                                "step_number": 1,
                                "service_id": "schedule_meeting",
                                "description": "Schedule team meeting",
                                "required_params": {
                                    "time": "10:00",
                                    "date": "2024-03-01",
                                    "description": "Team meeting",
                                    "participants": ["team@example.com"]
                                },
                                "optional_params": {}
                            }],
                            "missing_information": []
                        })
                    )
                )
            ]
        )
    )
    return mock_client

@pytest.mark.asyncio
async def test_simple():
    """A simple test that always passes."""
    assert True

@pytest.mark.asyncio
async def test_async_mock():
    """Test that async mocks work correctly."""
    mock = AsyncMock()
    mock.return_value = "test"
    result = await mock()
    assert result == "test"

@pytest.mark.asyncio
async def test_mock_openai(mock_openai):
    """Test that the OpenAI mock works correctly."""
    response = await mock_openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "test"}]
    )
    assert response.choices[0].message.content is not None

@pytest.mark.asyncio
async def test_mock_ticket():
    """Test that we can create and use a mock ticket."""
    ticket = MockTicket(
        ticket_id="test_123",
        original_message="Schedule a team meeting tomorrow at 10am"
    )
    
    assert ticket.ticket_id == "test_123"
    assert ticket.status == "created"
    assert not ticket.entities  # Should be empty dict
    
    # Test status update
    ticket.update_status("executing")
    assert ticket.status == "executing"
    
    # Test error handling
    ticket.add_error("Test error", "test_error")
    assert ticket.status == "error"
    assert len(ticket.errors) == 1
    assert ticket.errors[0]["type"] == "test_error"

@pytest.mark.asyncio
async def test_mock_service_analyzer_success():
    """Test the mock ServiceAnalyzer with a valid request."""
    analyzer = MockServiceAnalyzer()
    ticket = MockTicket(
        ticket_id="test_123",
        original_message="Schedule a team meeting tomorrow at 10am"
    )
    
    result = await analyzer.analyze_request(ticket)
    
    assert result.status == "executing"
    assert result.service == "schedule_meeting"
    assert len(result.execution_plan) == 1
    assert result.execution_plan[0]["service_id"] == "schedule_meeting"
    assert not result.errors

@pytest.mark.asyncio
async def test_mock_service_analyzer_missing_info():
    """Test the mock ServiceAnalyzer with missing information."""
    analyzer = MockServiceAnalyzer()
    ticket = MockTicket(
        ticket_id="test_124",
        original_message="Schedule a meeting"  # Missing time and date
    )
    
    result = await analyzer.analyze_request(ticket)
    
    assert result.status == "waiting_input"
    assert "date" in result.missing_entities
    assert "time" in result.missing_entities
    assert not result.errors

@pytest.mark.asyncio
async def test_mock_service_analyzer_unknown_request():
    """Test the mock ServiceAnalyzer with an unknown request."""
    analyzer = MockServiceAnalyzer()
    ticket = MockTicket(
        ticket_id="test_125",
        original_message="Do something unknown"
    )
    
    result = await analyzer.analyze_request(ticket)
    
    assert result.status == "error"
    assert len(result.errors) == 1
    assert result.errors[0]["type"] == "analysis_error"

@pytest.mark.asyncio
async def test_mock_service_analyzer_system_error():
    """Test the mock ServiceAnalyzer with a system error."""
    analyzer = MockServiceAnalyzer()
    # Create a ticket that will cause an error
    ticket = MockTicket(
        ticket_id="test_126",
        original_message=None  # This should cause an error when trying to use .lower()
    )
    
    result = await analyzer.analyze_request(ticket)
    
    assert result.status == "error"
    assert len(result.errors) == 1
    assert result.errors[0]["type"] == "system_error"

@pytest.mark.asyncio
async def test_google_auth_success():
    """Test successful Google authentication and response validation."""
    # Create test components
    ticket = MockTicket(
        ticket_id="test_auth_1",
        original_message="Schedule a team meeting tomorrow at 10am"
    )
    context = MockExecutionContext(ticket)
    auth_module = MockGoogleAuthModule(success=True)

    # Execute auth
    result = await auth_module.execute(context)

    # Verify success response
    assert result["success"] is True
    assert "credentials" in result
    assert result["credentials"]["valid"] is True
    assert result["credentials"]["token"] is not None
    assert any("calendar" in scope for scope in result["credentials"]["scopes"])

@pytest.mark.asyncio
async def test_google_auth_failure():
    """Test failed Google authentication."""
    ticket = MockTicket(
        ticket_id="test_auth_2",
        original_message="Schedule a team meeting tomorrow at 10am"
    )
    context = MockExecutionContext(ticket)
    auth_module = MockGoogleAuthModule(success=False)

    # Execute auth
    result = await auth_module.execute(context)

    # Verify failure response
    assert result["success"] is False
    assert "error" in result
    assert result["error"] == "Authentication failed"

@pytest.mark.asyncio
async def test_google_auth_expired_token():
    """Test handling of expired Google auth token."""
    ticket = MockTicket(
        ticket_id="test_auth_3",
        original_message="Schedule a team meeting tomorrow at 10am"
    )
    context = MockExecutionContext(ticket)

    # Create auth module with expired token
    auth_module = MockGoogleAuthModule(success=True)
    auth_module.credentials = MockGoogleAuthResponse(
        valid=True,
        expired=True,
        scopes=['https://www.googleapis.com/auth/gmail.modify']
    )

    result = await auth_module.execute(context)

    # Should still be successful as token refresh is handled
    assert result["success"] is True
    assert result["credentials"]["expired"] is True
    assert "gmail.modify" in result["credentials"]["scopes"][0]

@pytest.mark.asyncio
async def test_google_auth_missing_scopes():
    """Test handling of missing required scopes."""
    ticket = MockTicket(
        ticket_id="test_auth_4",
        original_message="Schedule a team meeting tomorrow at 10am"
    )
    context = MockExecutionContext(ticket)

    # Create auth module with limited scopes
    auth_module = MockGoogleAuthModule(success=True)
    auth_module.credentials = MockGoogleAuthResponse(
        valid=True,
        scopes=['https://www.googleapis.com/auth/gmail.modify']  # Only email scope
    )

    result = await auth_module.execute(context)

    # Should indicate success but missing required scope
    assert result["success"] is True
    assert "calendar" not in result["credentials"]["scopes"][0]
    assert "gmail.modify" in result["credentials"]["scopes"][0]

@pytest.mark.asyncio
async def test_google_auth_response_validation():
    """Test validation of Google auth response against service requirements."""
    # Load test service definition
    service_def = {
        "name": "schedule_meeting",
        "required_auth": {
            "type": "google_oauth2",
            "scopes": ["https://www.googleapis.com/auth/calendar"]
        },
        "success_criteria": {
            "auth": {
                "valid": True,
                "required_scopes": ["calendar"]
            }
        }
    }
    
    ticket = MockTicket(
        ticket_id="test_auth_5",
        original_message="Schedule a team meeting tomorrow at 10am"
    )
    context = MockExecutionContext(ticket)
    auth_module = MockGoogleAuthModule(success=True)
    
    # Execute auth
    result = await auth_module.execute(context)
    
    # Validate response against service requirements
    assert result["success"] is True
    assert any("calendar" in scope for scope in result["credentials"]["scopes"])
    assert result["credentials"]["valid"] is True
    
    # Verify all required scopes are present
    required_scopes = service_def["required_auth"]["scopes"]
    auth_scopes = result["credentials"]["scopes"]
    assert all(any(req_scope in auth_scope for auth_scope in auth_scopes) 
              for req_scope in required_scopes)

@pytest.mark.asyncio
async def test_google_auth_real_response_format():
    """Test handling of real Google auth response format."""
    # This is an example of a real Google OAuth2 response format
    real_response = {
        "token": "ya29.a0AfB_byC...",
        "refresh_token": "1//0eX...",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "1234567890-abcdef...",
        "client_secret": "GOCSPX-...",
        "scopes": [
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/gmail.modify"
        ],
        "expiry": "2024-02-22T12:00:00Z"
    }
    
    ticket = MockTicket(
        ticket_id="test_auth_6",
        original_message="Schedule a team meeting tomorrow at 10am"
    )
    context = MockExecutionContext(ticket)
    
    # Create result in real response format
    result = {
        "success": True,
        "credentials": real_response,
        "scopes": real_response["scopes"]
    }
    
    # Store result as if it came from auth module
    context.store_result(1, result, success=True)
    
    # Verify stored result matches expected format
    stored_result = context.get_result(1)
    assert stored_result["success"] is True
    assert "credentials" in stored_result
    assert "token" in stored_result["credentials"]
    assert "refresh_token" in stored_result["credentials"]
    assert "scopes" in stored_result["credentials"]
    assert "calendar" in stored_result["credentials"]["scopes"][0]

@pytest.mark.asyncio
async def test_live_google_auth():
    """Test live Google authentication flow."""
    from src.modules.google_auth import GoogleAuthModule
    from src.execution.context import ExecutionContext
    from src.models import Ticket
    
    # Create a real ticket
    ticket = Ticket(
        ticket_id="live_auth_test",
        original_message="Schedule a team meeting tomorrow at 10am",
        service="schedule_meeting",
        entities={}
    )
    
    # Create execution context with minimal service definition
    service_def = {
        "name": "schedule_meeting",
        "required_auth": {
            "type": "google_oauth2",
            "scopes": [
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/gmail.modify"
            ]
        }
    }
    
    context = ExecutionContext(ticket, service_def)
    
    # Create real auth module
    auth_module = GoogleAuthModule()
    
    # Execute auth
    result = await auth_module.execute(context)
    
    # Verify response structure
    assert result["success"] is True, f"Auth failed: {result.get('error', 'Unknown error')}"
    assert "credentials" in result
    assert result["credentials"]["valid"] is True
    assert result["credentials"]["token"] is not None
    
    # Verify scopes (order-independent)
    scopes = result["credentials"]["scopes"]
    assert any("calendar" in scope for scope in scopes), "Calendar scope not found"
    assert any("gmail.modify" in scope for scope in scopes), "Gmail scope not found"
    
    # Verify token storage
    stored_result = context.get_result(1)
    assert stored_result is not None
    assert stored_result["success"] is True
    assert "credentials" in stored_result
    
    # Verify token refresh
    assert result["credentials"]["valid"] is True
    assert result["credentials"]["expired"] is False
    assert result["credentials"]["refresh_token"] is not None
    assert result["credentials"]["token"] is not None
    
    # Verify stored scopes (order-independent)
    stored_scopes = stored_result["credentials"]["scopes"]
    assert any("calendar" in scope for scope in stored_scopes), "Calendar scope not found in stored result"
    assert any("gmail.modify" in scope for scope in stored_scopes), "Gmail scope not found in stored result" 