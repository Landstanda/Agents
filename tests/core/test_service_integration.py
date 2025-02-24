import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
import yaml
from pathlib import Path
from src.models import Ticket, TicketStatus
from src.tools.service_analyzer import ServiceAnalyzer
from src.core.agent.service_agent import ServiceAgent
from src.utils.flow_logger import FlowLogger
from src.core.registry.service_registry import ServiceRegistry
from src.core.registry.tool_registry import ToolRegistry
from src.core.agent.executor import ServiceExecutor

@pytest.fixture
def test_services_file(tmp_path):
    """Create a temporary test services file"""
    services = {
        "calendar_service": {
            "name": "calendar_service",
            "description": "Calendar service for testing",
            "steps": [
                {
                    "name": "create_event",
                    "tool": "calendar_tool",
                    "action": "create",
                    "params": {
                        "title": "Test Event",
                        "start_time": "2024-03-20T14:00:00"
                    }
                }
            ]
        },
        "task_service": {
            "name": "task_service",
            "description": "Task service for testing",
            "steps": [
                {
                    "name": "create_task",
                    "tool": "task_tool",
                    "action": "create",
                    "params": {
                        "title": "Test Task",
                        "description": "Test task description"
                    }
                }
            ]
        }
    }
    
    services_file = tmp_path / "test_services.yaml"
    with open(services_file, "w") as f:
        yaml.safe_dump(services, f)
    
    return services_file

@pytest.fixture
def flow_logger():
    """Create a flow logger for testing"""
    logger = AsyncMock(spec=FlowLogger)
    logger.log_event = AsyncMock()
    logger.error = AsyncMock()
    logger.info = AsyncMock()
    return logger

@pytest.fixture
def service_analyzer(flow_logger):
    """Create a service analyzer with test configuration"""
    analyzer = ServiceAnalyzer(flow_logger=flow_logger)
    return analyzer

@pytest.fixture
async def service_agent():
    """Create a service agent for testing"""
    # Create mock registries
    service_registry = AsyncMock(spec=ServiceRegistry)
    tool_registry = AsyncMock(spec=ToolRegistry)
    service_executor = AsyncMock(spec=ServiceExecutor)
    
    # Configure service registry mock
    service_registry.get_item.return_value = {
        "name": "Schedule Meeting",
        "description": "Schedule an event in the calendar.",
        "required_entities": ["time", "date"],
        "optional_entities": ["location", "participants", "duration", "description"]
    }
    
    # Configure executor mock
    service_executor.execute_service.return_value = {
        "status": "success",
        "result": {
            "event_id": "123",
            "event_link": "https://calendar.com/event/123"
        }
    }
    
    # Create agent with mocked components
    agent = ServiceAgent()
    agent.service_registry = service_registry
    agent.tool_registry = tool_registry
    agent.executor = service_executor
    await agent.initialize()
    return agent

@pytest.mark.asyncio
async def test_request_analysis_to_execution_flow(service_analyzer, service_agent, flow_logger):
    """Test the complete flow from request analysis to service execution"""
    # Create a test ticket
    ticket = Ticket(
        original_message="Schedule a team meeting for tomorrow at 2pm",
        user_info={"user_id": "U123", "channel_id": "C456"},
        channel_id="C456"
    )
    
    # Configure analyzer response
    with patch('src.tools.service_analyzer.AsyncOpenAI') as mock_openai:
        # Mock the chat completion response
        mock_completion = AsyncMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content=json.dumps({
                "understood_request": "Schedule a team meeting for tomorrow at 2pm",
                "confidence": 0.95,
                "execution_steps": [
                    {
                        "step_number": 1,
                        "service_id": "schedule_meeting",
                        "description": "Create calendar event",
                        "required_params": {
                            "time": "2:00 PM",
                            "date": "tomorrow"
                        },
                        "optional_params": {
                            "participants": "team"
                        }
                    }
                ],
                "missing_information": []
            })))
        ]
        mock_openai.return_value.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        
        # Analyze the request
        analyzed_ticket = await service_analyzer.analyze_request(ticket)
        
    # Verify analysis results
    assert analyzed_ticket.status == TicketStatus.EXECUTING
    assert len(analyzed_ticket.execution_plan) == 1
    assert analyzed_ticket.service == "schedule_meeting"
    
    # Execute the service
    agent = await service_agent
    result = await agent.executor.execute_service("schedule_meeting", analyzed_ticket)
    
    # Verify execution results
    assert result["status"] == "success"
    assert result["result"]["event_id"] == "123"
    assert agent.executor.execute_service.call_count == 1

@pytest.mark.asyncio
async def test_error_handling_in_analysis_flow(service_analyzer, service_agent, flow_logger):
    """Test error handling during request analysis"""
    # Create a test ticket
    ticket = Ticket(
        original_message="Invalid request that should fail",
        user_info={"user_id": "U123", "channel_id": "C456"},
        channel_id="C456"
    )

    # Configure analyzer to raise an error
    with patch('src.tools.service_analyzer.AsyncOpenAI') as mock_openai:
        error_msg = "Failed to parse request"
        mock_openai.return_value.chat.completions.create = AsyncMock(
            side_effect=ValueError(error_msg)
        )

        # Analyze the request
        analyzed_ticket = await service_analyzer.analyze_request(ticket)

    # Verify error handling
    assert analyzed_ticket.status == TicketStatus.ERROR
    assert len(analyzed_ticket.errors) > 0
    assert any(error_msg in error["message"] for error in analyzed_ticket.errors)
    assert flow_logger.error.call_count >= 1
    
    # Verify no execution attempted
    with patch('src.core.agent.service_agent.ServiceExecutor') as mock_executor:
        executor_instance = MagicMock()
        executor_instance.execute_service = AsyncMock(return_value={"status": "error"})
        mock_executor.return_value = executor_instance
        
        # Initialize agent
        await service_agent.initialize()
        
        # Execute service
        result = await service_agent.execute_service("test_service", analyzed_ticket)
    
    assert result["status"] == "error"
    assert analyzed_ticket.status == TicketStatus.ERROR

@pytest.mark.asyncio
async def test_missing_information_handling(service_analyzer, service_agent, flow_logger):
    """Test handling of missing information in the request"""
    # Create a test ticket
    ticket = Ticket(
        original_message="Schedule a team meeting",
        user_info={"user_id": "U123", "channel_id": "C456"},
        channel_id="C456"
    )
    
    # Configure analyzer response
    with patch('src.tools.service_analyzer.AsyncOpenAI') as mock_openai:
        mock_completion = AsyncMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content=json.dumps({
                "understood_request": "Schedule a team meeting",
                "confidence": 0.95,
                "execution_steps": [
                    {
                        "step_number": 1,
                        "service_id": "schedule_meeting",
                        "description": "Schedule a team meeting",
                        "required_params": {
                            "time": None,
                            "date": None
                        },
                        "optional_params": {
                            "participants": "team",
                            "description": "Team meeting"
                        }
                    }
                ],
                "missing_information": [
                    {
                        "param": "time",
                        "service": "schedule_meeting",
                        "description": "Need meeting time",
                        "step_number": 1
                    },
                    {
                        "param": "date",
                        "service": "schedule_meeting",
                        "description": "Need meeting date",
                        "step_number": 1
                    }
                ]
            })))
        ]
        mock_openai.return_value.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        
        # Analyze the request
        analyzed_ticket = await service_analyzer.analyze_request(ticket)
    
    # Verify handling of missing information
    assert analyzed_ticket.status == TicketStatus.WAITING_INPUT
    assert "time" in analyzed_ticket.missing_entities
    assert "date" in analyzed_ticket.missing_entities
    assert len(analyzed_ticket.missing_entities) == 2

@pytest.fixture
def mock_openai_response():
    return {
        "understood_request": "Schedule a meeting with John tomorrow at 3pm",
        "identified_service": "calendar_scheduling",
        "required_entities": {
            "attendee": "John",
            "date": "tomorrow",
            "time": "3pm"
        },
        "steps": [
            {
                "name": "validate_calendar_access",
                "tool": "calendar_tool",
                "action": "check_access"
            },
            {
                "name": "create_calendar_event",
                "tool": "calendar_tool",
                "action": "create_event",
                "params": {
                    "attendee": "{attendee}",
                    "date": "{date}",
                    "time": "{time}"
                }
            }
        ]
    }

@pytest.fixture
def mock_service_registry():
    registry = AsyncMock(spec=ServiceRegistry)
    registry.get_item.return_value = {
        "name": "Calendar Scheduling",
        "steps": [
            {
                "name": "validate_calendar_access",
                "tool": "calendar_tool",
                "action": "check_access"
            },
            {
                "name": "create_calendar_event",
                "tool": "calendar_tool",
                "action": "create_event"
            }
        ]
    }
    return registry

@pytest.fixture
def mock_tool_registry():
    registry = AsyncMock(spec=ToolRegistry)
    
    # Mock calendar tool
    calendar_tool = AsyncMock()
    calendar_tool.execute = AsyncMock(return_value={"status": "success"})
    
    registry.get_item.return_value = calendar_tool
    return registry

@pytest.mark.asyncio
async def test_complete_request_flow(
    service_analyzer,
    service_agent,
    mock_openai_response,
    flow_logger
):
    """Test complete flow from message analysis to execution"""
    # Create initial ticket
    ticket = Ticket(
        original_message="Schedule a meeting with John tomorrow at 3pm",
        user_info={"user_id": "U123", "channel_id": "C456"},
        channel_id="C456"
    )
    
    # Mock OpenAI for service analysis
    with patch('src.tools.service_analyzer.AsyncOpenAI') as mock_openai:
        mock_completion = AsyncMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content=json.dumps(mock_openai_response)))
        ]
        mock_openai.return_value.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        
        # Step 1: Analyze request
        ticket = await service_analyzer.analyze_request(ticket)
        
        # Verify analysis results
        assert ticket.status == TicketStatus.EXECUTING
        assert ticket.service == "calendar_scheduling"
        assert len(ticket.steps) == 2
        
        # Step 2: Execute service
        result = await service_agent.execute_service(ticket.service, ticket)
        
        # Verify execution results
        assert result["status"] == "success"
        assert ticket.status == TicketStatus.COMPLETED
        
        # Verify flow logger was called appropriately
        flow_logger.log_event.assert_called()

@pytest.mark.asyncio
async def test_error_handling_flow(
    service_analyzer,
    service_agent,
    mock_openai_response,
    flow_logger
):
    """Test error handling in the complete flow"""
    # Create initial ticket
    ticket = Ticket(
        original_message="Schedule a meeting with John tomorrow at 3pm",
        user_info={"user_id": "U123", "channel_id": "C456"},
        channel_id="C456"
    )
    
    # Mock OpenAI for service analysis
    with patch('src.tools.service_analyzer.AsyncOpenAI') as mock_openai:
        mock_completion = AsyncMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content=json.dumps(mock_openai_response)))
        ]
        mock_openai.return_value.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )
        
        # Step 1: Analyze request
        ticket = await service_analyzer.analyze_request(ticket)
        
        # Make execution fail
        service_agent.executor.execute_service.side_effect = Exception("Calendar API error")
        
        # Step 2: Execute service
        result = await service_agent.execute_service(ticket.service, ticket)
        
        # Verify error handling
        assert result["status"] == "error"
        assert ticket.status == TicketStatus.ERROR
        assert len(ticket.errors) > 0
        assert "Calendar API error" in str(ticket.errors[0]["error"])
        
        # Verify flow logger captured error
        flow_logger.log_event.assert_called_with(
            "ServiceAgent",
            "service_execution_error",
            {
                "service": ticket.service,
                "ticket_id": ticket.ticket_id,
                "error": "Calendar API error"
            }
        ) 