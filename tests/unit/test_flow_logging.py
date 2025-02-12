import pytest
import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
from datetime import datetime
from src.office.reception.front_desk import FrontDesk
from src.utils.flow_logger import FlowLogger

@pytest.fixture
def flow_logger():
    """Create a test flow logger instance."""
    return FlowLogger()

@pytest.fixture
def mock_slack_client():
    """Create a mock Slack client."""
    mock_client = AsyncMock()
    mock_client.users_info = AsyncMock(return_value={
        "ok": True,
        "user": {
            "id": "U123456",
            "real_name": "Test User",
            "is_bot": False
        }
    })
    mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})
    return mock_client

@pytest.fixture
def office_components(flow_logger, mock_slack_client):
    """Create and connect all office components with flow logger."""
    front_desk = FrontDesk()
    front_desk.flow_logger = flow_logger
    front_desk.nlp.flow_logger = flow_logger
    front_desk.cookbook.flow_logger = flow_logger
    front_desk.task_manager.flow_logger = flow_logger
    front_desk.request_tracker.flow_logger = flow_logger
    front_desk.ceo.flow_logger = flow_logger
    front_desk.web_client = mock_slack_client
    return front_desk

@pytest.mark.asyncio
async def test_flow_logging_basic(flow_logger):
    """Test basic flow logging functionality."""
    # Test event logging
    await flow_logger.log_event(
        "Test Component",
        "Test Event",
        {"key": "value"}
    )
    
    # Check log file creation
    log_file = flow_logger.log_dir / f"flow_log_{datetime.now().strftime('%Y%m%d')}.txt"
    assert log_file.exists()
    
    # Verify log content
    content = log_file.read_text()
    assert "Test Component - Test Event" in content
    assert "key: value" in content

@pytest.mark.asyncio
async def test_flow_logging_integration(office_components, flow_logger):
    """Test flow logging across multiple components."""
    message = {
        "type": "message",
        "channel": "C123456",
        "user": "U123456",
        "text": "Schedule a meeting with John tomorrow at 2pm",
        "ts": "1234567890.123456"
    }
    
    # Process the message
    await office_components.handle_message(message)
    
    # Check log file
    log_file = flow_logger.log_dir / f"flow_log_{datetime.now().strftime('%Y%m%d')}.txt"
    assert log_file.exists()
    
    # Verify log content contains entries from different components
    content = log_file.read_text()
    
    # Check for Front Desk logging
    assert "User Message" in content
    assert "Incoming Request" in content
    
    # Check for NLP Processor logging
    assert "NLP Processor" in content
    assert "Message Analysis" in content
    
    # Check for Cookbook Manager logging
    assert "Cookbook Manager" in content

@pytest.mark.asyncio
async def test_flow_logging_error_handling(office_components, flow_logger):
    """Test flow logging during error conditions."""
    # Force an error by making the NLP processor raise an exception
    office_components.nlp.process_message = AsyncMock(side_effect=Exception("Test error"))
    
    message = {
        "type": "message",
        "channel": "C123456",
        "user": "U123456",
        "text": "This will cause an error",
        "ts": "1234567890.123456"
    }
    
    # Process the message
    await office_components.handle_message(message)
    
    # Check log file
    log_file = flow_logger.log_dir / f"flow_log_{datetime.now().strftime('%Y%m%d')}.txt"
    assert log_file.exists()
    
    # Verify error logging
    content = log_file.read_text()
    assert "Error" in content or "error" in content.lower() 