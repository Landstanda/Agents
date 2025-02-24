import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from src.models import Ticket, TicketStatus
from src.core.orchestrator import RequestOrchestrator
from src.tools.service_analyzer import ServiceAnalyzer
from src.utils.flow_logger import FlowLogger
from src.core.registry import ServiceRegistry, ToolRegistry

# Test Data
SAMPLE_USER_INFO = {
    "user_id": "U123",
    "channel_id": "C456",
    "thread_ts": "1234567890.123",
    "ts": "1234567890.124"
}

SAMPLE_MESSAGE = "Please help me with task management"

@pytest.fixture
async def mock_flow_logger():
    logger = Mock(spec=FlowLogger)
    logger.log_event = AsyncMock()
    return logger

@pytest.fixture
async def service_analyzer():
    with patch('src.tools.service_analyzer.AsyncOpenAI') as mock_openai:
        analyzer = ServiceAnalyzer(flow_logger=Mock(spec=FlowLogger))
        analyzer.openai = mock_openai
        yield analyzer

@pytest.fixture
async def orchestrator(mock_flow_logger):
    orchestrator = RequestOrchestrator(flow_logger=mock_flow_logger)
    orchestrator.service_analyzer = Mock(spec=ServiceAnalyzer)
    orchestrator.service_analyzer.analyze_request = AsyncMock()
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
        assert ticket.execution_steps == []
        assert ticket.errors == []
        
    @pytest.mark.asyncio
    async def test_ticket_status_transitions(self):
        """Test ticket status transitions"""
        ticket = Ticket(SAMPLE_MESSAGE, SAMPLE_USER_INFO, SAMPLE_USER_INFO["channel_id"])
        
        # Test status transitions
        ticket.update_status(TicketStatus.ANALYZING)
        assert ticket.status == TicketStatus.ANALYZING
        
        ticket.update_status(TicketStatus.EXECUTING)
        assert ticket.status == TicketStatus.EXECUTING
        
        ticket.update_status(TicketStatus.COMPLETED)
        assert ticket.status == TicketStatus.COMPLETED
        
    def test_ticket_error_handling(self):
        """Test ticket error management"""
        ticket = Ticket(SAMPLE_MESSAGE, SAMPLE_USER_INFO, SAMPLE_USER_INFO["channel_id"])
        
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
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='{"confidence": 0.85, "understood_request": "test", "execution_steps": [], "missing_information": []}'))
        ]
        service_analyzer.openai.chat.completions.create = AsyncMock(return_value=mock_response)
        
        ticket = Ticket(SAMPLE_MESSAGE, SAMPLE_USER_INFO, SAMPLE_USER_INFO["channel_id"])
        updated_ticket = await service_analyzer.analyze_request(ticket)
        
        assert "confidence" in updated_ticket.execution_results[0]
        assert 0 <= updated_ticket.execution_results[0]["confidence"] <= 1
        
    @pytest.mark.asyncio
    async def test_execution_steps_structure(self, service_analyzer):
        """Test execution steps structure"""
        mock_steps = [
            {
                "step_number": 1,
                "service_id": "test_service",
                "description": "Test step",
                "required_params": {"param1": "value1"},
                "optional_params": {"param2": "value2"}
            }
        ]
        
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='''
                {
                    "confidence": 0.9,
                    "understood_request": "test",
                    "execution_steps": %s,
                    "missing_information": []
                }
            ''' % str(mock_steps).replace("'", '"')))
        ]
        service_analyzer.openai.chat.completions.create = AsyncMock(return_value=mock_response)
        
        ticket = Ticket(SAMPLE_MESSAGE, SAMPLE_USER_INFO, SAMPLE_USER_INFO["channel_id"])
        updated_ticket = await service_analyzer.analyze_request(ticket)
        
        assert len(updated_ticket.execution_steps) == 1
        assert updated_ticket.execution_steps[0]["step_number"] == 1
        assert "required_params" in updated_ticket.execution_steps[0]
        assert "optional_params" in updated_ticket.execution_steps[0]

class TestOrchestratorVariables:
    """Test suite for Orchestrator variable management"""
    
    @pytest.mark.asyncio
    async def test_service_execution_state(self, orchestrator):
        """Test service execution state management"""
        ticket = Ticket(SAMPLE_MESSAGE, SAMPLE_USER_INFO, SAMPLE_USER_INFO["channel_id"])
        
        # Mock analyzer response
        orchestrator.service_analyzer.analyze_request.return_value = ticket
        
        # Process request
        result_ticket = await orchestrator.process_request(
            message=SAMPLE_MESSAGE,
            user_info=SAMPLE_USER_INFO,
            channel_id=SAMPLE_USER_INFO["channel_id"]
        )
        
        assert result_ticket.status in [TicketStatus.COMPLETED, TicketStatus.ERROR]
        
    @pytest.mark.asyncio
    async def test_flow_logging_events(self, orchestrator, mock_flow_logger):
        """Test flow logging event propagation"""
        ticket = Ticket(SAMPLE_MESSAGE, SAMPLE_USER_INFO, SAMPLE_USER_INFO["channel_id"])
        
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
    async def test_error_handling_state(self, orchestrator):
        """Test error handling state management"""
        # Simulate error in service analyzer
        orchestrator.service_analyzer.analyze_request.side_effect = Exception("Test error")
        
        ticket = await orchestrator.process_request(
            message=SAMPLE_MESSAGE,
            user_info=SAMPLE_USER_INFO,
            channel_id=SAMPLE_USER_INFO["channel_id"]
        )
        
        assert ticket.status == TicketStatus.ERROR
        assert len(ticket.errors) > 0
        assert ticket.errors[0]["type"] == "processing_error"

class TestRegistryVariables:
    """Test suite for Registry variable management"""
    
    def test_registry_initialization_state(self):
        """Test registry initialization state management"""
        registry = BaseRegistry("test")
        assert not registry.initialized
        
        # Mock initialization
        registry._initialized = True
        assert registry.initialized
        
    def test_registry_items_management(self):
        """Test registry items dictionary management"""
        registry = BaseRegistry("test")
        
        # Mock item registration
        test_item = {"name": "test"}
        registry.items["test"] = test_item
        
        assert "test" in registry
        assert registry.get_item("test") == test_item
        assert len(registry) == 1 