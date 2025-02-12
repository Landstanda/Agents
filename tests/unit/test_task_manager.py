import pytest
import asyncio
from src.office.task.task_manager import TaskManager
from typing import Dict, Any

@pytest.fixture
def task_manager():
    """Initialize task manager for testing."""
    return TaskManager()

@pytest.fixture
def sample_recipe():
    """Create a sample recipe for testing."""
    return {
        "name": "Test Recipe",
        "intent": "test",
        "steps": [
            {
                "type": "api_call",
                "name": "test_api",
                "endpoint": "test/api"
            },
            {
                "type": "database_query",
                "name": "test_query",
                "query_type": "test"
            }
        ]
    }

@pytest.fixture
def sample_context():
    """Create a sample context for testing."""
    return {
        "nlp_result": {
            "intent": "test",
            "entities": {"test_entity": "value"}
        },
        "user_info": {
            "id": "U123",
            "real_name": "Test User"
        },
        "channel_id": "C123",
        "thread_ts": "1234567890.123"
    }

@pytest.mark.asyncio
async def test_basic_recipe_execution(task_manager, sample_recipe, sample_context):
    """Test basic execution of a recipe."""
    # Queue the recipe
    result = await task_manager.execute_recipe(sample_recipe, sample_context)
    assert result["status"] == "queued"
    assert "task_id" in result
    
    # Wait for processing
    await asyncio.sleep(0.1)
    
    # Check history for completion
    history = task_manager.get_task_history()
    assert len(history) == 1
    assert history[0]["result"]["status"] == "success"

@pytest.mark.asyncio
async def test_sequential_execution(task_manager, sample_recipe, sample_context):
    """Test sequential processing of tasks with different urgency levels."""
    # Create tasks with different urgency levels
    tasks = []
    for i in range(5):
        context = sample_context.copy()
        context["nlp_result"] = {"urgency": i}  # 0 is lowest, 4 is highest
        result = await task_manager.execute_recipe(sample_recipe, context)
        assert result["status"] == "queued"
        tasks.append(result["task_id"])
    
    # Wait a bit for tasks to process
    await asyncio.sleep(0.5)
    
    # Check task history
    history = task_manager.get_task_history()
    assert len(history) == 5
    
    # Verify tasks were executed in order of urgency (highest to lowest)
    urgencies = [entry["urgency"] for entry in history]
    assert urgencies == sorted(urgencies, reverse=True)
    
    # Verify all tasks completed successfully
    for entry in history:
        assert entry["result"]["status"] == "success"
    
    # Verify no active tasks remain
    assert task_manager.get_active_task() is None

@pytest.mark.asyncio
async def test_step_execution(task_manager, sample_context):
    """Test execution of different types of steps."""
    # Test API call step
    api_step = {
        "type": "api_call",
        "name": "test_api",
        "endpoint": "test/api"
    }
    result = await task_manager._execute_step(api_step, sample_context)
    assert result["status"] == "success"
    
    # Test database query step
    db_step = {
        "type": "database_query",
        "name": "test_query",
        "query_type": "test"
    }
    result = await task_manager._execute_step(db_step, sample_context)
    assert result["status"] == "success"
    
    # Test notification step
    notification_step = {
        "type": "notification",
        "name": "test_notification",
        "message": "Test message"
    }
    result = await task_manager._execute_step(notification_step, sample_context)
    assert result["status"] == "success"

@pytest.mark.asyncio
async def test_error_handling(task_manager, sample_context):
    """Test error handling during recipe execution."""
    # Test with invalid step type
    invalid_step = {
        "type": "invalid_type",
        "name": "test"
    }
    result = await task_manager._execute_step(invalid_step, sample_context)
    assert result["status"] == "error"
    assert "error" in result
    
    # Test with invalid recipe
    invalid_recipe = {
        "name": "Invalid Recipe",
        "steps": [invalid_step]
    }
    # Queue the invalid recipe
    result = await task_manager.execute_recipe(invalid_recipe, sample_context)
    assert result["status"] == "queued"
    
    # Wait for processing
    await asyncio.sleep(0.1)
    
    # Check history for error
    history = task_manager.get_task_history()
    assert len(history) > 0
    assert history[-1]["result"]["status"] == "error"

@pytest.mark.asyncio
async def test_task_tracking(task_manager, sample_recipe, sample_context):
    """Test tracking of active tasks and task history."""
    # Queue a recipe
    result = await task_manager.execute_recipe(sample_recipe, sample_context)
    assert result["status"] == "queued"
    
    # Wait for processing
    await asyncio.sleep(0.1)
    
    # Check task history
    history = task_manager.get_task_history()
    assert len(history) == 1
    assert history[0]["recipe_name"] == sample_recipe["name"]
    
    # Check active task (should be None after completion)
    active = task_manager.get_active_task()
    assert active is None

@pytest.mark.asyncio
async def test_execution_details_formatting(task_manager):
    """Test formatting of execution details."""
    results = [
        {"status": "success", "details": "Step 1 completed"},
        {"status": "success", "details": "Step 2 completed"},
        {"status": "error", "error": "Step 3 failed"}
    ]
    
    formatted = task_manager._format_execution_details(results)
    assert "Step 1" in formatted
    assert "Step 2" in formatted
    assert "Step 3" not in formatted  # Error step should be excluded 