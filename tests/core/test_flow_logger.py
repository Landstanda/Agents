import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from src.utils.flow_logger import FlowLogger
import os
import json

@pytest.fixture
def flow_logger():
    """Create a FlowLogger instance for testing"""
    return FlowLogger()

@pytest.mark.asyncio
class TestFlowLogger:
    """Tests for the FlowLogger class"""
    
    async def test_initialization(self, flow_logger):
        """Test basic logger initialization"""
        assert flow_logger.events == []
        assert flow_logger.errors == []
        assert flow_logger.history == []
        assert not flow_logger._initialized
    
    async def test_setup(self, flow_logger):
        """Test logger setup"""
        await flow_logger.setup()
        assert flow_logger._initialized
        assert os.path.exists(flow_logger.log_dir)
        assert flow_logger.current_log_file is not None
    
    async def test_log_event(self, flow_logger):
        """Test logging a basic event"""
        component = "TestComponent"
        event_type = "test_event"
        data = {"test_key": "test_value"}
        
        await flow_logger.log_event(component, event_type, data)
        
        assert len(flow_logger.events) == 1
        event = flow_logger.events[0]
        assert event["component"] == component
        assert event["type"].startswith(event_type)  # Check type prefix since it includes task_id
        assert event["data"] == data
        assert "timestamp" in event
    
    async def test_log_error(self, flow_logger):
        """Test logging an error"""
        component = "TestComponent"
        error_msg = "Test error"
        error_type = "test_error"
        
        await flow_logger.log_error(component, error_msg, error_type)
        
        assert len(flow_logger.errors) == 1
        error = flow_logger.errors[0]
        assert error["component"] == component
        assert error["message"] == error_msg
        assert error["type"] == error_type
        assert "timestamp" in error
    
    async def test_get_recent_events(self, flow_logger):
        """Test retrieving recent events"""
        # Log multiple events
        for i in range(5):
            await flow_logger.log_event(
                "TestComponent",
                f"event_{i}",
                {"index": i}
            )
        
        # Get recent events
        recent = flow_logger.get_recent_events(3)
        assert len(recent) == 3
        assert recent[0]["type"].startswith("event_4")  # Most recent first
        assert recent[2]["type"].startswith("event_2")
    
    async def test_get_component_history(self, flow_logger):
        """Test retrieving history for a specific component"""
        component = "TestComponent"
        
        # Log events for different components
        await flow_logger.log_event(component, "test_event", {"data": 1})
        await flow_logger.log_event("OtherComponent", "other_event", {"data": 2})
        await flow_logger.log_event(component, "another_event", {"data": 3})
        
        history = flow_logger.get_component_history(component)
        assert len(history) == 2
        assert all(event["component"] == component for event in history)
    
    async def test_get_error_history(self, flow_logger):
        """Test retrieving error history"""
        # Log some errors
        await flow_logger.log_error("Component1", "Error 1", "type1")
        await flow_logger.log_error("Component2", "Error 2", "type2")
        
        errors = flow_logger.get_error_history()
        assert len(errors) == 2
        assert errors[0]["message"] == "Error 2"  # Most recent first
        assert errors[1]["message"] == "Error 1"
    
    async def test_clear_history(self, flow_logger):
        """Test clearing history"""
        # Log some events and errors
        await flow_logger.log_event("TestComponent", "test_event", {})
        await flow_logger.log_error("TestComponent", "Test error", "test_error")
        
        # Clear history
        flow_logger.clear_history()
        
        assert len(flow_logger.events) == 0
        assert len(flow_logger.errors) == 0
        assert len(flow_logger.history) == 0
    
    async def test_event_timestamp_ordering(self, flow_logger):
        """Test that events are properly timestamped and ordered"""
        # Log events with small delays
        await flow_logger.log_event("TestComponent", "event1", {})
        await asyncio.sleep(0.1)
        await flow_logger.log_event("TestComponent", "event2", {})
        
        events = flow_logger.get_recent_events(2)
        assert events[0]["type"].startswith("event2")
        assert events[1]["type"].startswith("event1")
        assert events[0]["timestamp"] > events[1]["timestamp"]
    
    async def test_history_limit(self, flow_logger):
        """Test that history respects the maximum size limit"""
        # Log more events than the history limit
        limit = flow_logger.max_history_size
        for i in range(limit + 10):
            await flow_logger.log_event("TestComponent", f"event_{i}", {})
        
        assert len(flow_logger.events) <= limit
        assert flow_logger.events[-1]["type"].startswith(f"event_{limit + 9}")  # Most recent event
    
    async def test_error_with_stack_trace(self, flow_logger):
        """Test logging an error with stack trace"""
        try:
            raise ValueError("Test exception")
        except Exception as e:
            await flow_logger.log_error(
                "TestComponent",
                str(e),
                "value_error",
                exc_info=e
            )
        
        error = flow_logger.errors[0]
        assert error["type"] == "value_error"
        assert "stack_trace" in error
        assert "ValueError: Test exception" in error["stack_trace"]
    
    async def test_concurrent_logging(self, flow_logger):
        """Test concurrent event logging"""
        async def log_events(count, task_id):
            for i in range(count):
                await flow_logger.log_event(
                    "TestComponent",
                    f"concurrent_event_{i}",
                    {"task": task_id}
                )
        
        # Log events from multiple concurrent tasks
        tasks = [log_events(5, i) for i in range(3)]
        await asyncio.gather(*tasks)
        
        assert len(flow_logger.events) == 15
        event_types = [e["type"] for e in flow_logger.events]
        assert len(set(event_types)) == 15  # All events should be unique
        
        # Verify each event has unique task identifier
        task_ids = set()
        for event in flow_logger.events:
            task_id = event["type"].split("_")[-1]
            task_ids.add(task_id)
        assert len(task_ids) == 3  # Should have 3 unique task IDs
    
    async def test_file_logging(self, flow_logger, tmp_path):
        """Test that events are properly logged to file"""
        # Set up logger with temporary directory
        flow_logger.log_dir = str(tmp_path)
        await flow_logger.setup()
        
        # Log some events
        await flow_logger.log_event("TestComponent", "file_test", {"data": "test"})
        await flow_logger.log_error("TestComponent", "File error", "file_error")
        
        # Verify log file exists and contains events
        assert os.path.exists(flow_logger.current_log_file)
        with open(flow_logger.current_log_file, 'r') as f:
            log_lines = f.readlines()
            assert len(log_lines) == 2  # Should have two log entries
            
            # Verify event data in log file
            for line in log_lines:
                log_data = json.loads(line.split("INFO")[-1].strip())
                assert "timestamp" in log_data
                assert "component" in log_data
                assert "type" in log_data
                assert "data" in log_data 