import pytest
import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import os

from src.office.core.request_tracking import EnhancedRequestTracker, Request, RequestMetadata

@pytest.fixture
async def tracker():
    """Create a temporary tracker for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    tracker = EnhancedRequestTracker(storage_path=db_path)
    yield tracker
    
    # Cleanup
    os.unlink(db_path)

@pytest.mark.asyncio
async def test_request_lifecycle(tracker):
    """Test basic request lifecycle."""
    # Create request
    request = await tracker.create_request(
        channel_id="test-channel",
        user_id="test-user",
        initial_message="Test request",
        priority=0.8
    )
    
    # Verify request was created
    assert request.request_id is not None
    assert request.status == "new"
    assert request.metadata.priority == 0.8
    
    # Start processing
    await tracker.start_request_processing(request, "test-processor")
    updated = await tracker.get_request(request.request_id)
    assert updated.status == "processing"
    assert len(updated.processing_history) == 1
    
    # Complete request
    completion_data = {"result": "success"}
    await tracker.mark_request_complete(request, completion_data)
    completed = await tracker.get_request(request.request_id)
    assert completed.status == "completed"
    assert completed.completion_data == completion_data
    
@pytest.mark.asyncio
async def test_request_queueing(tracker):
    """Test request priority queueing."""
    # Create requests with different priorities
    high_req = await tracker.create_request(
        channel_id="test-channel",
        user_id="test-user",
        initial_message="High priority",
        priority=0.9
    )
    
    low_req = await tracker.create_request(
        channel_id="test-channel",
        user_id="test-user",
        initial_message="Low priority",
        priority=0.1
    )
    
    # High priority should come first
    next_req = await tracker.get_next_request()
    assert next_req.request_id == high_req.request_id
    
    # Then low priority
    next_req = await tracker.get_next_request()
    assert next_req.request_id == low_req.request_id
    
@pytest.mark.asyncio
async def test_request_cleanup(tracker):
    """Test cleanup of stale requests."""
    # Create a request
    request = await tracker.create_request(
        channel_id="test-channel",
        user_id="test-user",
        initial_message="Test request"
    )
    
    # Artificially age the request
    with sqlite3.connect(tracker.persistence.db_path) as conn:
        old_time = (datetime.now() - timedelta(hours=1)).isoformat()
        conn.execute(
            "UPDATE requests SET last_updated = ? WHERE request_id = ?",
            (old_time, request.request_id)
        )
    
    # Run cleanup
    await tracker.cleanup_stale_requests()
    
    # Verify request was marked as error
    updated = await tracker.get_request(request.request_id)
    assert updated.status == "error"
    assert any(step["component"] == "cleanup" for step in updated.processing_history)
    
@pytest.mark.asyncio
async def test_request_search(tracker):
    """Test request search functionality."""
    # Create some requests
    await tracker.create_request(
        channel_id="channel-1",
        user_id="user-1",
        initial_message="Test 1"
    )
    
    await tracker.create_request(
        channel_id="channel-2",
        user_id="user-1",
        initial_message="Test 2"
    )
    
    # Search by user
    results = await tracker.get_user_requests("user-1")
    assert len(results) == 2
    
    # Search by channel
    results = await tracker.search_requests({"channel_id": "channel-1"})
    assert len(results) == 1
    assert results[0].metadata.channel_id == "channel-1" 