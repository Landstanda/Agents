import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
from src.tools.service_analyzer import ServiceAnalyzer
from src.models import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger

@pytest.fixture
def flow_logger():
    return AsyncMock(spec=FlowLogger)

@pytest.fixture
def service_analyzer(flow_logger):
    return ServiceAnalyzer(flow_logger=flow_logger)

@pytest.fixture
def sample_service_response():
    return {
        "understood_request": "Schedule a meeting with John tomorrow at 3pm",
        "confidence": 0.95,
        "execution_steps": [
            {
                "step_number": 1,
                "service_id": "schedule_meeting",
                "description": "Schedule a meeting",
                "required_params": {
                    "time": "3pm",
                    "date": "tomorrow",
                    "attendee": "John"
                },
                "optional_params": {}
            }
        ],
        "missing_information": []
    }

@pytest.mark.asyncio
async def test_successful_request_analysis(service_analyzer, sample_service_response):
    """Test successful analysis of a user request"""
    # Create test ticket
    ticket = Ticket(
        original_message="Schedule a meeting with John tomorrow at 3pm",
        user_info={"user_id": "U123", "channel_id": "C456"},
        channel_id="C456"
    )
    
    # Mock OpenAI response
    with patch('src.tools.service_analyzer.AsyncOpenAI') as mock_openai:
        mock_completion = AsyncMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content=json.dumps(sample_service_response)))
        ]
        mock_openai.return_value.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        
        # Analyze request
        result = await service_analyzer.analyze_request(ticket)
        
        # Verify successful analysis
        assert result.status == TicketStatus.EXECUTING
        assert result.service == "schedule_meeting"
        assert len(result.execution_steps) == 1
        assert result.execution_steps[0]["service_id"] == "schedule_meeting"

@pytest.mark.asyncio
async def test_step_generation(service_analyzer, sample_service_response):
    """Test proper generation of execution steps"""
    # Create test ticket
    ticket = Ticket(
        original_message="Schedule a meeting with John tomorrow at 3pm",
        user_info={"user_id": "U123", "channel_id": "C456"},
        channel_id="C456"
    )
    
    # Mock OpenAI response
    with patch('src.tools.service_analyzer.AsyncOpenAI') as mock_openai:
        mock_completion = AsyncMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content=json.dumps(sample_service_response)))
        ]
        mock_openai.return_value.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        
        # Analyze request
        result = await service_analyzer.analyze_request(ticket)
        
        # Verify steps structure
        assert len(result.execution_steps) == 1
        step = result.execution_steps[0]
        assert step["step_number"] == 1
        assert step["service_id"] == "schedule_meeting"
        assert step["description"] == "Schedule a meeting with John tomorrow at 3pm"
        assert "time" in step["required_params"]
        assert "date" in step["required_params"]
        assert "participants" in step["optional_params"] 