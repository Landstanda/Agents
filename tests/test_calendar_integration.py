import pytest
from src.tools.agent import Agent
from src.tools.nlp import Ticket, TicketStatus, NLPAnalyzer
from datetime import datetime, timedelta
import yaml
from pathlib import Path
from src.modules.google_calendar import GoogleCalendarModule
from src.modules.google_auth import GoogleAuthModule
import pytz

@pytest.fixture
async def calendar_module():
    """Initialize a real Google Calendar module."""
    module = GoogleCalendarModule()
    module._initialize_service()  # Ensure we're authenticated
    return module

@pytest.fixture
async def nlp_analyzer():
    """Initialize a real NLP analyzer."""
    analyzer = await NLPAnalyzer.create()
    return analyzer

@pytest.fixture
async def test_agent():
    """Create and initialize a real agent."""
    agent = Agent()
    
    # Create test executions.yaml if it doesn't exist
    executions_path = Path("src/services/executions.yaml")
    executions_path.parent.mkdir(parents=True, exist_ok=True)
    
    executions_config = {
        'schedule_meeting': {
            'executor_type': 'calendar',
            'steps': [
                {
                    'name': 'validate_time',
                    'tool': 'calendar',
                    'action': 'check_availability',
                    'params': {
                        'time': '{time}',
                        'date': '{date}',
                        'timezone': 'America/Los_Angeles'
                    }
                },
                {
                    'name': 'create_event',
                    'tool': 'calendar',
                    'action': 'create_event',
                    'params': {
                        'summary': 'Meeting with {participants}',
                        'description': 'Scheduled via calendar integration test',
                        'start_time': '{time}',
                        'date': '{date}',
                        'attendees': '{participants}',
                        'timezone': 'America/Los_Angeles',
                        'duration': '60'  # 1 hour meeting
                    }
                }
            ]
        }
    }
    
    with open(executions_path, 'w') as f:
        yaml.dump(executions_config, f)
    
    # Load services and tools
    await agent.load_services()
    agent.load_tools()
    return agent

class TestCalendarIntegration:
    @pytest.mark.asyncio
    async def test_schedule_specific_meeting(self, test_agent, nlp_analyzer, calendar_module):
        """Test the full flow from natural language to calendar event creation."""
        # Await the fixtures
        agent = await test_agent
        analyzer = await nlp_analyzer
        cal_module = await calendar_module
        
        # First verify the time slot is available
        timezone = pytz.timezone('America/Los_Angeles')
        target_date = datetime(2025, 2, 15, 21, 0)  # 9 PM
        target_date = timezone.localize(target_date)
        
        # Check initial availability
        check_params = {
            'operation': 'check_availability',
            'start_time': target_date.isoformat(),
            'end_time': (target_date + timedelta(hours=1)).isoformat(),
            'timezone': 'America/Los_Angeles'
        }
        
        print("\nChecking initial availability...")
        avail_result = cal_module.execute(check_params)
        assert avail_result['success']
        assert avail_result['is_available'], "Time slot should be available before scheduling"
        
        # Create a test message
        message = "schedule a meeting with gabi for 9 pm Feb 15th 2025"
        user_info = {'user_id': 'U123', 'channel_id': 'C123'}
        
        # Process with NLP
        print("\nProcessing natural language request...")
        ticket = await analyzer.analyze_message(message, user_info)
        
        # Verify NLP extracted the correct entities
        assert ticket.entities['time'] == '21:00'
        assert ticket.entities['date'] == '2025-02-15'
        assert 'Gabi' in ticket.entities['participants']
        
        # Execute the service
        print("\nExecuting calendar service...")
        result = await agent.execute_service(ticket)
        
        # Verify execution was successful
        assert result['status'] == 'success', f"Service execution failed: {result.get('error', 'Unknown error')}"
        assert ticket.status == TicketStatus.COMPLETED
        assert len(ticket.steps_executed) > 0
        
        # Verify the event details in the execution results
        steps = ticket.steps_executed
        
        # First step should be availability check
        assert steps[0]['tool'] == 'calendar'
        assert steps[0]['action'] == 'check_availability'
        assert steps[0]['params']['time'] == '21:00'
        assert steps[0]['params']['date'] == '2025-02-15'
        
        # Second step should be event creation
        assert steps[1]['tool'] == 'calendar'
        assert steps[1]['action'] == 'create_event'
        assert steps[1]['params']['summary'] == 'Meeting with Gabi'
        assert steps[1]['params']['start_time'] == '21:00'
        assert steps[1]['params']['date'] == '2025-02-15'
        assert 'Gabi' in steps[1]['params']['attendees']
        
        # Verify the event exists by checking availability again
        print("\nVerifying event creation by checking availability...")
        avail_result = cal_module.execute(check_params)
        assert avail_result['success']
        assert not avail_result['is_available'], "Time slot should be blocked after scheduling"
        
        # List the event details
        print("\nListing event details...")
        list_params = {
            'operation': 'list_events',
            'time_min': target_date.isoformat(),
            'time_max': (target_date + timedelta(hours=1)).isoformat(),
            'timezone': 'America/Los_Angeles'
        }
        events = cal_module.execute(list_params)
        assert events['success']
        assert len(events['events']) > 0
        
        event = events['events'][0]
        print(f"\nCreated event details:")
        print(f"Summary: {event['summary']}")
        print(f"Start: {event['start']['dateTime']}")
        print(f"End: {event['end']['dateTime']}")
        print(f"Link: {event['htmlLink']}")
        
        assert event['summary'] == 'Meeting with Gabi'
        assert '2025-02-15' in event['start']['dateTime']
        assert '21:00:00' in event['start']['dateTime'] 