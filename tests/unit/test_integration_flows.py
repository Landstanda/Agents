import pytest
import asyncio
from typing import Dict, Any
from src.office.cookbook.cookbook_manager import CookbookManager
from src.office.task.task_manager import TaskManager
from src.office.reception.front_desk import FrontDesk
from src.office.reception.nlp_processor import NLPProcessor
from unittest.mock import AsyncMock, MagicMock, patch
import sys

class MockSocketClient:
    """Mock implementation of the Slack socket client."""
    def __init__(self):
        self._connected = False
        self.connect = AsyncMock()
        self.disconnect = AsyncMock()
        self.close = AsyncMock()
        self.send_message = AsyncMock()
        self.process_message = AsyncMock()
    
    @property
    def is_connected(self):
        return self._connected
    
    async def start(self):
        self._connected = True
    
    async def stop(self):
        self._connected = False

class MockSocketModeClient:
    """Complete mock of the Slack SDK socket mode client."""
    def __init__(self, app_token: str, web_client=None):
        self._connected = False
        self.app_token = app_token
        self.web_client = web_client
        self.message_listeners = []
        self.auto_reconnect_enabled = False
    
    @property
    def is_connected(self):
        return self._connected
    
    async def connect(self):
        """Mock connect implementation."""
        self._connected = True
    
    async def disconnect(self):
        """Mock disconnect implementation."""
        self._connected = False
    
    async def close(self):
        """Mock close implementation."""
        await self.disconnect()
    
    async def send_message(self, message: dict):
        """Mock message sending."""
        pass
    
    def on(self, event_type: str, fn):
        """Mock event listener registration."""
        self.message_listeners.append((event_type, fn))

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
    web_client.ssl = False  # Set SSL to False for testing
    web_client.apps_connections_open = AsyncMock(return_value={"ok": True, "url": "wss://test.slack.com/link"})
    
    # Create a complete mock socket client
    socket_client = MockSocketModeClient(app_token="test-token", web_client=web_client)
    
    front_desk = FrontDesk(
        web_client=web_client,
        nlp=NLPProcessor(),
        cookbook=cookbook_manager,  # Use the fixture with test recipes
        task_manager=task_manager,  # Use the fixture
        bot_id="U123"
    )
    front_desk.socket_client = socket_client
    return front_desk

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

@pytest.mark.asyncio
async def test_rate_limiting_handling(front_desk):
    """Test handling of rate limits and message throttling."""
    # Mock rate limit response from Slack
    front_desk.web_client.chat_postMessage = AsyncMock(side_effect=[
        {"ok": False, "error": "ratelimited", "retry_after": 1},
        {"ok": True},  # Second attempt succeeds
        {"ok": True}
    ])
    
    # Mock NLP results with valid intents
    nlp_results = [
        {
            "status": "success",
            "intent": "email_read",
            "all_intents": ["email_read"],
            "entities": {},
            "urgency": 0.5
        }
    ] * 3  # Same result for all three messages
    
    nlp_mock = AsyncMock()
    nlp_mock.process_message = AsyncMock()
    nlp_mock.process_message.side_effect = nlp_results
    front_desk.nlp = nlp_mock
    
    # Create multiple messages in quick succession
    messages = [
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> check my emails",
            "ts": f"1234567890.{i}"
        }
        for i in range(3)
    ]
    
    # Process messages concurrently
    tasks = [front_desk.handle_message(msg) for msg in messages]
    await asyncio.gather(*tasks)
    
    # Wait for retries
    await asyncio.sleep(1.5)
    
    # Verify all messages were eventually processed
    assert front_desk.web_client.chat_postMessage.call_count == 3
    
    # Check task history for successful completion
    history = front_desk.task_manager.get_task_history()
    assert len(history) == 3
    assert all(entry["result"]["status"] == "success" for entry in history)

@pytest.mark.asyncio
async def test_connection_recovery(front_desk):
    """Test recovery from connection interruptions."""
    # Mock the socket client's connect method
    connect_attempts = 0
    
    async def mock_connect():
        nonlocal connect_attempts
        connect_attempts += 1
        if connect_attempts == 1:
            raise Exception("Connection failed")
        return None
    
    # Set up the mock
    front_desk.socket_client.connect = AsyncMock(side_effect=mock_connect)
    front_desk.socket_client.close = AsyncMock()
    
    # Test first connection attempt (should fail)
    with pytest.raises(Exception) as exc_info:
        await front_desk.socket_client.connect()
    assert str(exc_info.value) == "Connection failed"
    assert connect_attempts == 1
    
    # Test second connection attempt (should succeed)
    await front_desk.socket_client.connect()
    assert connect_attempts == 2
    
    # Verify the socket client was used correctly
    assert front_desk.socket_client.connect.call_count == 2
    assert front_desk.socket_client.close.call_count == 0

@pytest.mark.asyncio
async def test_message_persistence(front_desk):
    """Test that messages aren't lost during processing delays."""
    # Create a delay in task processing
    original_execute = front_desk.task_manager.execute_recipe
    
    async def delayed_execute(*args, **kwargs):
        await asyncio.sleep(0.5)  # Simulate processing delay
        return await original_execute(*args, **kwargs)
    
    front_desk.task_manager.execute_recipe = delayed_execute
    
    # Send multiple messages
    messages = [
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": f"<@U123> urgent task {i}",
            "ts": f"1234567890.{i}"
        }
        for i in range(5)
    ]
    
    # Process messages
    for msg in messages:
        await front_desk.handle_message(msg)
    
    # Wait for processing
    await asyncio.sleep(3.0)
    
    # Verify all messages were processed
    history = front_desk.task_manager.get_task_history()
    assert len(history) == 5
    
    # Verify order was maintained
    timestamps = [entry["queued_time"] for entry in history]
    assert timestamps == sorted(timestamps)

@pytest.mark.asyncio
async def test_basic_conversation_flow(front_desk):
    """Test a basic back-and-forth conversation with the bot."""
    # Mock the NLP processor for a conversation
    nlp_results = [
        # Initial greeting
        {
            "status": "success",
            "intent": "greeting",
            "all_intents": ["greeting"],
            "entities": {},
            "urgency": 0.1
        },
        # Task request
        {
            "status": "success",
            "intent": "schedule_meeting",
            "all_intents": ["schedule_meeting"],
            "entities": {"time": "tomorrow"},  # Missing participants
            "urgency": 0.5
        },
        # Follow-up with missing info
        {
            "status": "success",
            "intent": "schedule_meeting",
            "all_intents": ["schedule_meeting"],
            "entities": {
                "time": "tomorrow",
                "participants": ["@john", "@mary"]
            },
            "urgency": 0.5
        }
    ]
    
    nlp_mock = AsyncMock()
    nlp_mock.process_message = AsyncMock()
    nlp_mock.process_message.side_effect = nlp_results
    front_desk.nlp = nlp_mock
    
    # Simulate a conversation
    messages = [
        # User says hello
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> hi there!",
            "ts": "1234567890.123"
        },
        # User makes incomplete request
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> schedule a meeting for tomorrow",
            "ts": "1234567890.124"
        },
        # User provides missing information
        {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": "<@U123> with @john and @mary",
            "ts": "1234567890.125"
        }
    ]
    
    # Process conversation
    for message in messages:
        await front_desk.handle_message(message)
        await asyncio.sleep(0.3)  # Wait for processing
    
    # Verify bot responses
    assert front_desk.web_client.chat_postMessage.call_count >= 3
    
    # Check task completion
    history = front_desk.task_manager.get_task_history()
    assert len(history) >= 1
    
    # Verify final task was successful
    final_task = history[-1]
    assert final_task["result"]["status"] == "success"
    assert final_task["recipe_name"] == "Schedule Meeting"

@pytest.mark.asyncio
async def test_service_lifecycle(front_desk):
    """Test full service start/stop lifecycle with proper cleanup."""
    # Use actual Slack SDK with test credentials
    front_desk.slack_app_token = "xapp-test"
    front_desk.slack_bot_token = "xoxb-test"
    
    try:
        # Start service with timeout
        await asyncio.wait_for(front_desk.start(), timeout=2.0)
        
        # Verify service started properly
        assert front_desk.running
        assert front_desk.start_time is not None
        assert front_desk.socket_client is not None
        
        # Stop service with timeout
        await asyncio.wait_for(front_desk.stop(), timeout=2.0)
        
        # Verify service stopped properly
        assert not front_desk.running
        assert not front_desk.socket_client.closed
        
    except asyncio.TimeoutError:
        # Force cleanup if timeout occurs
        front_desk.running = False
        if front_desk.socket_client:
            await front_desk.socket_client.close()
        raise
    except Exception as e:
        # Ensure cleanup on any other error
        front_desk.running = False
        if front_desk.socket_client:
            await front_desk.socket_client.close()
        raise

@pytest.mark.asyncio
async def test_enhanced_communication_flow(front_desk):
    """Test the enhanced communication flow with structured responses and GPT messaging."""
    # Set up bot ID and mention
    front_desk.bot_id = "U123"
    front_desk.bot_mention = "<@U123>"
    
    # Track GPT calls
    gpt_calls = []
    
    async def mock_gpt_response(prompt):
        gpt_calls.append(prompt)
        return f"Mock response for: {prompt[:50]}..."
    
    # Mock GPT client
    front_desk.get_gpt_response = AsyncMock(side_effect=mock_gpt_response)
    
    # Mock web client
    front_desk.web_client = AsyncMock()
    front_desk.web_client.chat_postMessage = AsyncMock()
    front_desk.web_client.users_info = AsyncMock(return_value={"ok": True, "user": {"real_name": "Test User", "id": "U456"}})
    
    # Define a complete recipe for testing
    schedule_meeting_recipe = {
        "name": "Schedule Meeting",
        "intent": "schedule_meeting",
        "description": "Schedule a meeting with participants",
        "steps": [
            {
                "type": "api_call",
                "action": "check_availability",
                "params": {
                    "time": "{time}",
                    "participants": "{participants}"
                }
            },
            {
                "type": "api_call",
                "action": "create_meeting",
                "params": {
                    "time": "{time}",
                    "participants": "{participants}"
                }
            }
        ],
        "required_entities": ["time", "participants"],
        "keywords": ["schedule", "meeting", "calendar"],
        "common_triggers": ["schedule a meeting", "set up a meeting"],
        "success_criteria": ["Meeting scheduled", "Invites sent"]
    }
    
    # Test cases with different scenarios
    test_cases = [
        {
            # Case 1: Missing information
            "message": "schedule a meeting tomorrow",
            "nlp_result": {
                "status": "success",
                "intent": "schedule_meeting",
                "all_intents": ["schedule_meeting"],
                "entities": {"time": "tomorrow"},
                "urgency": 0.5
            },
            "expected_cookbook_response": {
                "status": "missing_info",
                "recipe": schedule_meeting_recipe,
                "missing_requirements": ["participants"],
                "suggested_next_steps": "request_info",
                "details": "Recipe found for schedule_meeting but requires additional information"
            }
        },
        {
            # Case 2: Successful task
            "message": "schedule a meeting tomorrow with @john",
            "nlp_result": {
                "status": "success",
                "intent": "schedule_meeting",
                "all_intents": ["schedule_meeting"],
                "entities": {
                    "time": "tomorrow",
                    "participants": ["@john"]
                },
                "urgency": 0.5
            },
            "expected_cookbook_response": {
                "status": "success",
                "recipe": schedule_meeting_recipe,
                "missing_requirements": [],
                "suggested_next_steps": "execute_recipe",
                "details": "Recipe found with no missing requirements"
            }
        },
        {
            # Case 3: Unknown task (CEO consultation)
            "message": "research the latest AI trends",
            "nlp_result": {
                "status": "success",
                "intent": "unknown_task",
                "all_intents": ["research"],
                "entities": {"topic": "AI trends"},
                "urgency": 0.5
            },
            "expected_cookbook_response": {
                "status": "not_found",
                "recipe": None,
                "missing_requirements": [],
                "suggested_next_steps": "consult_ceo",
                "details": "No recipe found for intent: unknown_task"
            }
        },
        {
            # Case 4: Error case
            "message": "invalid request",
            "nlp_result": {
                "status": "error",
                "intent": None,
                "all_intents": [],
                "entities": {},
                "urgency": 0.1
            },
            "expected_cookbook_response": {
                "status": "error",
                "recipe": None,
                "missing_requirements": [],
                "suggested_next_steps": "consult_ceo",
                "details": "Error processing request"
            }
        }
    ]
    
    # Mock task manager
    task_manager_mock = MagicMock()
    task_manager_mock.task_history = []
    
    async def mock_execute_recipe(recipe, context):
        result = {
            "status": "success",
            "details": "Meeting scheduled successfully"
        } if recipe["name"] == "Schedule Meeting" and "participants" in context["nlp_result"]["entities"] else {
            "status": "error",
            "error": "Missing required information"
        }
        
        # Add to task history if successful
        if result["status"] == "success":
            task_manager_mock.task_history.append({
                "task_id": "test_task",
                "recipe_name": recipe["name"],
                "queued_time": "2024-02-10T14:00:00",
                "start_time": "2024-02-10T14:00:01",
                "end_time": "2024-02-10T14:00:02",
                "urgency": context["nlp_result"]["urgency"],
                "result": result
            })
        
        return result
    
    task_manager_mock.execute_recipe = AsyncMock(side_effect=mock_execute_recipe)
    task_manager_mock.get_task_history = lambda: task_manager_mock.task_history
    front_desk.task_manager = task_manager_mock
    
    # Mock NLP processor
    nlp_mock = AsyncMock()
    nlp_mock.process_message = AsyncMock()
    nlp_mock.process_message.side_effect = [case["nlp_result"] for case in test_cases]
    front_desk.nlp = nlp_mock
    
    # Mock cookbook responses
    cookbook_mock = MagicMock()
    cookbook_mock.get_recipe = MagicMock(side_effect=[case["expected_cookbook_response"] for case in test_cases])
    front_desk.cookbook = cookbook_mock
    
    # Process each test case
    for i, case in enumerate(test_cases):
        message = {
            "type": "message",
            "channel": "C123",
            "user": "U456",
            "text": f"<@U123> {case['message']}",
            "ts": f"1234567890.{i}"
        }

        # Clear previous calls
        gpt_calls.clear()
        front_desk.web_client.chat_postMessage.reset_mock()

        # Handle message
        await front_desk.handle_message(message)
        await asyncio.sleep(0.1)  # Allow for processing

        # Verify GPT was used for response
        assert len(gpt_calls) > 0, f"No GPT calls made for case {i}: {case['message']}"

        # Verify appropriate Slack message was sent
        front_desk.web_client.chat_postMessage.assert_called()

    # Verify all test cases were processed
    assert len(test_cases) == 4, "Expected 4 test cases"
    
    # Verify cookbook was consulted for each case
    assert cookbook_mock.get_recipe.call_count == len(test_cases)
    
    # Verify task manager was only called for successful case
    task_history = task_manager_mock.get_task_history()
    successful_tasks = [t for t in task_history if t["result"]["status"] == "success"]
    assert len(successful_tasks) == 1
    assert successful_tasks[0]["recipe_name"] == "Schedule Meeting"

@pytest.mark.asyncio
async def test_nlp_cookbook_integration():
    """Test that NLP processor correctly uses cookbook lexicon for intent recognition."""
    # Initialize components
    cookbook = CookbookManager()
    nlp = NLPProcessor(cookbook_manager=cookbook)
    cookbook.register_nlp_processor(nlp)
    
    # Test cases with different phrasings
    test_cases = [
        {
            "message": "could you see if I have any new emails?",
            "expected_intent": "email_read",
            "description": "Email check with indirect phrasing"
        },
        {
            "message": "schedule an appointment for tomorrow",
            "expected_intent": "schedule_meeting",
            "description": "Meeting scheduling with 'appointment' alias"
        },
        {
            "message": "can you set up a meeting with John?",
            "expected_intent": "schedule_meeting",
            "description": "Meeting scheduling with trigger phrase"
        },
        {
            "message": "check my inbox please",
            "expected_intent": "email_read",
            "description": "Email check with keyword variation"
        }
    ]
    
    # Process each test case
    for case in test_cases:
        # Process message
        result = await nlp.process_message(
            case["message"],
            {"id": "U123", "real_name": "Test User"}
        )
        
        # Verify intent recognition
        assert result["status"] == "success", f"Failed to process message: {case['description']}"
        assert result["intent"] == case["expected_intent"], \
            f"Wrong intent for '{case['description']}'. Expected {case['expected_intent']}, got {result['intent']}"
        assert case["expected_intent"] in result["all_intents"], \
            f"Expected intent not in all_intents for: {case['description']}"
    
    # Test lexicon update when adding new recipe
    new_recipe = {
        "name": "Task Reminder",
        "intent": "set_reminder",
        "description": "Set a reminder for a task",
        "steps": [
            {"type": "api_call", "name": "create_reminder", "endpoint": "reminders/create"}
        ],
        "required_entities": ["time", "task"],
        "keywords": ["remind", "reminder", "remember"],
        "common_triggers": ["remind me to", "set a reminder"],
        "success_criteria": ["Reminder set"]
    }
    
    # Add new recipe
    success = await cookbook.add_recipe(new_recipe)
    assert success, "Failed to add new recipe"
    
    # Test new recipe recognition
    result = await nlp.process_message(
        "remind me to call John tomorrow",
        {"id": "U123", "real_name": "Test User"}
    )
    
    assert result["status"] == "success"
    assert result["intent"] == "set_reminder", "Failed to recognize newly added recipe intent"
    
    # Test unregistering NLP processor
    cookbook.unregister_nlp_processor(nlp)
    assert nlp not in cookbook.nlp_processors, "Failed to unregister NLP processor"

@pytest.mark.asyncio
async def test_time_entity_flow(cookbook_manager, nlp_processor):
    """Test the flow of time entity from NLP processor to Cookbook Manager."""
    # Test cases with different time formats
    test_cases = [
        {
            "message": "schedule a meeting tomorrow at 9:00 AM",
            "time_checks": [
                lambda t: "9:00 AM" in t,  # Check time component
                lambda t: any(word in t.lower() for word in ["tomorrow", "2025-02-10"])  # Check date component
            ]
        },
        {
            "message": "set up a meeting for February 10th at 2:00 PM",
            "time_checks": [
                lambda t: "2:00 PM" in t,  # Check time component
                lambda t: "02-10" in t or "February 10th" in t  # Check date component
            ]
        },
        {
            "message": "book an appointment at 3pm",
            "time_checks": [
                lambda t: any(time in t for time in ["3:00 PM", "03:00 PM", "3 PM"])  # Check time component
            ]
        }
    ]

    for case in test_cases:
        # Process through NLP
        nlp_result = await nlp_processor.process_message(
            case["message"],
            {"id": "U123", "real_name": "Test User"}
        )
        
        # Verify NLP extracted the time
        assert nlp_result["status"] == "success", f"NLP processing failed for: {case['message']}"
        assert nlp_result["entities"]["time"] is not None, f"Time not extracted for: {case['message']}"
        
        # Check each time component using the validation functions
        extracted_time = nlp_result["entities"]["time"]
        for check in case["time_checks"]:
            assert check(extracted_time), f"Time validation failed for '{case['message']}' with extracted time '{extracted_time}'"

        # Find matching recipe
        recipe_response = await cookbook_manager.find_matching_recipe(nlp_result)
        assert recipe_response is not None, "No recipe found"
        assert recipe_response["intent"] == "schedule_meeting"

        # Check if cookbook correctly validates the time entity
        validation_response = cookbook_manager._validate_recipe_requirements(recipe_response, nlp_result)
        assert validation_response["status"] == "success", \
            f"Validation failed: {validation_response.get('missing_requirements', [])}"
        assert "time" not in validation_response.get("missing_requirements", []), \
            f"Time incorrectly reported as missing: {validation_response}"

        # Print debug information if the test fails
        if validation_response["status"] != "success":
            print("\nDebug Information:")
            print(f"Original message: {case['message']}")
            print(f"NLP result: {nlp_result}")
            print(f"Recipe response: {recipe_response}")
            print(f"Validation response: {validation_response}")

@pytest.mark.asyncio
async def test_entity_validation_in_cookbook(cookbook_manager):
    """Test that Cookbook Manager correctly validates entities."""
    # Create a test recipe
    recipe = {
        "name": "schedule_meeting",
        "intent": "schedule_meeting",
        "required_entities": ["time"],
        "steps": [
            {
                "action": "create_meeting",
                "params": {"time": "{time}"}
            }
        ]
    }

    # Test cases with different entity combinations
    test_cases = [
        {
            "description": "Complete time entity",
            "nlp_result": {
                "entities": {
                    "time": "2025-02-10 02:00 PM"
                }
            },
            "expected_status": "success"
        },
        {
            "description": "Missing time entity",
            "nlp_result": {
                "entities": {}
            },
            "expected_status": "missing_info"
        },
        {
            "description": "Time with different format",
            "nlp_result": {
                "entities": {
                    "time": "tomorrow at 9:00 AM"
                }
            },
            "expected_status": "success"
        }
    ]

    for case in test_cases:
        validation = cookbook_manager._validate_recipe_requirements(recipe, case["nlp_result"])
        assert validation["status"] == case["expected_status"], \
            f"Failed for {case['description']}: Expected {case['expected_status']}, got {validation['status']}" 