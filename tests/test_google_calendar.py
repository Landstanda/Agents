import pytest
from unittest.mock import MagicMock, AsyncMock
import pytz
from datetime import datetime, timedelta
from src.modules.google_calendar import GoogleCalendarModule

@pytest.fixture
def mock_google_auth(mocker):
    mock = AsyncMock()
    mock.execute.return_value = {
        'success': True,
        'credentials': MagicMock()
    }
    mocker.patch('src.modules.google_auth.GoogleAuthModule', return_value=mock)
    return mock

@pytest.fixture
def mock_calendar_service(mocker):
    mock = MagicMock()
    mocker.patch('src.modules.google_calendar.build', return_value=mock)
    return mock

@pytest.fixture
async def calendar_module(mock_google_auth, mock_calendar_service):
    module = GoogleCalendarModule()
    await module._initialize_service()
    return module

@pytest.fixture
async def real_calendar_module():
    """Create a calendar module with real credentials"""
    module = GoogleCalendarModule()
    await module._initialize_service()
    return module

@pytest.mark.asyncio
class TestGoogleCalendarModule:
    async def test_create_breakfast_event(self, calendar_module):
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

        # Create the event
        result = await calendar_module.execute(params)
        assert result['success'] is True
        assert 'event_id' in result

    async def test_check_availability(self, calendar_module):
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

        # Check availability
        result = await calendar_module.execute(params)
        assert result['success'] is True
        assert 'is_available' in result

    async def test_create_event(self, calendar_module, mock_calendar_service):
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

        # Execute operation
        result = await calendar_module.execute(params)

        # Verify result
        assert result['success'] is True
        assert result['event_id'] == 'test_event_id'
        assert result['html_link'] == 'https://calendar.google.com/event?id=test'

    async def test_list_events(self, calendar_module, mock_calendar_service):
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

        # Execute operation
        result = await calendar_module.execute(params)

        # Verify result
        assert result['success'] is True
        assert len(result['events']) == 1
        assert result['events'][0]['id'] == 'event1'
        
        # Verify mock calls
        mock_calendar_service.events.assert_called_once()
        events_mock.list.assert_called_once()
        list_mock.execute.assert_called_once()

    async def test_error_handling(self, calendar_module, mock_calendar_service):
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

        # Execute operation
        result = await calendar_module.execute(params)

        # Verify error handling
        assert result['success'] is False
        assert 'error' in result
        assert 'API Error' in result['error']

    async def test_list_all_events(self, calendar_module):
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

        print(f"\nListing all events for {day_start.strftime('%A, %B %d, %Y')}:")
        result = await calendar_module.execute(params)
        assert result['success'] is True
        assert 'events' in result
        
        # Also list events for the specific time we're interested in
        print(f"\nChecking specific time slot (9:15 AM):")
        target_time = target_date.replace(hour=9, minute=15, second=0, microsecond=0)
        params = {
            'operation': 'list_events',
            'time_min': target_time.isoformat(),
            'time_max': (target_time + timedelta(hours=1)).isoformat(),
            'timezone': 'America/Los_Angeles'
        }
        
        result = await calendar_module.execute(params)
        if result['success']:
            events = result['events']
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
    async def test_create_real_event(self, real_calendar_module):
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

        # Create the event
        result = await calendar_module.execute(params)
        
        print(f"\nResult: {result}")

        # Verify the result
        assert result['success'] is True
        assert 'event_id' in result
        assert 'html_link' in result

        # Print the event link
        print(f"\nEvent created successfully!")
        print(f"Event ID: {result['event_id']}")
        print(f"Event Link: {result['html_link']}") 