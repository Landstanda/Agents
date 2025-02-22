import pytest
from unittest.mock import Mock, AsyncMock
import os
from datetime import datetime
import json
from src.tools.service_analyzer import ServiceAnalyzer
from src.models.ticket import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger

@pytest.fixture
def mock_flow_logger():
    """Create a mock FlowLogger with async methods"""
    logger = Mock(spec=FlowLogger)
    logger.log_event = AsyncMock()
    logger._setup_log_file = AsyncMock()
    return logger

@pytest.fixture
def service_analyzer(mock_flow_logger):
    """Create a ServiceAnalyzer instance with mocked logger but real GPT"""
    return ServiceAnalyzer(
        services_path="src/services/service_index.json",
        flow_logger=mock_flow_logger
    )

@pytest.fixture
def meeting_ticket():
    """Create a test ticket for a simple meeting request"""
    return Ticket(
        ticket_id="test_meeting_001",
        original_message="Schedule a team meeting tomorrow at 3pm",
        user_info={
            "user_id": "U123456",
            "channel_id": "C123456",
            "thread_ts": "1645036800.000100"
        }
    )

@pytest.fixture
def complex_ticket():
    """Create a test ticket for a complex multi-service request"""
    return Ticket(
        ticket_id="test_complex_001",
        original_message="Schedule a meeting with the dev team for tomorrow at 2pm and send them an email with the agenda",
        user_info={
            "user_id": "U123456",
            "channel_id": "C123456",
            "thread_ts": "1645036800.000100"
        }
    )

class TestServiceAnalyzerBasic:
    """Test the ServiceAnalyzer with real GPT integration - Basic Cases"""

    @pytest.mark.asyncio
    async def test_simple_meeting_request(self, service_analyzer, meeting_ticket):
        """
        Test analysis of a simple meeting scheduling request.
        Verifies:
        - Service identification (schedule_meeting)
        - Required parameter extraction (time, date)
        - Execution plan generation
        - Confidence threshold
        """
        print("\n=== Simple Meeting Request Test ===")
        print(f"Original Message: {meeting_ticket.original_message}")
        
        # Analyze the request
        result = await service_analyzer.analyze_request(meeting_ticket)
        
        print("\nGPT Analysis Result:")
        print(f"Status: {result.status}")
        print(f"Service: {result.service}")
        print(f"Entities: {json.dumps(result.entities, indent=2)}")
        print("\nExecution Plan:")
        print(json.dumps(result.execution_plan, indent=2))
        
        if result.errors:
            print("\nErrors:")
            print(json.dumps(result.errors, indent=2))
        
        if result.missing_entities:
            print("\nMissing Information:")
            print(json.dumps(result.missing_entities, indent=2))
        
        # Verify basic requirements
        assert result.status == TicketStatus.EXECUTING, "Expected status to be EXECUTING"
        assert len(result.execution_plan) == 1, "Expected one execution step"
        assert result.execution_plan[0]["service_id"] == "schedule_meeting", "Expected schedule_meeting service"
        
        # Verify required parameters were extracted
        required_params = result.execution_plan[0].get("required_params", {})
        assert "time" in required_params, "Missing required parameter: time"
        assert "date" in required_params, "Missing required parameter: date"
        
        # Verify no errors occurred
        assert not result.errors, f"Unexpected errors: {result.errors}"
        
        # Verify logger was called
        service_analyzer.flow_logger.log_event.assert_called_with(
            "ServiceAnalyzer",
            "request_analyzed",
            {
                "ticket_id": meeting_ticket.ticket_id,
                "confidence": 1.0,  # GPT returned high confidence for this clear request
                "execution_plan": result.execution_plan,
                "missing_inputs": result.missing_entities
            }
        )

    @pytest.mark.asyncio
    async def test_complex_request(self, service_analyzer, complex_ticket):
        """
        Test analysis of a complex request requiring multiple services.
        Verifies:
        - Multiple service identification
        - Correct service ordering
        - Entity distribution across services
        - Dependencies between steps
        """
        print("\n=== Complex Multi-Service Request Test ===")
        print(f"Original Message: {complex_ticket.original_message}")
        
        # Analyze the request
        result = await service_analyzer.analyze_request(complex_ticket)
        
        print("\nGPT Analysis Result:")
        print(f"Status: {result.status}")
        print(f"Service: {result.service}")
        print(f"Entities: {json.dumps(result.entities, indent=2)}")
        print("\nExecution Plan:")
        print(json.dumps(result.execution_plan, indent=2))
        
        if result.errors:
            print("\nErrors:")
            print(json.dumps(result.errors, indent=2))
        
        if result.missing_entities:
            print("\nMissing Information:")
            print(json.dumps(result.missing_entities, indent=2))
        
        # Verify multi-service requirements
        assert result.status in [TicketStatus.EXECUTING, TicketStatus.WAITING_INPUT], \
            "Expected status to be EXECUTING or WAITING_INPUT"
        assert len(result.execution_plan) >= 2, "Expected at least two execution steps"
        
        # Verify services are in correct order
        services = [step["service_id"] for step in result.execution_plan]
        assert "schedule_meeting" in services, "Expected schedule_meeting service"
        assert "email_composer" in services, "Expected email_composer service"
        
        # Verify no errors occurred
        assert not result.errors, f"Unexpected errors: {result.errors}"

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 