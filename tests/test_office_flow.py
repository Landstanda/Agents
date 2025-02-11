import pytest
import logging
import sys
from datetime import datetime
from unittest.mock import Mock, patch
from src.office.reception.front_desk import FrontDesk
from src.office.executive.ceo import CEO
from src.office.cookbook.cookbook_manager import CookbookManager
from src.office.task.task_manager import TaskManager
from src.office.reception.nlp_processor import NLPProcessor
from src.office.reception.request_tracker import RequestTracker

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(message)s',
    stream=sys.stdout
)

def setup_test_logging():
    """Configure logging for tests"""
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)

@pytest.fixture(autouse=True)
def setup_logging():
    setup_test_logging()
    yield

def print_flow_step(title, details, show_arrow=True):
    """Print a single step in the message flow with optional arrow"""
    print("\n" + "="*80)
    print(f"📍 {title}")
    print("-"*80)
    for key, value in details.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for k, v in value.items():
                print(f"  - {k}: {v}")
        else:
            print(f"{key}: {value}")
    if show_arrow:
        print("\n        ⬇️")

def print_office_response(message):
    """Print a response from the office to the user"""
    print("\n" + "="*80)
    print("💬 OFFICE RESPONSE")
    print("-"*80)
    print(f"Message: {message}")
    print("\n        ⬇️")

@pytest.fixture
def office_components():
    """Create and connect all office components"""
    cookbook = CookbookManager()
    task_manager = TaskManager()
    nlp = NLPProcessor(cookbook_manager=cookbook)
    ceo = CEO(cookbook_manager=cookbook, task_manager=task_manager)
    request_tracker = RequestTracker()
    
    front_desk = FrontDesk(
        nlp=nlp,
        cookbook=cookbook,
        task_manager=task_manager,
        ceo=ceo
    )
    front_desk.request_tracker = request_tracker
    
    return {
        'front_desk': front_desk,
        'ceo': ceo,
        'cookbook': cookbook,
        'task_manager': task_manager,
        'nlp': nlp,
        'request_tracker': request_tracker
    }

@pytest.fixture
def mock_gpt_responses():
    """Mock GPT responses for office communications"""
    with patch('openai.AsyncOpenAI') as mock_openai:
        mock_openai.return_value.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="""name: Meeting Scheduler
description: Schedule a meeting with participants
intent: schedule_meeting
steps:
  - action: check_availability
    params:
      time: "{time}"
      participants: "{participants}"
  - action: create_meeting
    params:
      time: "{time}"
      participants: "{participants}"
common_triggers:
  - "schedule a meeting"
  - "set up a meeting"
required_entities:
  - time
  - participants
success_criteria:
  - "Meeting scheduled"
  - "Participants notified"
"""))]),
            Mock(choices=[Mock(message=Mock(content="I see you want to schedule a meeting. What time would you like to schedule it for?"))]),
            Mock(choices=[Mock(message=Mock(content="Great, I have the time. Who would you like to invite to this meeting?"))]),
            Mock(choices=[Mock(message=Mock(content="Perfect! I'll schedule the meeting for {time} with {participants}. Is there anything else you need?"))])
        ]
        yield mock_openai

def print_test_summary(test_name: str, request=None, validation=None, error=None):
    """Print a clean summary of the test results"""
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    print(f"Test: {test_name}")
    print("-"*40)
    
    if error:
        print("❌ Test Failed:")
        print(f"Error: {error}")
        return
        
    if request:
        print("📝 Final Request State:")
        print(f"  Status: {request.status}")
        print("  Collected Information:")
        for key, value in request.entities.items():
            if value:
                print(f"    • {key}: {value}")
    
    if validation:
        print("\n🔍 Validation Result:")
        print(f"  Status: {validation['status']}")
        if validation.get('missing_requirements'):
            print("  Missing Requirements:")
            for req in validation['missing_requirements']:
                print(f"    • {req}")
    
    print("\n✅ Test Completed Successfully")

@pytest.mark.asyncio
async def test_message_flow_through_office(office_components, mock_gpt_responses):
    """Test how a message flows through the office with detailed logging"""
    try:
        print("\n" + "="*80)
        print("🏢 Office Assistant Flow Test")
        print("="*80)

        # Simulate incoming message
        message = {
            "type": "message",
            "channel": "C123456",
            "user": "U123456",
            "text": "Can you help me schedule a meeting with John tomorrow at 2pm?",
            "ts": "1234567890.123456"
        }
        
        front_desk = office_components['front_desk']
        
        print("\n📨 Incoming Message")
        print(f"User: {message['text']}")
        print("\n        ⬇️")
        
        # 1. NLP Processing Stage
        print("\n🧠 NLP Processor")
        print("-"*40)
        nlp_result = await front_desk.nlp.process_message(message['text'], {"real_name": "User"}, message['channel'])
        print("Breaking down the message:")
        print(f"  Intent: {nlp_result.get('intent')}")
        print("  Entities found:")
        for key, value in nlp_result.get('entities', {}).items():
            if value:  # Only show non-empty entities
                print(f"    • {key}: {value}")
        print("\n        ⬇️")
        
        # 2. Front Desk Initial Processing
        print("\n👩‍💼 Front Desk")
        print("-"*40)
        print("Creating new request and checking recipe requirements...")
        await front_desk.handle_message(message)
        request = front_desk.request_tracker.get_active_request(message['channel'], message['user'])
        
        # 3. Request Tracker State
        print("\n📝 Request Tracker - Initial State")
        print("-"*40)
        print(f"Request ID: {request.request_id}")
        print(f"Status: {request.status}")
        print("Stored Information:")
        for key, value in request.entities.items():
            if value:  # Only show non-empty entities
                print(f"  • {key}: {value}")
        if hasattr(request, 'missing_entities') and request.missing_entities:
            print("Missing Information:")
            for entity in request.missing_entities:
                print(f"  • {entity}")
        print("\n        ⬇️")
        
        # 4. Cookbook Validation
        print("\n📖 Cookbook Manager")
        print("-"*40)
        validation = front_desk.cookbook._validate_recipe_requirements(request.recipe, nlp_result)
        print(f"Recipe: {request.recipe.get('name')}")
        print(f"Status: {validation['status']}")
        if validation.get('missing_requirements'):
            print("Missing Requirements:")
            for req in validation['missing_requirements']:
                print(f"  • {req}")
        print("\n        ⬇️")
        
        # 5. Front Desk Response
        print("\n👩‍💼 Front Desk Response")
        print("-"*40)
        if validation['status'] == 'success':
            print("All information collected, proceeding to task manager...")
        else:
            print(f"Need to request more information: {', '.join(validation.get('missing_requirements', []))}")
        print("\n        ⬇️")
        
        # 6. Task Manager (if we have all info)
        if validation['status'] == 'success':
            print("\n📋 Task Manager")
            print("-"*40)
            print("Creating task from recipe...")
            print(f"Recipe: {request.recipe.get('name')}")
            print("Steps to execute:")
            for i, step in enumerate(request.recipe.get('steps', []), 1):
                print(f"  {i}. {step['action']}")
                for param, value in step['params'].items():
                    print(f"     • {param}: {value}")
        
        # Add summary at the end
        print_test_summary(
            "Single-Step Message Flow",
            request=request,
            validation=validation
        )
        
    except Exception as e:
        print_test_summary("Single-Step Message Flow", error=str(e))
        raise

@pytest.mark.asyncio
async def test_multi_step_conversation_flow(office_components, mock_gpt_responses):
    """Test how the office handles a conversation that requires multiple interactions"""
    try:
        # Mock both Slack API calls
        with patch('slack_sdk.web.async_client.AsyncWebClient.chat_postMessage') as mock_post, \
             patch('slack_sdk.web.async_client.AsyncWebClient.users_info') as mock_user_info:
            
            mock_post.return_value = {"ok": True, "ts": "123.456"}
            mock_user_info.return_value = {
                "ok": True,
                "user": {"real_name": "Test User", "id": "U123456"}
            }
            
            front_desk = office_components['front_desk']
            
            print("\n" + "="*80)
            print("🔄 CONVERSATION FLOW")
            print("="*80)
            
            # Step 1: Initial Request
            print("\n📝 STEP 1: User wants to schedule a meeting")
            print("-"*40)
            initial_message = {
                "type": "message",
                "channel": "C123456",
                "user": "U123456",
                "text": "I need to set up a team meeting",
                "ts": "1234567890.123456"
            }
            print(f"User: {initial_message['text']}")
            print("\n⬇️  NLP Processing")
            
            nlp_result = await front_desk.nlp.process_message(initial_message['text'], {"real_name": "User"}, initial_message['channel'])
            print(f"Intent: {nlp_result.get('intent')}")
            print("Entities: None")
            
            await front_desk.handle_message(initial_message)
            request = front_desk.request_tracker.get_active_request(initial_message['channel'], initial_message['user'])
            
            print("\n⬇️  Request Tracker")
            print(f"Status: {request.status}")
            print("Missing: time, participants")
            
            print("\n⬇️  Front Desk Response")
            print("Office: I see you want to schedule a meeting. What time would you like to schedule it for?")
            
            # Step 2: Time Information
            print("\n📝 STEP 2: User provides time")
            print("-"*40)
            time_message = {
                "type": "message",
                "channel": "C123456",
                "user": "U123456",
                "text": "Tomorrow at 3pm",
                "ts": "1234567890.123457"
            }
            print(f"User: {time_message['text']}")
            print("\n⬇️  NLP Processing")
            
            nlp_result = await front_desk.nlp.process_message(time_message['text'], {"real_name": "User"}, time_message['channel'])
            print("Entities found:")
            print(f"  • time: {nlp_result.get('entities', {}).get('time')}")
            
            await front_desk.handle_message(time_message)
            request = front_desk.request_tracker.get_active_request(time_message['channel'], time_message['user'])
            
            print("\n⬇️  Request Tracker")
            print(f"Status: {request.status}")
            print(f"Stored: time = {request.entities.get('time')}")
            print("Missing: participants")
            
            print("\n⬇️  Front Desk Response")
            print("Office: Great, I have the time. Who would you like to invite to this meeting?")
            
            # Step 3: Participants Information
            print("\n📝 STEP 3: User provides participants")
            print("-"*40)
            participants_message = {
                "type": "message",
                "channel": "C123456",
                "user": "U123456",
                "text": "with John and Mary",
                "ts": "1234567890.123458"
            }
            print(f"User: {participants_message['text']}")
            print("\n⬇️  NLP Processing")
            
            nlp_result = await front_desk.nlp.process_message(participants_message['text'], {"real_name": "User"}, participants_message['channel'])
            print("Entities found:")
            print(f"  • participants: {nlp_result.get('entities', {}).get('participants')}")
            
            await front_desk.handle_message(participants_message)
            request = front_desk.request_tracker.get_active_request(participants_message['channel'], participants_message['user'])
            
            print("\n⬇️  Request Tracker")
            print(f"Status: {request.status}")
            print("All Information Collected:")
            print(f"  • time: {request.entities.get('time')}")
            print(f"  • participants: {request.entities.get('participants')}")
            
            print("\n⬇️  Task Creation")
            print(f"Recipe: {request.recipe.get('name')}")
            print("Steps:")
            for i, step in enumerate(request.recipe.get('steps', []), 1):
                print(f"  {i}. {step['action']}")
                for param, value in step['params'].items():
                    print(f"     • {param}: {value}")
            
            print("\n⬇️  Final Response")
            print(f"Office: Perfect! I'll schedule the meeting for {request.entities.get('time')} with {', '.join(request.entities.get('participants', []))}. Is there anything else you need?")
            
            print("\n" + "="*80)
            print("✅ Conversation Complete")
            print("="*80)
            
    except Exception as e:
        print(f"\n❌ Test Failed: {str(e)}")
        raise 