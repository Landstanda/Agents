# Request Tracking System

A robust system for tracking and managing requests throughout their lifecycle. The system provides persistent storage, priority-based queueing, and comprehensive request history tracking.

## Features

- Persistent storage using SQLite
- Priority-based request queueing (high, normal, low)
- Complete request lifecycle management
- Request metadata and history tracking
- Automatic cleanup of stale requests
- Search capabilities by user, channel, status, and date

## Components

### RequestMetadata

Stores routing and priority information for requests:
- Channel ID
- User ID
- Priority (0.0 - 1.0)
- Optional deadline
- Source system
- Tags

### Request

Main request object with tracking capabilities:
- Unique request ID
- Initial message
- Metadata
- Status tracking
- Intent and entities
- Conversation chain
- Processing history
- Completion data

### RequestPersistence

Handles persistent storage using SQLite:
- Automatic database initialization
- CRUD operations for requests
- Indexed fields for efficient querying

### RequestQueueManager

Manages prioritized request queues:
- Three priority levels (high, normal, low)
- Priority-based request retrieval
- Active request tracking

### EnhancedRequestTracker

Main coordinator for request tracking:
- Request creation and updates
- Status management
- Request search and retrieval
- Stale request cleanup
- Request completion handling

## Usage Example

```python
# Create a tracker
tracker = EnhancedRequestTracker(storage_path="data/requests.db")

# Create a new request
request = await tracker.create_request(
    channel_id="channel-1",
    user_id="user-1",
    initial_message="Process this request",
    priority=0.8
)

# Start processing
await tracker.start_request_processing(request, "processor-1")

# Mark as complete
await tracker.mark_request_complete(request, {"result": "success"})

# Search for user's requests
user_requests = await tracker.get_user_requests("user-1")
```

## Testing

The system includes comprehensive tests covering:
- Request lifecycle
- Priority queueing
- Request cleanup
- Search functionality

Run tests using pytest:
```bash
pytest tests/test_request_tracking.py -v
``` 