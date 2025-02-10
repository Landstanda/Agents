import pytest
import asyncio
from typing import Dict, Any
from src.office.cookbook.cookbook_manager import CookbookManager
from src.office.task.task_manager import TaskManager
from src.office.reception.front_desk import FrontDesk
from src.office.reception.nlp_processor import NLPProcessor
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def cookbook_manager():
    """Initialize cookbook manager for testing."""
    manager = CookbookManager()
    # Add test recipes
    manager.recipes = {
        "Schedule Meeting": {
            "name": "Schedule Meeting",
            "intent": "schedule_meeting",
            "description": "Schedule a meeting with participants",
            "steps": [
                {"type": "api_call", "name": "check_availability", "endpoint": "calendar/check"},
                {"type": "api_call", "name": "create_meeting", "endpoint": "calendar/create"}
            ],
            "required_entities": ["time", "participants"],
            "keywords": ["schedule", "meeting", "calendar"],
            "common_triggers": ["schedule a meeting", "set up a meeting"]
        },
        "Research Report": {
            "name": "Research Report",
            "intent": "research",
            "description": "Research a topic and create a report",
            "steps": [
                {"type": "api_call", "name": "search", "endpoint": "research/search"},
                {"type": "database_query", "name": "analyze", "query_type": "analysis"}
            ],
            "required_entities": ["topic"],
            "keywords": ["research", "analyze", "report"],
            "common_triggers": ["research about", "analyze topic"]
        },
        "Check Emails": {
            "name": "Check Emails",
            "intent": "email_read",
            "description": "Check and process emails",
            "steps": [
                {"type": "api_call", "name": "fetch_emails", "endpoint": "email/fetch"},
                {"type": "database_query", "name": "process", "query_type": "email_sort"}
            ],
            "required_entities": [],
            "keywords": ["email", "check", "read"],
            "common_triggers": ["check emails", "read emails"]
        }
    }
    return manager

@pytest.fixture
def task_manager():
    """Initialize task manager for testing."""
    return TaskManager()

@pytest.fixture
def nlp_processor():
    """Initialize NLP processor for testing."""
    return NLPProcessor()

@pytest.fixture
def front_desk(cookbook_manager, task_manager):
    """Initialize Front Desk with mocked dependencies."""
    web_client = AsyncMock()
    web_client.chat_postMessage = AsyncMock(return_value={"ok": True})
    web_client.users_info = AsyncMock(return_value={"ok": True, "user": {"real_name": "Test User"}})
    
    return FrontDesk(
        web_client=web_client,
        nlp=NLPProcessor(),
        cookbook=cookbook_manager,  # Use the fixture with test recipes
        task_manager=task_manager,  # Use the fixture
        bot_id="U123"
    )

@pytest.mark.asyncio
async def test_cookbook_to_task_flow(cookbook_manager, task_manager):
    """Test the flow from CookbookManager to TaskManager."""
    # Create a test request
    request = "schedule a meeting for tomorrow at 2pm with @john"
    
    # Process through NLP first to get proper context
    nlp = NLPProcessor()
    nlp_result = await nlp.process_message(request, {"id": "U123", "real_name": "Test User"})
    
    # Ensure NLP result has the expected structure
    nlp_result["intent"] = "schedule_meeting"
    nlp_result["all_intents"] = ["schedule_meeting", "scheduling"]
    nlp_result["entities"] = {
        "time": "tomorrow at 2pm",
        "participants": ["@john"]
    }
    
    # Find matching recipe
    recipe = await cookbook_manager.find_matching_recipe(nlp_result)
    assert recipe is not None, "Should find a matching recipe"
    assert recipe["intent"] == "schedule_meeting"
    
    # Execute recipe through task manager
    context = {
        "nlp_result": nlp_result,
        "user_info": {"id": "U123", "real_name": "Test User"},
        "channel_id": "C123",
        "thread_ts": "1234567890.123"
    }
    
    result = await task_manager.execute_recipe(recipe, context)
    assert result["status"] == "queued"
    
    # Wait for processing
    await asyncio.sleep(0.1)
    
    # Verify task completion
    history = task_manager.get_task_history()
    assert len(history) == 1
    assert history[0]["recipe_name"] == recipe["name"]
    assert history[0]["result"]["status"] == "success"

@pytest.mark.asyncio
async def test_nlp_to_task_flow(nlp_processor, cookbook_manager, task_manager):
    """Test the flow from NLP Processor through CookbookManager to TaskManager."""
    # Start with a raw message
    message = "URGENT: research AI trends and prepare a report ASAP!"  # Added more urgency indicators
    user_info = {"id": "U123", "real_name": "Test User"}
    
    # Process through NLP
    nlp_result = await nlp_processor.process_message(message, user_info)
    assert nlp_result["status"] == "success"
    assert nlp_result["urgency"] > 0.5  # Should detect high urgency
    assert "research" in nlp_result.get("all_intents", [])
    
    # Find matching recipe
    recipe = await cookbook_manager.find_matching_recipe(nlp_result)
    assert recipe is not None
    assert recipe["intent"] == "research"
    
    # Execute through task manager
    context = {
        "nlp_result": nlp_result,
        "user_info": user_info,
        "channel_id": "C123",
        "thread_ts": "1234567890.123"
    }
    
    result = await task_manager.execute_recipe(recipe, context)
    assert result["status"] == "queued"
    
    # Wait for processing
    await asyncio.sleep(0.1)
    
    # Verify task completion and urgency handling
    history = task_manager.get_task_history()
    assert len(history) == 1
    assert history[0]["urgency"] > 0.5
    assert history[0]["result"]["status"] == "success"

@pytest.mark.asyncio
async def test_front_desk_to_task_flow(front_desk):
    """Test the complete flow from Front Desk through all components to TaskManager."""
    # Mock the NLP processor to return expected results
    front_desk.nlp.process_message = AsyncMock(return_value={
        "status": "success",
        "intent": "schedule_meeting",
        "all_intents": ["schedule_meeting", "scheduling"],
        "entities": {
            "time": "tomorrow at 2pm",
            "participants": ["@john"]
        },
        "urgency": 0.8
    })
    
    # Simulate a Slack message
    message = {
        "type": "message",
        "channel": "C123",
        "user": "U456",
        "text": "<@U123> URGENT: schedule a meeting with @john tomorrow at 2pm!!",
        "ts": "1234567890.123"
    }
    
    # Process through Front Desk
    await front_desk.handle_message(message)
    
    # Wait for processing
    await asyncio.sleep(0.3)
    
    # Verify task execution in task manager
    task_history = front_desk.task_manager.get_task_history()
    assert len(task_history) == 1
    assert task_history[0]["result"]["status"] == "success"
    assert task_history[0]["urgency"] > 0.5

@pytest.mark.asyncio
async def test_priority_handling_flow(front_desk):
    """Test that tasks are properly prioritized through the entire flow."""
    # Mock NLP processor with different urgency levels
    nlp_results = [
        {
            "status": "success",
            "intent": "email_read",
            "all_intents": ["email_read"],
            "entities": {},
            "urgency": 0.2
        },
        {
            "status": "success",
            "intent": "schedule_meeting",
            "all_intents": ["schedule_meeting", "scheduling"],
            "entities": {"time": "now", "participants": ["@john"]},
            "urgency": 0.9
        },
        {
            "status": "success",
            "intent": "research",
            "all_intents": ["research"],
            "entities": {"topic": "AI trends"},
            "urgency": 0.5
        }
    ]
    
    nlp_mock = AsyncMock()
    nlp_mock.process_message = AsyncMock()
    nlp_mock.process_message.side_effect = nlp_results
    front_desk.nlp = nlp_mock
    
    # Create messages with different urgency levels
    messages = [
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> check my emails when you have time",
            "ts": "1234567890.123"
        },
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> URGENT: schedule meeting with @john ASAP!!",
            "ts": "1234567890.124"
        },
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> research AI trends by tomorrow",
            "ts": "1234567890.125"
        }
    ]
    
    # Temporarily disable task processing
    front_desk.task_manager._processing = True
    
    # Submit all messages quickly
    for message in messages:
        await front_desk.handle_message(message)
    
    # Wait a moment for all tasks to be queued
    await asyncio.sleep(0.1)
    
    # Enable task processing
    front_desk.task_manager._processing = False
    asyncio.create_task(front_desk.task_manager._process_queue())
    
    # Wait for processing to complete
    await asyncio.sleep(0.8)
    
    # Verify task execution order based on urgency
    task_history = front_desk.task_manager.get_task_history()
    assert len(task_history) == 3
    
    # Sort tasks by start_time to get execution order
    sorted_tasks = sorted(task_history, key=lambda x: x["start_time"])
    
    # First task should be highest urgency (0.9)
    assert sorted_tasks[0]["urgency"] == 0.9, "Highest urgency task (0.9) should be executed first"
    
    # Second task should be medium urgency (0.5)
    assert sorted_tasks[1]["urgency"] == 0.5, "Medium urgency task (0.5) should be executed second"
    
    # Third task should be lowest urgency (0.2)
    assert sorted_tasks[2]["urgency"] == 0.2, "Lowest urgency task (0.2) should be executed last"

@pytest.mark.asyncio
async def test_error_propagation_flow(front_desk):
    """Test error handling and propagation through the entire flow."""
    # Create a message that should trigger an invalid recipe
    message = {
        "type": "message",
        "channel": "C123",
        "user": "U456",
        "text": "<@U123> execute invalid task type",
        "ts": "1234567890.123"
    }
    
    # Process message
    await front_desk.handle_message(message)
    
    # Wait for processing
    await asyncio.sleep(0.2)
    
    # Verify error was properly handled
    task_history = front_desk.task_manager.get_task_history()
    if task_history:  # If task made it to task manager
        assert task_history[-1]["result"]["status"] == "error"
    
    # Verify error message was sent to Slack
    front_desk.web_client.chat_postMessage.assert_called()

@pytest.mark.asyncio
async def test_equal_urgency_ordering(front_desk):
    """Test that tasks with equal urgency maintain FIFO order."""
    # Mock NLP processor with equal urgency levels
    nlp_results = [
        {
            "status": "success",
            "intent": "email_read",
            "all_intents": ["email_read"],
            "entities": {},
            "urgency": 0.5
        },
        {
            "status": "success",
            "intent": "schedule_meeting",
            "all_intents": ["schedule_meeting"],
            "entities": {"time": "now", "participants": ["@john"]},
            "urgency": 0.5
        },
        {
            "status": "success",
            "intent": "research",
            "all_intents": ["research"],
            "entities": {"topic": "AI trends"},
            "urgency": 0.5
        }
    ]
    
    nlp_mock = AsyncMock()
    nlp_mock.process_message = AsyncMock()
    nlp_mock.process_message.side_effect = nlp_results
    front_desk.nlp = nlp_mock
    
    messages = [
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> check my emails",
            "ts": "1234567890.123"
        },
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> schedule meeting with @john",
            "ts": "1234567890.124"
        },
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> research AI trends",
            "ts": "1234567890.125"
        }
    ]
    
    # Temporarily disable task processing
    front_desk.task_manager._processing = True
    
    # Submit messages
    for message in messages:
        await front_desk.handle_message(message)
    
    await asyncio.sleep(0.1)
    
    # Enable task processing
    front_desk.task_manager._processing = False
    asyncio.create_task(front_desk.task_manager._process_queue())
    
    await asyncio.sleep(0.8)
    
    # Verify FIFO order maintained
    task_history = front_desk.task_manager.get_task_history()
    assert len(task_history) == 3
    
    sorted_tasks = sorted(task_history, key=lambda x: x["start_time"])
    assert sorted_tasks[0]["recipe_name"] == "Check Emails"
    assert sorted_tasks[1]["recipe_name"] == "Schedule Meeting"
    assert sorted_tasks[2]["recipe_name"] == "Research Report"

@pytest.mark.asyncio
async def test_task_queue_overflow(front_desk):
    """Test that task manager handles a realistic burst of activity."""
    # Create a realistic burst of tasks (simulating a busy period)
    nlp_results = [
        # Urgent meeting request
        {
            "status": "success",
            "intent": "schedule_meeting",
            "all_intents": ["schedule_meeting"],
            "entities": {"time": "now", "participants": ["@team"]},
            "urgency": 0.9
        },
        # Regular email check
        {
            "status": "success",
            "intent": "email_read",
            "all_intents": ["email_read"],
            "entities": {},
            "urgency": 0.3
        },
        # Important research request
        {
            "status": "success",
            "intent": "research",
            "all_intents": ["research"],
            "entities": {"topic": "quarterly report"},
            "urgency": 0.7
        },
        # Another meeting
        {
            "status": "success",
            "intent": "schedule_meeting",
            "all_intents": ["schedule_meeting"],
            "entities": {"time": "tomorrow", "participants": ["@john"]},
            "urgency": 0.5
        },
        # Document request
        {
            "status": "success",
            "intent": "document",
            "all_intents": ["document"],
            "entities": {"doc_type": "report"},
            "urgency": 0.4
        }
    ]

    messages = [
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> URGENT: Schedule team meeting now!",
            "ts": "1234567890.123"
        },
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> check my emails",
            "ts": "1234567890.124"
        },
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> research for quarterly report - important",
            "ts": "1234567890.125"
        },
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> schedule meeting with @john for tomorrow",
            "ts": "1234567890.126"
        },
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> create a report document",
            "ts": "1234567890.127"
        }
    ]

    nlp_mock = AsyncMock()
    nlp_mock.process_message = AsyncMock()
    nlp_mock.process_message.side_effect = nlp_results
    front_desk.nlp = nlp_mock

    # Temporarily disable task processing while queueing
    front_desk.task_manager._processing = True

    # Submit tasks with realistic timing
    for message in messages:
        await front_desk.handle_message(message)
        await asyncio.sleep(0.2)  # Simulate slight delay between messages

    # Enable processing
    front_desk.task_manager._processing = False
    process_task = asyncio.create_task(front_desk.task_manager._process_queue())

    # Wait for all tasks to be processed (1 second per task plus buffer)
    await asyncio.sleep(3.0)

    # Verify tasks were handled properly
    task_history = front_desk.task_manager.get_task_history()
    assert len(task_history) == len(messages), "All tasks should be processed"

    # Verify tasks were processed in priority order
    task_urgencies = [task["urgency"] for task in task_history]
    assert task_urgencies == sorted(task_urgencies, reverse=True), "Tasks should be processed in priority order"

@pytest.mark.asyncio
async def test_long_running_task_handling(front_desk):
    """Test handling of long-running tasks with different urgencies."""
    # Mock a long-running task
    async def slow_api_call(*args, **kwargs):
        await asyncio.sleep(0.5)  # Simulate long API call
        return {"status": "success", "details": "Long task completed"}
    
    # Replace API handler with slow version
    front_desk.task_manager._handle_api_call = slow_api_call
    
    # Create tasks with different urgencies
    nlp_results = [
        {
            "status": "success",
            "intent": "research",
            "all_intents": ["research"],
            "entities": {"topic": "topic1"},
            "urgency": 0.9
        },
        {
            "status": "success",
            "intent": "research",
            "all_intents": ["research"],
            "entities": {"topic": "topic2"},
            "urgency": 0.5
        }
    ]
    
    nlp_mock = AsyncMock()
    nlp_mock.process_message = AsyncMock()
    nlp_mock.process_message.side_effect = nlp_results
    front_desk.nlp = nlp_mock
    
    messages = [
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> research topic1",
            "ts": "1234567890.123"
        },
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> research topic2",
            "ts": "1234567890.124"
        }
    ]
    
    # Submit tasks
    for message in messages:
        await front_desk.handle_message(message)
    
    # Wait for processing
    await asyncio.sleep(1.5)
    
    # Verify tasks completed in priority order despite long execution time
    task_history = front_desk.task_manager.get_task_history()
    assert len(task_history) == 2
    
    sorted_tasks = sorted(task_history, key=lambda x: x["start_time"])
    assert sorted_tasks[0]["urgency"] == 0.9
    assert sorted_tasks[1]["urgency"] == 0.5

@pytest.mark.asyncio
async def test_recovery_after_failure(front_desk):
    """Test system recovers and continues processing after task failures."""
    # Mock NLP processor with tasks that will succeed and fail
    nlp_results = [
        {
            "status": "success",
            "intent": "invalid_intent",  # This will cause failure
            "all_intents": ["invalid"],
            "entities": {},
            "urgency": 0.9
        },
        {
            "status": "success",
            "intent": "email_read",  # This should succeed
            "all_intents": ["email_read"],
            "entities": {},
            "urgency": 0.5
        }
    ]

    nlp_mock = AsyncMock()
    nlp_mock.process_message = AsyncMock()
    nlp_mock.process_message.side_effect = nlp_results
    front_desk.nlp = nlp_mock

    messages = [
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> invalid task",
            "ts": "1234567890.123"
        },
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> check my emails",
            "ts": "1234567890.124"
        }
    ]

    # Submit tasks
    for message in messages:
        await front_desk.handle_message(message)
        await asyncio.sleep(0.2)  # Add delay between messages

    # Wait for processing (2 seconds total)
    await asyncio.sleep(2.0)

    # Verify system recovered and processed second task
    task_history = front_desk.task_manager.get_task_history()

    # Find successful task
    successful_tasks = [t for t in task_history if t["result"]["status"] == "success"]
    assert len(successful_tasks) > 0, "Should have at least one successful task"
    assert successful_tasks[0]["recipe_name"] == "Check Emails"

    # Verify error was handled
    error_tasks = [t for t in task_history if t.get("result", {}).get("status") == "error"]
    assert len(error_tasks) > 0, "Should have at least one error task" 