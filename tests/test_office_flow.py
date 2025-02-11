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
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stdout
)

def setup_test_logging():
    """Configure logging for tests with timestamps"""
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)

@pytest.fixture(autouse=True)
def setup_logging():
    setup_test_logging()
    yield

def print_section(title, content=None, level=1):
    """Print a section with consistent formatting"""
    border = "=" if level == 1 else "-" if level == 2 else "."
    print(f"\n{border * 80}")
    print(f"{'#' * level} {title}")
    print(f"{border * 80}")
    if content:
        if isinstance(content, dict):
            for key, value in content.items():
                if isinstance(value, dict):
                    print(f"{key}:")
                    for k, v in value.items():
                        print(f"  - {k}: {v}")
                else:
                    print(f"{key}: {value}")
        else:
            print(content)
    print(f"\n        ⬇️")

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
    """Mock GPT responses for testing"""
    with patch('openai.AsyncOpenAI') as mock_openai:
        # Mock for existing recipe test
        mock_openai.return_value.chat.completions.create.side_effect = [
            # Front desk responses
            Mock(choices=[Mock(message=Mock(content="I'll help you schedule a meeting. What time works for you?"))]),
            Mock(choices=[Mock(message=Mock(content="Great! Who would you like to invite?"))]),
            Mock(choices=[Mock(message=Mock(content="Perfect! I'll schedule that for you right away."))]),
            
            # CEO new recipe creation
            Mock(choices=[Mock(message=Mock(content="""
name: Research Report
description: Research a topic and create a detailed report
intent: research_report
common_triggers:
  - "research about"
  - "create a report about"
  - "analyze and report on"
required_entities:
  - topic
  - depth
steps:
  - action: web_research
    params:
      topic: "{topic}"
      depth: "{depth}"
  - action: analyze_data
    params:
      format: "report"
success_criteria:
  - "Research completed"
  - "Report generated"
"""))]),
        ]
        yield mock_openai

@pytest.mark.asyncio
async def test_existing_recipe_flow(office_components, mock_gpt_responses):
    """Test processing a request that matches an existing recipe"""
    print_section("Testing Existing Recipe Flow", "Testing schedule meeting recipe")
    
    message = {
        "type": "message",
        "channel": "C123456",
        "user": "U123456",
        "text": "Schedule a meeting with John tomorrow at 2pm",
        "ts": "1234567890.123456"
    }
    
    front_desk = office_components['front_desk']
    
    # 1. NLP Processing
    print_section("NLP Processing", level=2)
    nlp_result = await front_desk.nlp.process_message(
        message['text'], 
        {"real_name": "User"}, 
        message['channel']
    )
    print(f"Intent: {nlp_result.get('intent')}")
    print("Entities:")
    for key, value in nlp_result.get('entities', {}).items():
        if value:
            print(f"  • {key}: {value}")
    
    # 2. Recipe Matching
    print_section("Recipe Matching", level=2)
    cookbook_response = front_desk.cookbook.get_recipe(nlp_result.get('intent'))
    print(f"Recipe Found: {cookbook_response['recipe']['name'] if cookbook_response.get('recipe') else 'None'}")
    print(f"Status: {cookbook_response['status']}")
    
    # 3. Task Creation
    print_section("Task Manager Processing", level=2)
    if cookbook_response['status'] == 'success':
        result = await front_desk.task_manager.execute_recipe(
            cookbook_response['recipe'],
            {"nlp_result": nlp_result}
        )
        print(f"Execution Status: {result['status']}")
        print(f"Details: {result.get('details', 'No details')}")
    
    assert cookbook_response['status'] == 'success'

@pytest.mark.asyncio
async def test_ceo_recipe_creation(office_components, mock_gpt_responses):
    """Test CEO creating a new recipe for an unknown request"""
    print_section("Testing CEO Recipe Creation", "Testing research report recipe creation")
    
    message = {
        "type": "message",
        "channel": "C123456",
        "user": "U123456",
        "text": "Can you research and create a detailed report about AI trends?",
        "ts": "1234567890.123456"
    }
    
    front_desk = office_components['front_desk']
    
    # 1. NLP Processing
    print_section("NLP Processing", level=2)
    nlp_result = await front_desk.nlp.process_message(
        message['text'], 
        {"real_name": "User"}, 
        message['channel']
    )
    print(f"Intent: {nlp_result.get('intent')}")
    print("Entities:")
    for key, value in nlp_result.get('entities', {}).items():
        if value:
            print(f"  • {key}: {value}")
    
    # 2. CEO Analysis
    print_section("CEO Analysis", level=2)
    ceo_response = await front_desk.ceo.consider_request(
        message['text'],
        {"nlp_result": nlp_result}
    )
    print(f"Status: {ceo_response['status']}")
    print(f"Decision: {ceo_response['decision']}")
    print(f"Confidence: {ceo_response['confidence']}")
    
    if ceo_response.get('recipe'):
        print("\nNew Recipe Created:")
        print(f"Name: {ceo_response['recipe']['name']}")
        print(f"Intent: {ceo_response['recipe']['intent']}")
        print("Steps:")
        for step in ceo_response['recipe']['steps']:
            print(f"  - {step['action']}")
    
    # 3. Recipe Storage
    print_section("Recipe Storage", level=2)
    if ceo_response['status'] == 'success':
        added = await front_desk.cookbook.add_recipe(ceo_response['recipe'])
        print(f"Recipe Added: {added}")
        
        # Verify recipe was stored
        stored_recipe = front_desk.cookbook.get_recipe(ceo_response['recipe']['intent'])
        print(f"Recipe Retrievable: {stored_recipe['status'] == 'success'}")
    
    assert ceo_response['status'] == 'success'
    assert ceo_response.get('recipe') is not None

def print_test_summary(test_name: str, request=None, validation=None, error=None):
    """Print a clean summary of the test results"""
    print_section("Test Summary", level=1)
    print(f"Test: {test_name}")
    
    if error:
        print("❌ Test Failed:")
        print(f"Error: {error}")
        return
        
    if request:
        print("📝 Final Request State:")
        print(f"Status: {request.status}")
        print("Collected Information:")
        for key, value in request.entities.items():
            if value:
                print(f"  • {key}: {value}")
    
    if validation:
        print("\n🔍 Validation Result:")
        print(f"Status: {validation['status']}")
        if validation.get('missing_requirements'):
            print("Missing Requirements:")
            for req in validation['missing_requirements']:
                print(f"  • {req}")
    
    print("\n✅ Test Completed Successfully") 