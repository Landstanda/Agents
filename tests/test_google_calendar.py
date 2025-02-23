import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import pytz
from datetime import datetime, timedelta
from src.modules.google_calendar import GoogleCalendarModule
import asyncio
from typing import Dict, Any
from unittest.mock import Mock
from src.models import Ticket, TicketStatus
from src.core.registry.tools import ToolRegistry
from src.core.registry.services import ServiceRegistry
from src.core.agent.executor import ServiceExecutor
from src.core.agent.base import Agent
from src.modules.google_auth import GoogleAuthModule
from src.execution.context import ExecutionContext

@pytest.fixture
def mock_google_auth(mocker):
    """Mock Google auth module"""
    mock_auth = mocker.AsyncMock()
    mock_auth.execute.return_value = {
        'success': True,
        'credentials': {
            'token': 'test_token',
            'refresh_token': 'test_refresh',
            'token_uri': 'test_uri',
            'client_id': 'test_id',
            'client_secret': 'test_secret',
            'scopes': ['https://www.googleapis.com/auth/calendar']
        }
    }
    return mock_auth

@pytest.fixture
def mock_calendar_service(mocker):
    """Mock Google Calendar service"""
    mock_service = mocker.MagicMock()
    
    # Mock the build function
    mock_build = mocker.patch('src.modules.google_calendar.build')
    mock_build.return_value = mock_service
    
    # Mock service methods
    mock_events = mocker.MagicMock()
    mock_service.events.return_value = mock_events
    
    # Mock insert method
    mock_insert = mocker.MagicMock()
    mock_events.insert.return_value = mock_insert
    mock_insert.execute.return_value = {
        'id': 'test_event_id',
        'htmlLink': 'https://calendar.google.com/test'
    }
    
    return mock_service

@pytest.fixture
def mock_service():
    """Create a mock service definition"""
    return {
        'name': 'test_calendar_service',
        'version': '1.0.0',
        'steps': [
            {
                'name': 'auth',
                'tool': 'google_auth',
                'action': 'authenticate'
            },
            {
                'name': 'calendar',
                'tool': 'google_calendar',
                'action': 'execute'
            }
        ]
    }

@pytest.fixture
def base_ticket():
    """Create a base ticket for testing"""
    return Ticket(
        ticket_id='test_123',
        original_message='Test calendar operation',
        service='test_calendar_service',
        entities={}
    )

@pytest.fixture
async def calendar_module(mock_google_auth, mock_calendar_service, mock_service, base_ticket):
    module = GoogleCalendarModule()
    context = ExecutionContext(base_ticket, mock_service)
    context.store_result(step_number=1, result={
        'success': True,
        'credentials': {
            'valid': True,
            'expired': False,
            'token': 'test_token',
            'refresh_token': 'test_refresh',
            'token_uri': 'test_uri',
            'client_id': 'test_client_id',
            'scopes': ['https://www.googleapis.com/auth/calendar']
        }
    })
    await module._initialize_service(context)
    return module

@pytest.fixture
async def real_calendar_module(mock_service, base_ticket):
    """Create a calendar module with real credentials"""
    module = GoogleCalendarModule()
    context = ExecutionContext(base_ticket, mock_service)
    context.store_result(step_number=1, result={
        'success': True,
        'credentials': {
            'valid': True,
            'expired': False,
            'token': 'test_token',
            'refresh_token': 'test_refresh',
            'token_uri': 'test_uri',
            'client_id': 'test_client_id',
            'scopes': ['https://www.googleapis.com/auth/calendar']
        }
    })
    await module._initialize_service(context)
    return module

@pytest.fixture
async def service_registry():
    """Create and initialize a service registry for testing"""
    registry = ServiceRegistry('src/services/service_definitions.yaml')
    await registry.load_services()
    return registry

@pytest.fixture
async def tool_registry():
    """Create and initialize a tool registry for testing"""
    registry = ToolRegistry()
    await registry.register_tool('google_auth', GoogleAuthModule)
    await registry.register_tool('google_calendar', GoogleCalendarModule)
    return registry

@pytest.fixture
async def executor(service_registry, tool_registry):
    """Create and initialize a service executor for testing"""
    sr = await service_registry
    tr = await tool_registry
    return ServiceExecutor(sr, tr)

@pytest.fixture
async def agent(service_registry, tool_registry):
    """Create and initialize an agent for testing"""
    sr = await service_registry
    tr = await tool_registry
    agent = Agent()
    agent.service_registry = sr
    agent.tool_registry = tr
    agent.executor = ServiceExecutor(sr, tr)
    agent._initialized = True
    return agent

@pytest.fixture
def meeting_ticket():
    """Create a test ticket for scheduling a meeting"""
    tomorrow = datetime.now() + timedelta(days=1)
    meeting_date = tomorrow.strftime('%Y-%m-%d')
    meeting_time = '14:00'  # 2 PM
    
    return Ticket(
        ticket_id='meeting_test_123',
        original_message='Schedule a team meeting for tomorrow at 2 PM',
        service='schedule_meeting',
        entities={
            'time': meeting_time,
            'date': meeting_date,
            'description': 'Team sync meeting',
            'participants': ['test@example.com'],
            'duration': 60  # 60 minutes
        }
    )

@pytest.mark.asyncio
class TestGoogleAuthFlow:
    """Test the authentication flow for Google Calendar"""
    
    async def test_auth_success(self, mock_google_auth, mock_service, base_ticket, mocker):
        """Test successful authentication"""
        context = ExecutionContext(base_ticket, mock_service)
        
        # Store auth result
        auth_result = {
            'success': True,
            'credentials': {
                'token': 'test_token',
                'refresh_token': 'test_refresh',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_id',
                'client_secret': 'test_secret',
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
        }
        context.store_result(1, auth_result)
        
        # Create mock service
        mock_calendar = mocker.MagicMock()
        
        # Mock the build function to return our mock service
        def mock_build(*args, **kwargs):
            return mock_calendar
            
        mocker.patch('src.modules.google_calendar.build', return_value=mock_calendar)
        
        module = GoogleCalendarModule()
        service = await module._initialize_service(context)
        
        assert service is not None
        assert service == mock_calendar
        assert base_ticket.status != TicketStatus.ERROR

    async def test_auth_failure(self, mock_google_auth, mock_service, base_ticket):
        """Test authentication failure"""
        context = ExecutionContext(base_ticket, mock_service)
        context.store_result(1, {
            'success': False,
            'error': 'Auth failed'
        })
        
        module = GoogleCalendarModule()
        service = await module._initialize_service(context)
        assert service is None
        assert base_ticket.status == TicketStatus.ERROR

@pytest.mark.asyncio
class TestEntityValidation:
    """Test entity validation for Google Calendar operations"""
    
    async def test_create_event_entities(self, mock_service, base_ticket, mocker):
        """Test entity validation for event creation"""
        context = ExecutionContext(base_ticket, mock_service)
        
        # Set up successful authentication first
        auth_result = {
            'success': True,
            'credentials': {
                'token': 'test_token',
                'refresh_token': 'test_refresh',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': 'test_id',
                'client_secret': 'test_secret',
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
        }
        context.store_result(1, auth_result)
        
        # Create mock service
        mock_calendar = mocker.MagicMock()
        mocker.patch('src.modules.google_calendar.build', return_value=mock_calendar)
        
        module = GoogleCalendarModule()
        
        # Test with missing entities
        result = await module.execute(context)
        assert result['status'] == 'error'
        assert 'Missing required entities' in result['error']
        
        # Test with all required entities
        base_ticket.entities = {
            'operation': 'create_event',
            'time': '10:00',
            'date': '2024-03-20',
            'description': 'Test Event',
            'participants': ['test@example.com']
        }
        
        result = await module.execute(context)
        assert result['status'] != 'error'
        assert 'error' not in result

@pytest.mark.asyncio
class TestCalendarOperations:
    """Test individual calendar operations"""
    
    async def test_create_event(self, mock_service, base_ticket, mock_calendar_service):
        """Test event creation"""
        context = ExecutionContext(base_ticket, mock_service)
        module = GoogleCalendarModule()
        
        # Setup auth result
        context.store_result(1, {
            'success': True,
            'credentials': {
                'token': 'test_token',
                'refresh_token': 'test_refresh',
                'token_uri': 'test_uri',
                'client_id': 'test_id',
                'client_secret': 'test_secret',
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
        })
        
        # Test event creation
        base_ticket.entities = {
            'time': '14:00',
            'date': '2024-02-22',
            'description': 'Test Meeting',
            'participants': ['test@example.com']
        }
        result = await module.execute(context)
        assert result['status'] == 'completed'
        assert result['results'][0]['success'] is True

@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling scenarios"""
    
    async def test_service_initialization_error(self, mock_service, base_ticket):
        """Test handling of service initialization errors"""
        context = ExecutionContext(base_ticket, mock_service)
        module = GoogleCalendarModule()
        
        # Test with missing auth result
        result = await module.execute(context)
        assert result['status'] == 'error'
        assert 'Failed to initialize' in result['error']
        
    async def test_api_error_handling(self, mock_service, base_ticket, mock_calendar_service):
        """Test handling of API errors"""
        context = ExecutionContext(base_ticket, mock_service)
        module = GoogleCalendarModule()
        
        # Setup auth success but API failure
        context.store_result(1, {
            'success': True,
            'credentials': {
                'token': 'test_token',
                'refresh_token': 'test_refresh',
                'token_uri': 'test_uri',
                'client_id': 'test_id',
                'client_secret': 'test_secret',
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
        })
        
        # Simulate API error
        mock_calendar_service.events().insert.return_value.execute.side_effect = Exception("API Error")
        
        base_ticket.entities = {
            'time': '14:00',
            'date': '2024-02-22',
            'description': 'Test Meeting',
            'participants': ['test@example.com']
        }
        result = await module.execute(context)
        assert result['status'] == 'error'
        assert base_ticket.status == TicketStatus.ERROR

@pytest.mark.asyncio
class TestIntegration:
    """Test integration between components"""
    
    async def test_full_meeting_flow(self, agent, meeting_ticket):
        """Test complete meeting scheduling flow"""
        # Process ticket
        await agent.process_ticket(meeting_ticket)
        
        # Verify final status
        assert meeting_ticket.status == TicketStatus.COMPLETED
        assert len(meeting_ticket.execution_results) > 0
        assert not meeting_ticket.errors

    async def test_auth_integration(self, agent, meeting_ticket, mock_service):
        """Test authentication integration"""
        # Modify ticket for auth testing
        meeting_ticket.service = 'google_auth'
        
        # Process ticket
        await agent.process_ticket(meeting_ticket)
        
        # Verify auth results
        assert meeting_ticket.status != TicketStatus.ERROR
        assert any(result.get('success') for result in meeting_ticket.execution_results)

@pytest.mark.asyncio
class TestGoogleCalendarModuleInitialization:
    """Tests focusing on module initialization and authentication"""
    
    async def test_module_creation(self):
        """Test basic module creation"""
        module = GoogleCalendarModule()
        assert module is not None
        assert isinstance(module.capabilities, list)
        assert 'google_calendar_integration' in module.capabilities

    async def test_service_initialization_with_valid_auth(self, mock_google_auth, mock_calendar_service, mock_service, base_ticket):
        module = GoogleCalendarModule()
        context = ExecutionContext(base_ticket, mock_service)
        context.store_result(step_number=1, result={
            'success': True,
            'credentials': {
                'valid': True,
                'expired': False,
                'token': 'test_token',
                'refresh_token': 'test_refresh',
                'token_uri': 'test_uri',
                'client_id': 'test_client_id',
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
        })
        service = await module._initialize_service(context)
        assert service is not None

    async def test_service_initialization_with_invalid_auth(self, mock_google_auth, mock_calendar_service, mock_service, base_ticket):
        module = GoogleCalendarModule()
        context = ExecutionContext(base_ticket, mock_service)
        context.store_result(step_number=1, result={
            'success': False,
            'error': 'Authentication failed'
        })
        service = await module._initialize_service(context)
        assert service is None

@pytest.mark.asyncio
class TestGoogleCalendarModuleEntityValidation:
    """Tests focusing on entity validation"""
    
    async def test_missing_required_entities(self, calendar_module, mock_service, base_ticket):
        ticket = Ticket(
            ticket_id='test_123',
            original_message='Schedule a meeting',
            service='schedule_meeting',
            entities={}
        )
        context = ExecutionContext(ticket, mock_service)
        result = await calendar_module.execute(ticket, context)
        assert result['status'] == 'error'
        assert ticket.status == TicketStatus.ERROR
        assert 'Missing required entities' in result['error']

    async def test_partial_required_entities(self, calendar_module, mock_service, base_ticket):
        ticket = Ticket(
            ticket_id='test_123',
            original_message='Schedule a meeting',
            service='schedule_meeting',
            entities={'time': '14:00', 'date': '2025-02-23'}
        )
        context = ExecutionContext(ticket, mock_service)
        result = await calendar_module.execute(ticket, context)
        assert result['status'] == 'error'
        assert ticket.status == TicketStatus.ERROR
        assert 'Missing required entities' in result['error']

    async def test_all_required_entities(self, calendar_module, mock_service, base_ticket):
        ticket = Ticket(
            ticket_id='test_123',
            original_message='Schedule a meeting',
            service='schedule_meeting',
            entities={
                'time': '14:00',
                'date': '2025-02-23',
                'description': 'Test meeting',
                'participants': ['test@example.com']
            }
        )
        context = ExecutionContext(ticket, mock_service)
        result = await calendar_module.execute(ticket, context)
        assert result['status'] == 'completed'
        assert ticket.status == TicketStatus.COMPLETED

@pytest.mark.asyncio
class TestGoogleCalendarModuleOperations:
    """Tests focusing on calendar operations"""
    
    async def test_create_event_success(self, calendar_module, mock_calendar_service, mock_service):
        mock_calendar_service.events().insert().execute.return_value = {
            'id': 'test_event_id',
            'htmlLink': 'https://calendar.google.com/event?id=test'
        }
        
        ticket = Ticket(
            ticket_id='test_123',
            original_message='Schedule a meeting',
            service='schedule_meeting',
            entities={
                'time': '14:00',
                'date': '2025-02-23',
                'description': 'Test meeting',
                'participants': ['test@example.com']
            }
        )
        context = ExecutionContext(ticket, mock_service)
        context.store_result(step_number=1, result={
            'success': True,
            'credentials': {
                'valid': True,
                'expired': False,
                'token': 'test_token',
                'refresh_token': 'test_refresh',
                'token_uri': 'test_uri',
                'client_id': 'test_client_id',
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
        })
        
        result = await calendar_module.execute(ticket, context)
        assert result['status'] == 'completed'
        assert ticket.status == TicketStatus.COMPLETED

    async def test_create_event_api_failure(self, calendar_module, mock_calendar_service, mock_service):
        mock_calendar_service.events().insert().execute.side_effect = Exception('API Error')
        
        ticket = Ticket(
            ticket_id='test_123',
            original_message='Schedule a meeting',
            service='schedule_meeting',
            entities={
                'time': '14:00',
                'date': '2025-02-23',
                'description': 'Test meeting',
                'participants': ['test@example.com']
            }
        )
        context = ExecutionContext(ticket, mock_service)
        context.store_result(step_number=1, result={
            'success': True,
            'credentials': {
                'valid': True,
                'expired': False,
                'token': 'test_token',
                'refresh_token': 'test_refresh',
                'token_uri': 'test_uri',
                'client_id': 'test_client_id',
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
        })
        
        result = await calendar_module.execute(ticket, context)
        assert result['status'] == 'error'
        assert ticket.status == TicketStatus.ERROR
        assert 'API Error' in result['error']

@pytest.mark.asyncio
class TestGoogleCalendarModuleErrorHandling:
    """Tests focusing on error handling"""
    
    async def test_invalid_date_format(self, mock_google_auth, mock_calendar_service, mock_service, base_ticket):
        """Test handling of invalid date format"""
        module = GoogleCalendarModule()
        base_ticket.entities = {
            'time': 'invalid_time',
            'date': 'invalid_date',
            'description': 'Test meeting',
            'participants': ['test@example.com']
        }
        context = ExecutionContext(base_ticket, mock_service)
        
        result = await module.execute(base_ticket, context)
        assert result['status'] == 'error'
        assert base_ticket.status == TicketStatus.ERROR

    async def test_invalid_email_format(self, mock_google_auth, mock_calendar_service, mock_service, base_ticket):
        """Test handling of invalid email format"""
        module = GoogleCalendarModule()
        base_ticket.entities = {
            'time': '14:00',
            'date': '2024-02-22',
            'description': 'Test meeting',
            'participants': ['invalid_email']
        }
        context = ExecutionContext(base_ticket, mock_service)
        
        result = await module.execute(base_ticket, context)
        assert result['status'] == 'error'
        assert base_ticket.status == TicketStatus.ERROR

    async def test_service_build_failure(self, mock_google_auth, mock_service, base_ticket):
        """Test handling of service build failure"""
        module = GoogleCalendarModule()
        base_ticket.entities = {
            'time': '14:00',
            'date': '2024-02-22',
            'description': 'Test meeting',
            'participants': ['test@example.com']
        }
        context = ExecutionContext(base_ticket, mock_service)
        
        # Mock service build failure
        with patch('src.modules.google_calendar.build', side_effect=Exception("Failed to build service")):
            result = await module.execute(base_ticket, context)
            assert result['status'] == 'error'
            assert base_ticket.status == TicketStatus.ERROR
            assert any('Failed to build service' in error['message'] for error in base_ticket.errors)

@pytest.mark.asyncio
class TestGoogleCalendarModule:
    async def test_create_breakfast_event(self, calendar_module, mock_service):
        calendar_module = await calendar_module
        # Set up event parameters for tomorrow at 9:15 AM
        event_date = datetime(2025, 2, 15, 9, 15, 0)
        
        # Format time in the expected format
        start_time = event_date.strftime('%Y-%m-%dT%H:%M:00')
        end_time = (event_date + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:00')

        # Create the event
        params = {
            'operation': 'create_event',
            'summary': 'Breakfast Meeting',
            'description': 'Morning breakfast meeting',
            'start_time': start_time,
            'end_time': end_time,
            'timezone': 'America/Los_Angeles',
            'location': 'Local Cafe'
        }

        print(f"\nAttempting to create breakfast event:")
        print(f"Date: {event_date.strftime('%A, %B %d, %Y')}")
        print(f"Time: {event_date.strftime('%I:%M %p')}")
        print(f"Parameters: {params}")

        # Create execution context
        ticket = Ticket(
            ticket_id='breakfast_test_123',
            original_message='Schedule a breakfast meeting',
            service='schedule_meeting',
            entities=params
        )
        context = ExecutionContext(ticket, mock_service)

        # Create the event
        await calendar_module.execute(context)
        assert context.get_result(2)['success'] is True
        assert 'event_id' in context.get_result(2)['result']

    async def test_check_availability(self, calendar_module, mock_service):
        calendar_module = await calendar_module
        # Set date to tomorrow at 9:15 AM
        now = datetime.now()
        event_date = datetime(2025, 2, 15, 9, 15)  # Changed year to 2025

        print(f"Checking availability for tomorrow at {event_date.strftime('%I:%M %p')} PST")

        # Check availability for tomorrow's breakfast time
        timezone = pytz.timezone('America/Los_Angeles')
        event_date = timezone.localize(event_date)

        params = {
            'operation': 'check_availability',
            'start_time': event_date.isoformat(),
            'end_time': (event_date + timedelta(hours=1)).isoformat(),
            'timezone': 'America/Los_Angeles'
        }

        # Create execution context
        ticket = Ticket(
            ticket_id='availability_test_123',
            original_message='Check calendar availability',
            service='schedule_meeting',
            entities=params
        )
        context = ExecutionContext(ticket, mock_service)

        # Check availability
        await calendar_module.execute(context)
        result = context.get_result(2)
        assert result['success'] is True
        assert 'is_available' in result['result']

    async def test_create_event(self, calendar_module, mock_calendar_service, mock_service):
        calendar_module = await calendar_module
        # Setup mock response
        mock_event = {
            'id': 'test_event_id',
            'htmlLink': 'https://calendar.google.com/event?id=test'
        }
        mock_calendar_service.events().insert().execute.return_value = mock_event

        # Test parameters
        params = {
            'operation': 'create_event',
            'summary': 'Test Meeting',
            'start_time': '2024-03-20T10:00:00Z',
            'end_time': '2024-03-20T11:00:00Z',
            'description': 'Test meeting description',
            'attendees': ['test@example.com']
        }

        # Create execution context
        ticket = Ticket(
            ticket_id='create_test_123',
            original_message='Create a test meeting',
            service='schedule_meeting',
            entities=params
        )
        context = ExecutionContext(ticket, mock_service)

        # Execute operation
        await calendar_module.execute(context)
        result = context.get_result(2)

        # Verify result
        assert result['success'] is True
        assert result['result']['event_id'] == 'test_event_id'
        assert result['result']['html_link'] == 'https://calendar.google.com/event?id=test'

    async def test_list_events(self, calendar_module, mock_calendar_service, mock_service):
        calendar_module = await calendar_module
        # Setup mock response
        mock_events = {
            'items': [
                {
                    'id': 'event1',
                    'summary': 'Test Event 1',
                    'start': {'dateTime': '2024-03-20T10:00:00Z'},
                    'end': {'dateTime': '2024-03-20T11:00:00Z'}
                }
            ]
        }
        
        # Reset mock to ensure clean state
        mock_calendar_service.reset_mock()
        
        # Setup the mock chain
        events_mock = MagicMock()
        list_mock = MagicMock()
        execute_mock = MagicMock(return_value=mock_events)
        
        list_mock.execute = MagicMock(return_value=mock_events)
        events_mock.list = MagicMock(return_value=list_mock)
        mock_calendar_service.events = MagicMock(return_value=events_mock)

        # Test parameters
        params = {
            'operation': 'list_events',
            'max_results': 10
        }

        # Create execution context
        ticket = Ticket(
            ticket_id='list_test_123',
            original_message='List calendar events',
            service='schedule_meeting',
            entities=params
        )
        context = ExecutionContext(ticket, mock_service)

        # Execute operation
        await calendar_module.execute(context)
        result = context.get_result(2)

        # Verify result
        assert result['success'] is True
        assert len(result['result']['events']) == 1
        assert result['result']['events'][0]['id'] == 'event1'
        
        # Verify mock calls
        mock_calendar_service.events.assert_called_once()
        events_mock.list.assert_called_once()
        list_mock.execute.assert_called_once()

    async def test_error_handling(self, calendar_module, mock_calendar_service, mock_service):
        calendar_module = await calendar_module
        # Setup mock to raise an exception
        mock_calendar_service.events().insert().execute.side_effect = Exception("API Error")

        # Test parameters
        params = {
            'operation': 'create_event',
            'summary': 'Test Meeting',
            'start_time': '2024-03-20T10:00:00Z',
            'end_time': '2024-03-20T11:00:00Z'
        }

        # Create execution context
        ticket = Ticket(
            ticket_id='error_test_123',
            original_message='Create a test meeting',
            service='schedule_meeting',
            entities=params
        )
        context = ExecutionContext(ticket, mock_service)

        # Execute operation
        await calendar_module.execute(context)
        result = context.get_result(2)

        # Verify error handling
        assert result['success'] is False
        assert 'error' in result
        assert 'API Error' in result['error']
        assert context.ticket.status == TicketStatus.ERROR

    async def test_list_all_events(self, calendar_module, mock_service):
        calendar_module = await calendar_module
        """List all events in the calendar for debugging"""
        # Set specific date for February 15th
        timezone = pytz.timezone('America/Los_Angeles')
        target_date = timezone.localize(datetime(2024, 2, 15))
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        params = {
            'operation': 'list_events',
            'time_min': day_start.isoformat(),
            'time_max': day_end.isoformat(),
            'timezone': 'America/Los_Angeles'
        }

        # Create execution context
        ticket = Ticket(
            ticket_id='list_all_test_123',
            original_message='List all calendar events',
            service='schedule_meeting',
            entities=params
        )
        context = ExecutionContext(ticket, mock_service)

        print(f"\nListing all events for {day_start.strftime('%A, %B %d, %Y')}:")
        await calendar_module.execute(context)
        result = context.get_result(2)
        assert result['success'] is True
        assert 'events' in result['result']
        
        # Also list events for the specific time slot
        print(f"\nChecking specific time slot (9:15 AM):")
        target_time = target_date.replace(hour=9, minute=15, second=0, microsecond=0)
        params = {
            'operation': 'list_events',
            'time_min': target_time.isoformat(),
            'time_max': (target_time + timedelta(hours=1)).isoformat(),
            'timezone': 'America/Los_Angeles'
        }
        
        # Create new context for specific time slot
        ticket = Ticket(
            ticket_id='list_slot_test_123',
            original_message='List events in time slot',
            service='schedule_meeting',
            entities=params
        )
        context = ExecutionContext(ticket, mock_service)
        
        await calendar_module.execute(context)
        result = context.get_result(2)
        if result['success']:
            events = result['result']['events']
            if events:
                print(f"Found {len(events)} events in the breakfast time slot:")
                for event in events:
                    start = event.get('start', {}).get('dateTime', 'No start time')
                    end = event.get('end', {}).get('dateTime', 'No end time')
                    print(f"- {event.get('summary', 'No title')} ({start} to {end})")
                    print(f"  ID: {event.get('id')}")
                    print(f"  Link: {event.get('htmlLink')}")
            else:
                print("No events found in the breakfast time slot")

    @pytest.mark.integration
    async def test_create_real_event(self, real_calendar_module, mock_service):
        """Test creating a real event in Google Calendar"""
        calendar_module = await real_calendar_module
        
        # Set up event parameters for tomorrow at 9:15 AM
        event_date = datetime.now() + timedelta(days=1)
        event_date = event_date.replace(hour=9, minute=15, second=0, microsecond=0)

        # Create the event
        params = {
            'operation': 'create_event',
            'summary': 'Test Breakfast Meeting',
            'description': 'This is a test event created by the test suite',
            'start_time': event_date.isoformat(),
            'end_time': (event_date + timedelta(hours=1)).isoformat(),
            'timezone': 'America/Los_Angeles',
            'location': 'Virtual Meeting'
        }

        print(f"\nAttempting to create real calendar event:")
        print(f"Date: {event_date.strftime('%A, %B %d, %Y')}")
        print(f"Time: {event_date.strftime('%I:%M %p')}")
        print(f"Parameters: {params}")

        # Create execution context
        ticket = Ticket(
            ticket_id='real_event_test_123',
            original_message='Create a real calendar event',
            service='schedule_meeting',
            entities=params
        )
        context = ExecutionContext(ticket, mock_service)

        # Create the event
        await calendar_module.execute(context)
        result = context.get_result(2)
        
        print(f"\nResult: {result}")

        # Verify the result
        assert result['success'] is True
        assert 'event_id' in result['result']
        assert 'html_link' in result['result']

        # Print the event link
        print(f"\nEvent created successfully!")
        print(f"Event ID: {result['result']['event_id']}")
        print(f"Event Link: {result['result']['html_link']}")

@pytest.mark.asyncio
async def test_schedule_meeting_flow(agent, meeting_ticket):
    """Test the complete flow of scheduling a meeting"""
    # Process ticket
    agent_instance = await agent
    await agent_instance.process_ticket(meeting_ticket)
    
    # Verify execution completed successfully
    assert meeting_ticket.status == TicketStatus.COMPLETED
    assert len(meeting_ticket.execution_results) > 0
    assert not meeting_ticket.errors
    
    # Verify specific results from calendar creation
    last_result = meeting_ticket.execution_results[-1]
    assert last_result['status'] == 'completed'
    assert 'event_id' in last_result.get('results', {})
    assert 'html_link' in last_result.get('results', {})

@pytest.mark.asyncio
async def test_schedule_meeting_auth_failure(agent, meeting_ticket, mock_service):
    """Test handling of authentication failure"""
    # Mock auth failure
    with patch('src.modules.google_auth.GoogleAuthModule.execute') as mock_auth:
        mock_auth.return_value = {'success': False, 'error': 'Authentication failed'}
        
        # Process ticket
        agent_instance = await agent
        await agent_instance.process_ticket(meeting_ticket)
        
        # Verify error handling
        assert meeting_ticket.status == TicketStatus.ERROR
        assert len(meeting_ticket.errors) > 0
        assert 'Authentication failed' in meeting_ticket.errors[0]['message']

@pytest.mark.asyncio
async def test_schedule_meeting_calendar_failure(agent, meeting_ticket, mock_service):
    """Test handling of calendar operation failure"""
    # Mock calendar failure after successful auth
    with patch('src.modules.google_calendar.GoogleCalendarModule.execute') as mock_calendar:
        mock_calendar.return_value = {'status': 'error', 'error': 'Failed to create event'}
        
        # Process ticket
        agent_instance = await agent
        await agent_instance.process_ticket(meeting_ticket)
        
        # Verify error handling
        assert meeting_ticket.status == TicketStatus.ERROR
        assert len(meeting_ticket.errors) > 0
        assert 'Failed to create event' in meeting_ticket.errors[0]['message']

@pytest.mark.asyncio
async def test_schedule_meeting_missing_entities(agent):
    """Test handling of missing required entities"""
    # Create ticket with missing entities
    incomplete_ticket = Ticket(
        ticket_id='incomplete_test_123',
        original_message='Schedule a team meeting',
        service='schedule_meeting',
        entities={}  # No entities provided
    )
    
    # Process ticket
    agent_instance = await agent
    await agent_instance.process_ticket(incomplete_ticket)
    
    # Verify error handling
    assert incomplete_ticket.status == TicketStatus.ERROR
    assert len(incomplete_ticket.errors) > 0
    assert any('required' in error['message'].lower() for error in incomplete_ticket.errors) 