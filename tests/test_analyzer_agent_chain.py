import pytest
import asyncio
import logging
from datetime import datetime
from src.core.agent import BaseAgent
from src.tools.service_analyzer import ServiceAnalyzer
from src.models.ticket import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger
from src.execution.context import ExecutionContext
from src.core.services.registry import ServiceRegistry
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import os
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Mark all tests as async
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_openai():
    """Mock OpenAI client"""
    mock = AsyncMock()
    mock.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(content=json.dumps({
            "understood_request": "yes",
            "confidence": 0.9,
            "execution_steps": [{
                "step_number": 1,
                "service_id": "schedule_meeting",
                "description": "Schedule a team meeting",
                "required_params": {"time": "3pm", "date": "tomorrow"},
                "optional_params": {}
            }],
            "missing_information": []
        })))]
    ))
    return mock

@pytest.fixture
async def flow_logger():
    """Create and initialize FlowLogger"""
    logger = FlowLogger()
    logger.log_event = AsyncMock()  # Mock the log_event method
    await logger.setup()
    return logger

@pytest.fixture
async def service_analyzer(flow_logger):
    """Create ServiceAnalyzer instance"""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "mock-key"}), \
         patch('src.tools.service_analyzer.AsyncOpenAI') as mock_openai, \
         patch('src.tools.service_analyzer.ServiceAnalyzer._load_services_schema', 
               return_value={"services": {"schedule_meeting": {}, "send_email": {}, "google_auth": {}}}):
        # Configure mock OpenAI response
        mock_openai.return_value.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "understood_request": "Test request understood",
                "confidence": 0.9,
                "execution_steps": [{
                    "step_number": 1,
                    "service_id": "schedule_meeting",
                    "description": "Schedule a team meeting",
                    "required_params": {"time": "3pm", "date": "tomorrow"},
                    "optional_params": {}
                }],
                "missing_information": []
            })))]
        ))
        
        # Create mock flow logger
        mock_flow_logger = MagicMock()
        mock_flow_logger.log_event = AsyncMock()
        
        analyzer = ServiceAnalyzer(
            services_path="src/services/service_index.json",
            flow_logger=mock_flow_logger
        )
        return analyzer

@pytest.fixture
async def mock_agent():
    agent = AsyncMock()
    agent._initialized = True
    agent.service_registry = AsyncMock()
    agent.tool_registry = AsyncMock()
    agent.executor = AsyncMock()

    async def mock_process_ticket(ticket):
        try:
            for step in ticket.execution_plan:
                result = await agent.execute_service(step)
                ticket.execution_results.append(result)
            return ticket
        except Exception as e:
            ticket.update_status(TicketStatus.ERROR)
            ticket.add_error(str(e), "execution_error")
            raise

    async def mock_execute_service(step):
        return {
            "success": True,
            "result": f"Executed {step['service_id']} with params {step.get('required_params', {})}",
            "step": step
        }

    agent.process_ticket = AsyncMock(side_effect=mock_process_ticket)
    agent.execute_service = AsyncMock(side_effect=mock_execute_service)
    return agent

@pytest.fixture
def sample_tickets():
    """Create sample tickets for different scenarios"""
    return {
        "simple": Ticket(
            ticket_id="test_chain_001",
            original_message="Schedule a team meeting tomorrow at 3pm",
            user_info={"user_id": "U123456", "channel_id": "C123456"}
        ),
        "multi_step": Ticket(
            ticket_id="test_chain_002",
            original_message="Schedule a meeting for tomorrow and send the agenda via email",
            user_info={"user_id": "U123456", "channel_id": "C123456"}
        ),
        "with_auth": Ticket(
            ticket_id="test_chain_003",
            original_message="Check my calendar for conflicts next week",
            user_info={"user_id": "U123456", "channel_id": "C123456"}
        )
    }

class TestAnalyzerAgentChain:
    """Test suite for Service Analyzer to Agent execution chain"""

    async def test_basic_request_flow(self, service_analyzer, mock_agent, sample_tickets):
        """Test basic request flow from analyzer to agent"""
        analyzer = await service_analyzer
        agent = await mock_agent
        ticket = sample_tickets["simple"]
        
        # Mock OpenAI response
        analyzer.openai.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "understood_request": "yes",
                "confidence": 0.9,
                "execution_steps": [{
                    "step_number": 1,
                    "service_id": "schedule_meeting",
                    "description": "Schedule a team meeting",
                    "required_params": {"time": "3pm", "date": "tomorrow"},
                    "optional_params": {}
                }],
                "missing_information": []
            })))]
        ))
        
        # Analyze request
        analyzed_ticket = await analyzer.analyze_request(ticket)
        assert analyzed_ticket.status == TicketStatus.EXECUTING
        assert analyzed_ticket.execution_plan
        
        # Mock successful execution
        agent.execute_service.return_value = {"success": True}
        
        # Process with agent
        await agent.process_ticket(analyzed_ticket)
        
        # Verify agent interaction
        agent.process_ticket.assert_called_once()
        assert analyzed_ticket.status in [TicketStatus.COMPLETED, TicketStatus.EXECUTING]
        assert not analyzed_ticket.errors

    async def test_multi_step_execution(self, service_analyzer, mock_agent, sample_tickets):
        """Test multi-step service execution chain"""
        analyzer = await service_analyzer
        agent = await mock_agent
        ticket = sample_tickets["multi_step"]
        
        # Mock OpenAI response for multi-step
        analyzer.openai.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "understood_request": "yes",
                "confidence": 0.9,
                "execution_steps": [
                    {
                        "step_number": 1,
                        "service_id": "schedule_meeting",
                        "description": "Schedule a team meeting",
                        "required_params": {"time": "tomorrow"},
                        "optional_params": {}
                    },
                    {
                        "step_number": 2,
                        "service_id": "send_email",
                        "description": "Send agenda email",
                        "required_params": {"agenda": "meeting agenda"},
                        "optional_params": {}
                    }
                ],
                "missing_information": []
            })))]
        ))
        
        # Analyze complex request
        analyzed_ticket = await analyzer.analyze_request(ticket)
        assert len(analyzed_ticket.execution_plan) >= 2
        
        # Mock step executions
        agent.execute_service.side_effect = [
            {"success": True, "meeting_id": "123"},
            {"success": True, "email_sent": True}
        ]
        
        # Process with agent
        await agent.process_ticket(analyzed_ticket)
        
        # Verify execution
        assert agent.execute_service.call_count >= 2
        assert analyzed_ticket.status in [TicketStatus.COMPLETED, TicketStatus.EXECUTING]
        assert analyzed_ticket.execution_results

    async def test_auth_requirement_handling(self, service_analyzer, mock_agent, sample_tickets):
        """Test handling of services requiring authentication"""
        analyzer = await service_analyzer
        agent = await mock_agent
        ticket = sample_tickets["with_auth"]
        
        # Mock OpenAI response for auth requirement
        analyzer.openai.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "understood_request": "yes",
                "confidence": 0.9,
                "execution_steps": [
                    {
                        "step_number": 1,
                        "service_id": "google_auth",
                        "description": "Authenticate with Google",
                        "required_params": {},
                        "optional_params": {}
                    },
                    {
                        "step_number": 2,
                        "service_id": "check_calendar",
                        "description": "Check calendar conflicts",
                        "required_params": {"timeframe": "next week"},
                        "optional_params": {}
                    }
                ],
                "missing_information": []
            })))]
        ))
        
        # Analyze request
        analyzed_ticket = await analyzer.analyze_request(ticket)
        
        # Verify auth step inclusion
        auth_steps = [step for step in analyzed_ticket.execution_plan 
                     if step.get("service_id") == "google_auth"]
        assert auth_steps
        
        # Mock auth and service execution
        agent.execute_service.side_effect = [
            {"success": True, "credentials": "mock_creds"},
            {"success": True, "calendar_checked": True}
        ]
        
        # Process with agent
        await agent.process_ticket(analyzed_ticket)
        
        # Verify execution order
        calls = agent.execute_service.call_args_list
        assert len(calls) >= 2
        assert calls[0][0][0]["service_id"] == "google_auth"

    async def test_state_preservation(self, service_analyzer, mock_agent, sample_tickets):
        """Test state preservation through execution chain"""
        analyzer = await service_analyzer
        agent = await mock_agent
        ticket = sample_tickets["multi_step"]
        
        # Mock OpenAI response
        analyzer.openai.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "understood_request": "yes",
                "confidence": 0.9,
                "execution_steps": [
                    {
                        "step_number": 1,
                        "service_id": "schedule_meeting",
                        "description": "Schedule a team meeting",
                        "required_params": {"time": "tomorrow"},
                        "optional_params": {}
                    },
                    {
                        "step_number": 2,
                        "service_id": "send_email",
                        "description": "Send agenda email",
                        "required_params": {},
                        "optional_params": {}
                    }
                ],
                "missing_information": []
            })))]
        ))
        
        # Analyze request
        analyzed_ticket = await analyzer.analyze_request(ticket)
        
        # Mock stateful execution
        async def mock_execute_service(step):
            if step["service_id"] == "schedule_meeting":
                return {"success": True, "meeting_id": "123"}
            elif step["service_id"] == "send_email":
                return {"success": True, "email_sent": True}

        agent.execute_service.side_effect = mock_execute_service
        
        # Process with agent
        await agent.process_ticket(analyzed_ticket)
        
        # Verify state preservation
        assert len(analyzed_ticket.execution_results) >= 2
        assert analyzed_ticket.execution_results[0]["success"] is True
        assert analyzed_ticket.execution_results[1]["success"] is True

    async def test_error_propagation(self, service_analyzer, mock_agent, sample_tickets):
        """Test error handling and propagation through chain"""
        analyzer = await service_analyzer
        agent = await mock_agent
        ticket = sample_tickets["multi_step"]

        # Mock OpenAI response
        analyzer.openai.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "understood_request": "yes",
                "confidence": 0.9,
                "execution_steps": [
                    {
                        "step_number": 1,
                        "service_id": "schedule_meeting",
                        "description": "Schedule a team meeting",
                        "required_params": {"time": "tomorrow"},
                        "optional_params": {}
                    }
                ],
                "missing_information": []
            })))]
        ))

        # Analyze request
        analyzed_ticket = await analyzer.analyze_request(ticket)

        # Mock execution with error
        agent.execute_service.side_effect = Exception("Service execution failed")

        # Process with agent and expect error
        try:
            await agent.process_ticket(analyzed_ticket)
        except Exception as e:
            assert str(e) == "Service execution failed"
            assert analyzed_ticket.status == TicketStatus.ERROR
            assert len(analyzed_ticket.errors) == 1
            assert analyzed_ticket.errors[0]["message"] == "Service execution failed"
            assert analyzed_ticket.errors[0]["type"] == "execution_error"

    async def test_partial_completion(self, service_analyzer, mock_agent, sample_tickets):
        """Test handling of partial execution completion"""
        analyzer = await service_analyzer
        agent = await mock_agent
        ticket = sample_tickets["multi_step"]

        # Mock OpenAI response
        analyzer.openai.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "understood_request": "yes",
                "confidence": 0.9,
                "execution_steps": [
                    {
                        "step_number": 1,
                        "service_id": "schedule_meeting",
                        "description": "Schedule a team meeting",
                        "required_params": {"time": "tomorrow"},
                        "optional_params": {}
                    },
                    {
                        "step_number": 2,
                        "service_id": "send_email",
                        "description": "Send agenda email",
                        "required_params": {},
                        "optional_params": {}
                    }
                ],
                "missing_information": []
            })))]
        ))

        # Analyze request
        analyzed_ticket = await analyzer.analyze_request(ticket)

        # Mock partial completion
        agent.execute_service.side_effect = [
            {"success": True, "meeting_id": "123"},
            Exception("Email service unavailable")
        ]

        # Process with agent and expect error
        try:
            await agent.process_ticket(analyzed_ticket)
        except Exception as e:
            assert str(e) == "Email service unavailable"
            assert len(analyzed_ticket.execution_results) == 1
            assert analyzed_ticket.execution_results[0]["success"] is True
            assert analyzed_ticket.execution_results[0]["meeting_id"] == "123"

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 