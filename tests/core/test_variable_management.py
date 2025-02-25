import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from src.models import Ticket, TicketStatus
from src.core.orchestrator import RequestOrchestrator
from src.tools.service_analyzer import ServiceAnalyzer
from src.utils.flow_logger import FlowLogger
from src.core.registry.base_registry import BaseRegistry
from src.core.registry import ServiceRegistry, ToolRegistry
from collections import deque
from typing import Any

# Test Data
SAMPLE_USER_INFO = {
    "user_id": "U123",
    "channel_id": "C456",
    "thread_ts": "1234567890.123",
    "ts": "1234567890.124"
}

SAMPLE_MESSAGE = "Please help me with task management"

@pytest.fixture
def mock_flow_logger():
    logger = Mock(spec=FlowLogger)
    logger.log_event = AsyncMock()
    return logger

@pytest.fixture
async def service_analyzer():
    mock_openai = AsyncMock()
    with patch('src.tools.service_analyzer.AsyncOpenAI', return_value=mock_openai):
        analyzer = ServiceAnalyzer(flow_logger=Mock(spec=FlowLogger))
        analyzer.openai = mock_openai
        return analyzer

@pytest.fixture
def mock_service_registry():
    registry = Mock(spec=ServiceRegistry)
    registry.initialized = True
    registry.get_item = Mock(return_value={
        "name": "Test Service",
        "description": "Test service for unit tests",
        "steps": []
    })
    return registry

@pytest.fixture
def mock_agent(mock_service_registry):
    agent = Mock()
    agent.service_registry = mock_service_registry
    agent.initialized = True
    return agent

@pytest.fixture
def orchestrator(mock_flow_logger, mock_agent):
    orchestrator = RequestOrchestrator(flow_logger=mock_flow_logger)
    orchestrator.service_analyzer = Mock(spec=ServiceAnalyzer)
    orchestrator.service_analyzer.analyze_request = AsyncMock()
    orchestrator.agent = mock_agent
    orchestrator._initialized = True
    return orchestrator

class TestTicketVariables:
    """Test suite for Ticket variable management"""
    
    def test_ticket_initialization(self):
        """Test ticket variable initialization"""
        ticket = Ticket(
            original_message=SAMPLE_MESSAGE,
            user_info=SAMPLE_USER_INFO,
            channel_id=SAMPLE_USER_INFO["channel_id"]
        )
        
        assert ticket.original_message == SAMPLE_MESSAGE
        assert ticket.user_info == SAMPLE_USER_INFO
        assert ticket.channel_id == SAMPLE_USER_INFO["channel_id"]
        assert ticket.status == TicketStatus.CREATED
        assert ticket.service is None
        assert ticket.entities == {}
        assert ticket.execution_results == []
        assert ticket.missing_entities == []
        assert ticket.execution_plan == []
        assert isinstance(ticket.execution_steps, deque)
        assert len(ticket.execution_steps) == 0
        
    @pytest.mark.asyncio
    async def test_ticket_status_transitions(self):
        """Test ticket status transitions"""
        ticket = Ticket(
            original_message=SAMPLE_MESSAGE,
            user_info=SAMPLE_USER_INFO,
            channel_id=SAMPLE_USER_INFO["channel_id"]
        )
        
        # Test status transitions
        ticket.update_status(TicketStatus.ANALYZING)
        assert ticket.status == TicketStatus.ANALYZING
        
        ticket.update_status(TicketStatus.EXECUTING)
        assert ticket.status == TicketStatus.EXECUTING
        
        ticket.update_status(TicketStatus.COMPLETED)
        assert ticket.status == TicketStatus.COMPLETED
        
    def test_ticket_error_handling(self):
        """Test ticket error management"""
        ticket = Ticket(
            original_message=SAMPLE_MESSAGE,
            user_info=SAMPLE_USER_INFO,
            channel_id=SAMPLE_USER_INFO["channel_id"]
        )
        
        error_msg = "Test error"
        error_type = "test_error"
        
        ticket.add_error(error_msg, error_type)
        assert len(ticket.errors) == 1
        assert ticket.errors[0]["message"] == error_msg
        assert ticket.errors[0]["type"] == error_type

class TestServiceAnalyzerVariables:
    """Test suite for ServiceAnalyzer variable management"""
    
    @pytest.mark.asyncio
    async def test_analysis_confidence_score(self, service_analyzer):
        """Test confidence score handling"""
        service_analyzer = await service_analyzer
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='{"confidence": 0.85, "understood_request": "test", "execution_steps": [{"step_number": 1, "service_id": "test_service", "description": "test", "required_params": {}, "optional_params": {}}], "missing_information": []}'))
        ]
        service_analyzer.openai.chat.completions.create = AsyncMock(return_value=mock_response)
        
        ticket = Ticket(
            original_message=SAMPLE_MESSAGE,
            user_info=SAMPLE_USER_INFO,
            channel_id=SAMPLE_USER_INFO["channel_id"]
        )
        
        # Mock services schema
        service_analyzer.services_schema = {
            "version": "1.0",
            "services": {
                "test_service": {
                    "name": "Test Service",
                    "description": "Test service for unit tests",
                    "steps": []
                }
            }
        }
        
        updated_ticket = await service_analyzer.analyze_request(ticket)
        
        assert updated_ticket.status == TicketStatus.EXECUTING
        assert len(updated_ticket.execution_steps) == 1
        assert updated_ticket.service == "test_service"

class TestOrchestratorVariables:
    """Test suite for Orchestrator variable management"""
    
    @pytest.mark.asyncio
    async def test_service_execution_state(self, orchestrator, mock_flow_logger):
        """Test service execution state management"""
        ticket = Ticket(
            original_message=SAMPLE_MESSAGE,
            user_info=SAMPLE_USER_INFO,
            channel_id=SAMPLE_USER_INFO["channel_id"]
        )
        ticket.service = "test_service"
        ticket.status = TicketStatus.EXECUTING
        
        # Mock analyzer response
        orchestrator.service_analyzer.analyze_request.return_value = ticket
        
        # Process request
        result_ticket = await orchestrator.process_request(
            message=SAMPLE_MESSAGE,
            user_info=SAMPLE_USER_INFO,
            channel_id=SAMPLE_USER_INFO["channel_id"]
        )
        
        assert result_ticket is not None
        assert result_ticket.status in [TicketStatus.COMPLETED, TicketStatus.ERROR]
        
    @pytest.mark.asyncio
    async def test_flow_logging_events(self, orchestrator, mock_flow_logger):
        """Test flow logging event propagation"""
        # Set up mock flow logger
        orchestrator.flow_logger = mock_flow_logger
        
        ticket = Ticket(
            original_message=SAMPLE_MESSAGE,
            user_info=SAMPLE_USER_INFO,
            channel_id=SAMPLE_USER_INFO["channel_id"]
        )
        ticket.service = "test_service"
        ticket.status = TicketStatus.EXECUTING
        
        # Mock analyzer response
        orchestrator.service_analyzer.analyze_request.return_value = ticket
        
        # Process request
        await orchestrator.process_request(
            message=SAMPLE_MESSAGE,
            user_info=SAMPLE_USER_INFO,
            channel_id=SAMPLE_USER_INFO["channel_id"]
        )
        
        # Verify flow logger was called
        assert mock_flow_logger.log_event.called
        
    @pytest.mark.asyncio
    async def test_error_handling_state(self, orchestrator, mock_flow_logger):
        """Test error handling state management"""
        # Set up mock flow logger
        orchestrator.flow_logger = mock_flow_logger
        
        # Create ticket with initial analyzing state
        ticket = Ticket(
            original_message=SAMPLE_MESSAGE,
            user_info=SAMPLE_USER_INFO,
            channel_id=SAMPLE_USER_INFO["channel_id"]
        )
        
        # Mock analyzer response to return the ticket in ANALYZING state
        async def mock_analyze_request(ticket):
            ticket.update_status(TicketStatus.ANALYZING)
            raise Exception("Test error")
        
        orchestrator.service_analyzer.analyze_request = mock_analyze_request
        
        # Process request
        result_ticket = await orchestrator.process_request(
            message=SAMPLE_MESSAGE,
            user_info=SAMPLE_USER_INFO,
            channel_id=SAMPLE_USER_INFO["channel_id"]
        )
        
        assert result_ticket is not None
        assert result_ticket.status == TicketStatus.ERROR
        assert len(result_ticket.errors) > 0
        assert result_ticket.errors[0]["type"] == "analysis_error"

class TestRegistry(BaseRegistry):
    """Concrete implementation of BaseRegistry for testing"""
    
    async def load_items(self) -> None:
        """Test implementation of load_items"""
        pass
        
    async def validate_item(self, item: Any) -> bool:
        """Test implementation of validate_item"""
        return True

class TestRegistryVariables:
    """Test suite for Registry variable management"""
    
    def test_registry_initialization_state(self):
        """Test registry initialization state management"""
        registry = TestRegistry("test")
        assert not registry.initialized
        
        # Mock initialization
        registry._initialized = True
        assert registry.initialized
        
    def test_registry_items_management(self):
        """Test registry items dictionary management"""
        registry = TestRegistry("test")
        
        # Mock item registration
        test_item = {"name": "test"}
        registry.items["test"] = test_item
        
        assert "test" in registry
        assert registry.get_item("test") == test_item
        assert len(registry) == 1 