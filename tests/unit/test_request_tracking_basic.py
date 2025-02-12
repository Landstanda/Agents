import pytest
import asyncio
from datetime import datetime, timedelta
import tempfile
import os
from src.office.core.request_tracking import EnhancedRequestTracker

@pytest.fixture
def db_path():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    yield path
    try:
        os.unlink(path)
    except:
        pass

@pytest.fixture
def request_tracker(db_path):
    """Create a tracker instance for testing."""
    return EnhancedRequestTracker(storage_path=db_path)

@pytest.mark.asyncio
async def test_basic_request_creation(request_tracker):
    """Test basic request creation and retrieval."""
    # Create a request
    request = await request_tracker.create_request(
        channel_id="test-channel",
        user_id="test-user",
        initial_message="Test request",
        priority=0.5
    )
    
    # Verify request was created with correct attributes
    assert request.request_id is not None
    assert request.initial_message == "Test request"
    assert request.metadata.channel_id == "test-channel"
    assert request.metadata.user_id == "test-user"
    assert request.metadata.priority == 0.5
    assert request.status == "new"
    
    # Retrieve the request and verify it matches
    retrieved = await request_tracker.get_request(request.request_id)
    assert retrieved is not None
    assert retrieved.request_id == request.request_id
    assert retrieved.initial_message == request.initial_message

@pytest.mark.asyncio
async def test_request_lifecycle(request_tracker):
    """Test request going through its lifecycle."""
    # Create request
    request = await request_tracker.create_request(
        channel_id="test-channel",
        user_id="test-user",
        initial_message="Lifecycle test",
        priority=0.8
    )
    
    # Start processing
    await request_tracker.start_request_processing(request, "test-processor")
    assert request.status == "processing"
    
    # Complete request
    completion_data = {"result": "success", "details": "Task completed"}
    await request_tracker.mark_request_complete(request, completion_data)
    assert request.status == "completed"
    assert request.completion_data == completion_data
    
    # Verify final state
    final = await request_tracker.get_request(request.request_id)
    assert final.status == "completed"
    assert final.completion_data == completion_data

@pytest.mark.asyncio
async def test_request_error_handling(request_tracker):
    """Test request error handling."""
    # Create request
    request = await request_tracker.create_request(
        channel_id="test-channel",
        user_id="test-user",
        initial_message="Error test",
        priority=0.5
    )
    
    # Mark as error
    error_msg = "Test error message"
    error_details = {"error_code": 500, "source": "test"}
    await request_tracker.mark_request_error(request, error_msg, error_details)
    
    # Verify error state
    assert request.status == "error"
    error_step = next((step for step in request.processing_history if step["component"] == "error"), None)
    assert error_step is not None
    assert error_step["result"]["error"] == error_msg
    assert error_step["result"]["error_code"] == 500

@pytest.mark.asyncio
async def test_request_search(request_tracker):
    """Test request search functionality."""
    # Create multiple requests
    requests = []
    for i in range(3):
        request = await request_tracker.create_request(
            channel_id=f"channel-{i}",
            user_id="test-user",
            initial_message=f"Test request {i}",
            priority=0.5
        )
        requests.append(request)
    
    # Search by user
    user_requests = await request_tracker.get_user_requests("test-user", limit=10)
    assert len(user_requests) == 3
    
    # Search by channel
    channel_requests = await request_tracker.search_requests({"channel_id": "channel-0"})
    assert len(channel_requests) == 1
    assert channel_requests[0].metadata.channel_id == "channel-0"

@pytest.mark.asyncio
async def test_priority_queue_ordering(request_tracker):
    """Test that requests are processed in priority order."""
    # Create requests with different priorities
    low_priority = await request_tracker.create_request(
        channel_id="test-channel",
        user_id="test-user",
        initial_message="Low priority",
        priority=0.1
    )
    
    high_priority = await request_tracker.create_request(
        channel_id="test-channel",
        user_id="test-user",
        initial_message="High priority",
        priority=0.9
    )
    
    medium_priority = await request_tracker.create_request(
        channel_id="test-channel",
        user_id="test-user",
        initial_message="Medium priority",
        priority=0.5
    )
    
    # Get requests in order
    next_request = await request_tracker.get_next_request()
    assert next_request.request_id == high_priority.request_id
    
    next_request = await request_tracker.get_next_request()
    assert next_request.request_id == medium_priority.request_id
    
    next_request = await request_tracker.get_next_request()
    assert next_request.request_id == low_priority.request_id

@pytest.mark.asyncio
async def test_fifo_equal_priority(request_tracker):
    """Test FIFO behavior for requests with equal priority."""
    requests = []
    # Create multiple requests with same priority
    for i in range(3):
        request = await request_tracker.create_request(
            channel_id="test-channel",
            user_id="test-user",
            initial_message=f"Request {i}",
            priority=0.5
        )
        requests.append(request)
        await asyncio.sleep(0.1)  # Ensure different timestamps
    
    # Verify they come out in order
    for expected_request in requests:
        next_request = await request_tracker.get_next_request()
        assert next_request.request_id == expected_request.request_id

@pytest.mark.asyncio
async def test_request_timeout_handling(request_tracker):
    """Test handling of stale requests."""
    # Create a request
    request = await request_tracker.create_request(
        channel_id="test-channel",
        user_id="test-user",
        initial_message="Timeout test",
        priority=0.5
    )
    
    # Artificially age the request
    request.last_updated = datetime.now() - timedelta(minutes=31)
    await request_tracker.update_request(request)
    
    # Run cleanup
    await request_tracker.cleanup_stale_requests()
    
    # Verify request was marked as error
    updated_request = await request_tracker.get_request(request.request_id)
    assert updated_request.status == "error"
    assert any(step["component"] == "cleanup" for step in updated_request.processing_history)

@pytest.mark.asyncio
async def test_concurrent_request_handling(request_tracker):
    """Test handling multiple requests concurrently."""
    async def create_and_process_request(i: int):
        request = await request_tracker.create_request(
            channel_id=f"channel-{i}",
            user_id=f"user-{i}",
            initial_message=f"Concurrent request {i}",
            priority=0.5
        )
        await request_tracker.start_request_processing(request, f"processor-{i}")
        await request_tracker.mark_request_complete(request, {"result": f"completed-{i}"})
        return request.request_id
    
    # Create and process multiple requests concurrently
    request_ids = await asyncio.gather(*[
        create_and_process_request(i) for i in range(5)
    ])
    
    # Verify all requests completed successfully
    for request_id in request_ids:
        request = await request_tracker.get_request(request_id)
        assert request.status == "completed"
        assert request.completion_data["result"].startswith("completed-")

@pytest.mark.asyncio
async def test_queue_overflow_handling(request_tracker):
    """Test handling of queue overflow."""
    # Create many requests
    requests = []
    for i in range(100):  # Create more requests than typical
        request = await request_tracker.create_request(
            channel_id="test-channel",
            user_id="test-user",
            initial_message=f"Request {i}",
            priority=0.5
        )
        requests.append(request)
    
    # Verify we can still get all requests
    for _ in range(len(requests)):
        request = await request_tracker.get_next_request()
        assert request is not None
        
    # Verify queue is empty
    assert await request_tracker.get_next_request() is None 