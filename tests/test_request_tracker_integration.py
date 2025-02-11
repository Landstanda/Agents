import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from src.office.reception.request_tracker import RequestTracker, Request
from src.office.reception.front_desk import FrontDesk
from src.office.task.task_manager import TaskManager
from src.office.cookbook.cookbook_manager import CookbookManager
from src.office.executive.ceo import CEO
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def request_tracker():
    return RequestTracker()

@pytest.fixture
def mock_front_desk():
    front_desk = MagicMock()
    front_desk.get_gpt_response = AsyncMock()
    front_desk.web_client = MagicMock()
    front_desk.web_client.chat_postMessage = AsyncMock()
    return front_desk

@pytest.fixture
def mock_task_manager():
    task_manager = MagicMock()
    task_manager.execute_recipe = AsyncMock()
    return task_manager

@pytest.mark.asyncio
async def test_request_lifecycle(request_tracker, mock_front_desk, mock_task_manager):
    """Test a request through its complete lifecycle."""
    # Create initial request
    request = request_tracker.create_request("C123", "U456", "Schedule a meeting tomorrow at 2pm")
    assert request.status == "new"
    
    # Simulate NLP processing
    request.update(
        intent="schedule_meeting",
        entities={"time": "tomorrow at 2:00 PM"}
    )
    assert request.intent == "schedule_meeting"
    
    # Simulate cookbook matching
    request.update(
        recipe={
            "name": "schedule_meeting",
            "steps": [{"action": "create_meeting"}]
        }
    )
    assert request.recipe is not None
    
    # Simulate task execution
    request.mark_delegated("task_manager")
    request.task_id = "task_123"
    assert request.delegated_to == "task_manager"
    
    # Complete the request
    request.complete_with_data({
        "status": "success",
        "details": "Meeting scheduled for tomorrow at 2:00 PM"
    })
    assert request.status == "completed"
    assert "Meeting scheduled" in request.completion_data["details"]

@pytest.mark.asyncio
async def test_request_error_handling(request_tracker):
    """Test request error handling and recovery."""
    request = request_tracker.create_request("C123", "U456", "Invalid request")
    
    # Simulate error in NLP
    request.update(status="error")
    request.add_message("Failed to process intent", is_user=False, source="nlp")
    
    assert request.status == "error"
    assert any(msg["source"] == "nlp" for msg in request.conversation_history)
    
    # Test recovery
    request.update(status="new")
    assert request.status == "new"

@pytest.mark.asyncio
async def test_request_delegation_chain(request_tracker, mock_front_desk, mock_task_manager):
    """Test request being passed through the office chain."""
    request = request_tracker.create_request("C123", "U456", "Research AI trends")
    
    # Front Desk processing
    request.mark_delegated("front_desk")
    request.update(
        intent="research",
        entities={"topic": "AI trends"}
    )
    
    # CEO consultation
    request.mark_delegated("ceo")
    request.ceo_consulted = True
    request.update(priority=0.8)
    
    # Task Manager execution
    request.mark_delegated("task_manager")
    request.task_id = "task_456"
    
    # Verify chain
    delegation_chain = [msg["message"] for msg in request.conversation_history 
                       if msg["source"] == "system" and "delegated to" in msg["message"]]
    assert len(delegation_chain) == 3
    assert "front_desk" in delegation_chain[0]
    assert "ceo" in delegation_chain[1]
    assert "task_manager" in delegation_chain[2]

@pytest.mark.asyncio
async def test_request_context_maintenance(request_tracker):
    """Test that request maintains context through updates."""
    request = request_tracker.create_request("C123", "U456", "Schedule team meeting")
    
    # Initial NLP
    request.update(
        intent="schedule_meeting",
        entities={}
    )
    
    # Add time in follow-up
    request.add_message("at 2pm tomorrow", is_user=True)
    request.update(
        entities={"time": "tomorrow at 2:00 PM"}
    )
    
    # Add participants in another follow-up
    request.add_message("with @john and @mary", is_user=True)
    request.update(
        entities={
            "time": "tomorrow at 2:00 PM",
            "participants": ["@john", "@mary"]
        }
    )
    
    # Verify context is maintained
    assert request.entities["time"] == "tomorrow at 2:00 PM"
    assert len(request.entities["participants"]) == 2
    assert len(request.conversation_history) == 3

@pytest.mark.asyncio
async def test_request_timeout_handling(request_tracker):
    """Test that requests are properly timed out."""
    request = request_tracker.create_request("C123", "U456", "Schedule meeting")
    
    # Simulate time passing
    request.last_updated = datetime.now() - timedelta(minutes=31)
    
    # Clean up old requests
    request_tracker._cleanup_old_requests()
    
    # Verify request was moved to completed with timeout status
    assert request.status == "timeout"
    assert request not in request_tracker.active_requests.get("C123", {}).values()
    assert request in request_tracker.completed_requests

@pytest.mark.asyncio
async def test_concurrent_requests(request_tracker):
    """Test handling multiple concurrent requests."""
    # Create multiple requests
    request1 = request_tracker.create_request("C123", "U456", "Schedule meeting")
    request2 = request_tracker.create_request("C123", "U789", "Research AI")
    request3 = request_tracker.create_request("C456", "U456", "Another meeting")
    
    # Update them concurrently
    await asyncio.gather(
        asyncio.create_task(_async_update(request1, "schedule_meeting")),
        asyncio.create_task(_async_update(request2, "research")),
        asyncio.create_task(_async_update(request3, "schedule_meeting"))
    )
    
    # Verify all requests maintained their integrity
    assert request1.intent == "schedule_meeting"
    assert request2.intent == "research"
    assert request3.intent == "schedule_meeting"
    
    # Verify they're properly tracked
    assert request1 == request_tracker.get_active_request("C123", "U456")
    assert request2 == request_tracker.get_active_request("C123", "U789")
    assert request3 == request_tracker.get_active_request("C456", "U456")

async def _async_update(request: Request, intent: str):
    """Helper for async request updates."""
    await asyncio.sleep(0.1)  # Simulate processing time
    request.update(intent=intent) 

@pytest.mark.asyncio
async def test_conversational_messages_not_tracked():
    """Test that conversational messages don't create requests."""
    front_desk = FrontDesk()
    front_desk.bot_mention = None  # Set bot_mention to None for testing
    
    # Mock NLP processor
    front_desk.nlp.process_message = AsyncMock(return_value={
        "status": "success",
        "intent": "greeting",
        "needs_tracking": False
    })
    
    # Mock web client
    front_desk.web_client = MagicMock()
    front_desk.web_client.chat_postMessage = AsyncMock()
    front_desk.get_gpt_response = AsyncMock(return_value="Hello!")
    
    # Send a greeting
    message = {
        "channel": "C123",
        "user": "U456",
        "text": "Hi there!"
    }
    
    await front_desk.handle_message(message)
    
    # Verify no request was created
    assert not front_desk.request_tracker.get_active_request("C123", "U456")
    
    # Verify response was sent
    assert front_desk.web_client.chat_postMessage.called

@pytest.mark.asyncio
async def test_request_state_transitions():
    """Test that requests transition through states correctly."""
    request_tracker = RequestTracker()
    
    # Create request
    request = request_tracker.create_request("C123", "U456", "Schedule a meeting")
    assert request.status == "new"
    
    # Update to processing
    request.update(status="processing")
    assert request.status == "processing"
    
    # Update to waiting for info
    request.update(status="waiting_for_info")
    assert request.status == "waiting_for_info"
    
    # Update to completed
    request.complete_with_data({"status": "success"})
    assert request.status == "completed"
    
    # Verify completed request is archived
    assert request not in request_tracker.active_requests.get("C123", {}).values()
    assert request in request_tracker.completed_requests

@pytest.mark.asyncio
async def test_request_history_cleanup():
    """Test that completed requests are properly archived and cleaned up."""
    request_tracker = RequestTracker()
    
    # Create and complete many requests
    for i in range(1100):  # More than the 1000 limit
        request = request_tracker.create_request(f"C{i}", "U456", f"Request {i}")
        request.complete_with_data({"status": "success"})
    
    # Verify history is limited
    assert len(request_tracker.completed_requests) <= 1000
    
    # Verify oldest requests were removed
    request_ids = [r.request_id for r in request_tracker.completed_requests]
    assert len(request_ids) == len(set(request_ids))  # No duplicates

@pytest.mark.asyncio
async def test_request_priority_handling():
    """Test that request priority is properly set and maintained."""
    request_tracker = RequestTracker()
    
    # Create requests with different priorities
    urgent_request = request_tracker.create_request("C123", "U456", "URGENT: Schedule meeting now!")
    normal_request = request_tracker.create_request("C123", "U789", "Schedule meeting next week")
    
    # Update priorities
    urgent_request.update(priority=0.9)
    normal_request.update(priority=0.5)
    
    # Verify priorities
    assert urgent_request.priority > normal_request.priority
    assert urgent_request.priority == 0.9
    assert normal_request.priority == 0.5

@pytest.mark.asyncio
async def test_request_entity_updates():
    """Test that entities are properly updated and merged."""
    request_tracker = RequestTracker()
    
    # Create request
    request = request_tracker.create_request("C123", "U456", "Schedule a meeting")
    
    # Initial entities
    request.update(entities={
        "time": "2pm",
        "participants": ["@john"]
    })
    
    # Add more entities
    request.update(entities={
        "participants": ["@john", "@mary"],
        "location": "conference room"
    })
    
    # Verify entities were merged correctly
    assert request.entities["time"] == "2pm"
    assert len(request.entities["participants"]) == 2
    assert request.entities["location"] == "conference room" 