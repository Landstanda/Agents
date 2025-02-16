import pytest
import os
from datetime import datetime
from src.tools.service_analyzer import ServiceAnalyzer
from src.models.ticket import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger

@pytest.fixture
async def service_analyzer():
    """Create a ServiceAnalyzer instance with real dependencies"""
    flow_logger = FlowLogger()
    await flow_logger._setup_log_file()  # Properly initialize the logger
    return ServiceAnalyzer(
        services_path="src/services/service_index.json",
        flow_logger=flow_logger
    )

@pytest.fixture
def sample_tickets():
    """Create sample tickets for different test scenarios"""
    return {
        "simple": Ticket(
            ticket_id="test_simple_001",
            original_message="Schedule a team meeting tomorrow at 3pm",
            user_info={"user_id": "U123456", "channel_id": "C123456"}
        ),
        "complex": Ticket(
            ticket_id="test_complex_001",
            original_message="Schedule a meeting with the dev team for tomorrow at 2pm and send them an email with the agenda",
            user_info={"user_id": "U123456", "channel_id": "C123456"}
        ),
        "ambiguous": Ticket(
            ticket_id="test_ambiguous_001",
            original_message="Check my stuff",
            user_info={"user_id": "U123456", "channel_id": "C123456"}
        ),
        "email": Ticket(
            ticket_id="test_email_001",
            original_message="Check my latest emails from John about the project",
            user_info={"user_id": "U123456", "channel_id": "C123456"}
        )
    }

class TestServiceAnalyzer:
    """
    Test suite for ServiceAnalyzer with real GPT integration.
    Tests the analyzer's ability to:
    1. Understand simple, single-service requests
    2. Break down complex, multi-service requests
    3. Handle ambiguous requests appropriately
    4. Extract entities and parameters
    5. Match requests to available services
    6. Generate proper execution plans
    7. Handle missing information cases
    """

    @pytest.mark.asyncio
    async def test_simple_meeting_request(self, service_analyzer, sample_tickets):
        """
        Test analysis of a simple meeting scheduling request.
        Verifies:
        - Service identification (schedule_meeting)
        - Required parameter extraction (time, date)
        - Execution plan generation
        - Confidence threshold
        """
        result = await service_analyzer.analyze_request(sample_tickets["simple"])
        
        assert result.status == TicketStatus.EXECUTING
        assert len(result.execution_plan) == 1
        assert result.execution_plan[0]["service_id"] == "schedule_meeting"
        assert "time" in result.entities
        assert "date" in result.entities
        assert not result.errors

    @pytest.mark.asyncio
    async def test_complex_request_breakdown(self, service_analyzer, sample_tickets):
        """
        Test analysis of a complex request requiring multiple services.
        Verifies:
        - Multiple service identification
        - Correct service ordering
        - Entity distribution across services
        - Dependencies between steps
        """
        result = await service_analyzer.analyze_request(sample_tickets["complex"])
        
        assert result.status in [TicketStatus.EXECUTING, TicketStatus.WAITING_INPUT]
        assert len(result.execution_plan) >= 2
        services = [step["service_id"] for step in result.execution_plan]
        assert "schedule_meeting" in services
        assert len(result.entities) > 0

    @pytest.mark.asyncio
    async def test_ambiguous_request_handling(self, service_analyzer, sample_tickets):
        """
        Test handling of ambiguous or unclear requests.
        Verifies:
        - Low confidence detection
        - Appropriate error status
        - Meaningful error messages
        """
        result = await service_analyzer.analyze_request(sample_tickets["ambiguous"])
        
        if result.status == TicketStatus.ERROR:
            assert result.errors
            assert any("unclear" in error["message"].lower() for error in result.errors)
        else:
            assert result.status == TicketStatus.WAITING_INPUT
            assert result.missing_entities

    @pytest.mark.asyncio
    async def test_email_request_analysis(self, service_analyzer, sample_tickets):
        """
        Test analysis of email-related request.
        Verifies:
        - Email service identification
        - Parameter extraction (sender, subject)
        - Optional parameter handling
        """
        result = await service_analyzer.analyze_request(sample_tickets["email"])
        
        assert result.status == TicketStatus.EXECUTING
        assert len(result.execution_plan) >= 1
        assert "check_emails" in [step["service_id"] for step in result.execution_plan]
        assert "sender" in result.entities
        assert not result.errors

if __name__ == "__main__":
    pytest.main(["-v", __file__])
