import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
from src.tools.service_analyzer import ServiceAnalyzer
from src.models import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger

@pytest.fixture
def flow_logger():
    """Create a mock flow logger"""
    return AsyncMock(spec=FlowLogger)

@pytest.fixture
def service_analyzer(flow_logger):
    """Create a service analyzer for testing"""
    return ServiceAnalyzer(flow_logger=flow_logger)

@pytest.mark.asyncio
async def test_analyzer_handles_value_error(service_analyzer):
    """Test handling of ValueError during analysis"""
    # Create test ticket
    ticket = Ticket(
        original_message="test request",
        user_info={"user_id": "U123", "channel_id": "C456"},
        channel_id="C456"
    )
    
    # Mock OpenAI to raise ValueError
    with patch('src.tools.service_analyzer.AsyncOpenAI') as mock_openai:
        error_msg = "Failed to parse request"
        mock_openai.return_value.chat.completions.create = AsyncMock(
            side_effect=ValueError(error_msg)
        )
        
        # Analyze request
        result = await service_analyzer.analyze_request(ticket)
        
        # Verify error handling
        assert result.status == TicketStatus.ERROR
        assert len(result.errors) > 0
        assert any(error_msg in str(error.get("message", "")) for error in result.errors)

@pytest.mark.asyncio
async def test_analyzer_handles_invalid_json(service_analyzer):
    """Test handling of invalid JSON response"""
    ticket = Ticket(
        original_message="test request",
        user_info={"user_id": "U123", "channel_id": "C456"},
        channel_id="C456"
    )
    
    # Mock OpenAI to return invalid JSON
    with patch('src.tools.service_analyzer.AsyncOpenAI') as mock_openai:
        mock_completion = AsyncMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Invalid JSON"))
        ]
        mock_openai.return_value.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        
        # Analyze request
        result = await service_analyzer.analyze_request(ticket)
        
        # Verify error handling
        assert result.status == TicketStatus.ERROR
        assert len(result.errors) > 0
        assert any("Invalid JSON" in str(error.get("message", "")) for error in result.errors)

@pytest.mark.asyncio
async def test_analyzer_handles_missing_fields(service_analyzer):
    """Test handling of response missing required fields"""
    ticket = Ticket(
        original_message="test request",
        user_info={"user_id": "U123", "channel_id": "C456"},
        channel_id="C456"
    )
    
    # Mock OpenAI to return incomplete JSON
    with patch('src.tools.service_analyzer.AsyncOpenAI') as mock_openai:
        mock_completion = AsyncMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content=json.dumps({
                "understood_request": "test request",
                # Missing required fields
            })))
        ]
        mock_openai.return_value.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        
        # Analyze request
        result = await service_analyzer.analyze_request(ticket)
        
        # Verify error handling
        assert result.status == TicketStatus.ERROR
        assert len(result.errors) > 0
        assert any("Invalid analysis structure" in str(error.get("message", "")) for error in result.errors) 