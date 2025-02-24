import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from src.core.orchestrator import RequestOrchestrator
from src.models import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger
from src.tools.service_analyzer import ServiceAnalyzer
from src.core.agent.service_agent import ServiceAgent
from src.tools.message_maker import MessageMaker

@pytest.fixture
def flow_logger():
    """Create a mock flow logger"""
    logger = AsyncMock(spec=FlowLogger)
    logger.log_event = AsyncMock()
    return logger

@pytest.fixture
def mock_service_analyzer():
    """Create a mock service analyzer"""
    analyzer = AsyncMock(spec=ServiceAnalyzer)
    analyzer.analyze_request = AsyncMock()
    return analyzer

@pytest.fixture
def mock_agent():
    """Create a mock service agent"""
    agent = AsyncMock(spec=ServiceAgent)
    agent.execute_service = AsyncMock()
    agent.process_ticket = AsyncMock()
    agent.initialize = AsyncMock()
    return agent

@pytest.fixture
def mock_message_maker():
    """Create a mock message maker"""
    maker = AsyncMock(spec=MessageMaker)
    maker.send_message = AsyncMock()
    maker.send_error_message = AsyncMock()
    return maker

@pytest.fixture
async def orchestrator(flow_logger, mock_service_analyzer, mock_agent, mock_message_maker):
    """Create an orchestrator with mock components"""
    orchestrator = RequestOrchestrator(flow_logger=flow_logger)
    orchestrator.service_analyzer = mock_service_analyzer
    orchestrator.agent = mock_agent
    orchestrator.message_maker = mock_message_maker
    await orchestrator.initialize()
    return orchestrator

def _update_ticket_for_test(ticket: Ticket, status: TicketStatus) -> Ticket:
    """Helper function to update ticket status for testing"""
    ticket.status = status
    return ticket

@pytest.mark.asyncio
async def test_orchestrator_initialization(orchestrator, mock_agent, mock_service_analyzer, mock_message_maker, flow_logger):
    """Test orchestrator initialization"""
    orchestrator_instance = await orchestrator
    assert orchestrator_instance.agent == mock_agent
    assert orchestrator_instance.service_analyzer == mock_service_analyzer
    assert orchestrator_instance.message_maker == mock_message_maker
    assert orchestrator_instance.flow_logger == flow_logger
    mock_agent.process_ticket.assert_called_once()

@pytest.mark.asyncio
async def test_process_request_success(orchestrator, mock_service_analyzer, mock_agent, mock_message_maker):
    """Test successful request processing"""
    orchestrator_instance = await orchestrator
    
    # Setup test data
    message = "Schedule a meeting with John tomorrow at 3pm"
    user_info = {"user_id": "U123"}
    channel_id = "C456"

    # Configure mock responses
    mock_service_analyzer.analyze_request.side_effect = lambda ticket: _update_ticket_for_test(ticket, TicketStatus.EXECUTING)
    mock_agent.execute_service.return_value = {
        "status": "success",
        "results": {"event_id": "123"}
    }

    # Process request
    ticket = await orchestrator_instance.process_request(
        message=message,
        user_info=user_info,
        channel_id=channel_id
    )

    # Verify ticket status and interactions
    assert ticket.status == TicketStatus.COMPLETED
    mock_service_analyzer.analyze_request.assert_called_once()
    mock_agent.execute_service.assert_called_once()
    mock_message_maker.send_message.assert_called()

@pytest.mark.asyncio
async def test_process_request_analysis_error(orchestrator, mock_service_analyzer, mock_message_maker):
    """Test request processing with analysis error"""
    orchestrator_instance = await orchestrator
    
    # Setup test data
    message = "Invalid request"
    user_info = {"user_id": "U123"}

    # Configure mock to simulate analysis error
    mock_service_analyzer.analyze_request.side_effect = Exception("Analysis failed")

    # Process request
    ticket = await orchestrator_instance.process_request(
        message=message,
        user_info=user_info,
        channel_id="C456"
    )

    # Verify error handling
    assert ticket.status == TicketStatus.ERROR
    mock_message_maker.send_error_message.assert_called()

@pytest.mark.asyncio
async def test_process_request_execution_error(orchestrator, mock_service_analyzer, mock_agent, mock_message_maker):
    """Test request processing with execution error"""
    orchestrator_instance = await orchestrator
    
    # Setup test data
    message = "Schedule a meeting tomorrow"
    user_info = {"user_id": "U123"}

    # Configure mocks
    mock_service_analyzer.analyze_request.side_effect = lambda ticket: _update_ticket_for_test(ticket, TicketStatus.EXECUTING)
    mock_agent.execute_service.side_effect = Exception("Execution failed")

    # Process request
    ticket = await orchestrator_instance.process_request(
        message=message,
        user_info=user_info,
        channel_id="C456"
    )

    # Verify error handling
    assert ticket.status == TicketStatus.ERROR
    mock_message_maker.send_error_message.assert_called()

@pytest.mark.asyncio
async def test_process_request_waiting_input(orchestrator, mock_service_analyzer, mock_message_maker):
    """Test request processing when waiting for input"""
    orchestrator_instance = await orchestrator
    
    # Setup test data
    message = "Schedule a meeting"
    user_info = {"user_id": "U123"}

    # Configure mock for waiting input
    mock_service_analyzer.analyze_request.side_effect = lambda ticket: _update_ticket_for_test(ticket, TicketStatus.WAITING_INPUT)

    # Process request
    ticket = await orchestrator_instance.process_request(
        message=message,
        user_info=user_info,
        channel_id="C456"
    )

    # Verify waiting input handling
    assert ticket.status == TicketStatus.WAITING_INPUT
    mock_message_maker.send_message.assert_called()

@pytest.mark.asyncio
async def test_acknowledgment_message(orchestrator, mock_service_analyzer, mock_agent, mock_message_maker):
    """Test acknowledgment message sending"""
    orchestrator_instance = await orchestrator
    
    # Setup test data
    message = "Schedule a meeting tomorrow at 3pm"
    user_info = {"user_id": "U123"}

    # Configure mocks
    mock_service_analyzer.analyze_request.side_effect = lambda ticket: _update_ticket_for_test(ticket, TicketStatus.EXECUTING)
    mock_agent.execute_service.return_value = {"status": "success"}

    # Process request
    await orchestrator_instance.process_request(
        message=message,
        user_info=user_info,
        channel_id="C456"
    )

    # Verify acknowledgment was sent
    mock_message_maker.send_message.assert_called()

class TestRequestOrchestrator:
    """Tests for the RequestOrchestrator class"""

    @pytest.mark.asyncio
    async def test_successful_request_processing(self, orchestrator, flow_logger):
        """Test successful processing of a request"""
        # Get initialized orchestrator
        orchestrator_instance = await orchestrator
        
        # Setup test data
        message = "Schedule a meeting with John tomorrow at 3pm"
        user_info = {"user_id": "U123"}
        channel_id = "C456"

        # Configure mock analyzer response
        ticket = Ticket(
            original_message=message,
            user_info=user_info,
            channel_id=channel_id,
            service="schedule_meeting",
            status=TicketStatus.EXECUTING
        )
        orchestrator_instance.service_analyzer.analyze_request.return_value = ticket

        # Configure mock agent response
        orchestrator_instance.agent.execute_service.return_value = {
            "status": "success",
            "results": {"event_id": "123"}
        }

        # Process request
        result = await orchestrator_instance.process_request(
            message=message,
            user_info=user_info,
            channel_id=channel_id
        )

        # Verify flow
        assert result.status == TicketStatus.COMPLETED
        assert orchestrator_instance.service_analyzer.analyze_request.called
        assert orchestrator_instance.agent.execute_service.called
        assert orchestrator_instance.message_maker.send_message.called
        
        # Verify logging
        assert flow_logger.log_event.call_count >= 2
        flow_logger.log_event.assert_any_call(
            "Orchestrator",
            "request_received",
            {"ticket_id": result.ticket_id, "message": message, "channel": channel_id}
        )

    @pytest.mark.asyncio
    async def test_analysis_error_handling(self, orchestrator):
        """Test handling of analysis errors"""
        # Get initialized orchestrator
        orchestrator_instance = await orchestrator
        
        # Setup test data
        message = "Invalid request"
        user_info = {"user_id": "U123"}
        channel_id = "C456"

        # Configure analyzer to raise an error
        error_msg = "Analysis failed"
        orchestrator_instance.service_analyzer.analyze_request.side_effect = Exception(error_msg)

        # Process request
        result = await orchestrator_instance.process_request(
            message=message,
            user_info=user_info,
            channel_id=channel_id
        )

        # Verify error handling
        assert result.status == TicketStatus.ERROR
        assert len(result.errors) > 0
        assert error_msg in result.errors[0]["message"]
        assert orchestrator_instance.message_maker.send_error_message.called
        assert not orchestrator_instance.agent.execute_service.called

    @pytest.mark.asyncio
    async def test_missing_information_handling(self, orchestrator):
        """Test handling of requests with missing information"""
        # Get initialized orchestrator
        orchestrator_instance = await orchestrator
        
        # Setup test data
        message = "Schedule a meeting"
        user_info = {"user_id": "U123"}
        channel_id = "C456"

        # Configure analyzer to return ticket with missing info
        waiting_ticket = Ticket(
            original_message=message,
            user_info=user_info,
            channel_id=channel_id,
            status=TicketStatus.WAITING_INPUT
        )
        waiting_ticket.missing_entities = ["time", "date"]
        orchestrator_instance.service_analyzer.analyze_request.return_value = waiting_ticket

        # Process request
        result = await orchestrator_instance.process_request(
            message=message,
            user_info=user_info,
            channel_id=channel_id
        )

        # Verify handling
        assert result.status == TicketStatus.WAITING_INPUT
        assert len(result.missing_entities) == 2
        assert orchestrator_instance.message_maker.send_message.called
        assert not orchestrator_instance.agent.execute_service.called

    @pytest.mark.asyncio
    async def test_execution_error_handling(self, orchestrator):
        """Test handling of execution errors"""
        # Get initialized orchestrator
        orchestrator_instance = await orchestrator
        
        # Setup test data
        message = "Schedule a meeting tomorrow"
        user_info = {"user_id": "U123"}
        channel_id = "C456"

        # Configure successful analysis
        ticket = Ticket(
            original_message=message,
            user_info=user_info,
            channel_id=channel_id,
            service="schedule_meeting",
            status=TicketStatus.EXECUTING
        )
        orchestrator_instance.service_analyzer.analyze_request.return_value = ticket

        # Configure execution error
        error_msg = "Execution failed"
        orchestrator_instance.agent.execute_service.side_effect = Exception(error_msg)

        # Process request
        result = await orchestrator_instance.process_request(
            message=message,
            user_info=user_info,
            channel_id=channel_id
        )

        # Verify error handling
        assert result.status == TicketStatus.ERROR
        assert len(result.errors) > 0
        assert error_msg in result.errors[0]["message"]
        assert orchestrator_instance.message_maker.send_error_message.called

    @pytest.mark.asyncio
    async def test_acknowledgment_sending(self, orchestrator):
        """Test sending of acknowledgment messages"""
        # Get initialized orchestrator
        orchestrator_instance = await orchestrator
        
        # Setup test data
        message = "Schedule a meeting tomorrow at 3pm"
        user_info = {"user_id": "U123"}
        channel_id = "C456"

        # Configure successful analysis
        executing_ticket = Ticket(
            original_message=message,
            user_info=user_info,
            channel_id=channel_id,
            service="schedule_meeting",
            status=TicketStatus.EXECUTING
        )
        orchestrator_instance.service_analyzer.analyze_request.return_value = executing_ticket

        # Configure successful execution
        orchestrator_instance.agent.execute_service.return_value = {
            "status": "success",
            "results": {"event_id": "123"}
        }

        # Process request
        await orchestrator_instance.process_request(
            message=message,
            user_info=user_info,
            channel_id=channel_id
        )

        # Verify acknowledgment was sent
        assert orchestrator_instance.message_maker.send_message.call_count >= 2
        # First call should be acknowledgment
        first_call_args = orchestrator_instance.message_maker.send_message.call_args_list[0]
        assert "working on your request" in str(first_call_args).lower() 