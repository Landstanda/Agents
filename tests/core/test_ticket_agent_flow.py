import pytest
from typing import Dict, Any
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.models import Ticket, TicketStatus
from src.tools.service_analyzer import ServiceAnalyzer
from src.core.agent.base_agent import BaseAgent
from src.core.module_interface import ModuleResponse
from src.utils.flow_logger import FlowLogger

@pytest.fixture
def mock_service_index():
    """Mock service index for testing"""
    return {
        "calendar_service": {
            "name": "Calendar Service",
            "description": "Manages calendar operations",
            "examples": ["Schedule a meeting with John tomorrow at 3 PM"],
            "required_entities": ["time", "date", "attendees"],
            "optional_entities": ["location", "duration"],
            "outputs": ["calendar_event_id"]
        }
    }

@pytest.fixture
def mock_gpt_response():
    """Mock GPT response for service analysis"""
    return {
        "understood_request": "Schedule a meeting with John tomorrow at 3 PM",
        "confidence": 0.95,
        "execution_steps": [
            {
                "step_number": 1,
                "service_id": "calendar_service",
                "description": "Create calendar event",
                "required_params": {
                    "time": "3 PM",
                    "date": "tomorrow",
                    "attendees": ["John"]
                },
                "optional_params": {}
            }
        ],
        "missing_information": []
    }

@pytest.fixture
def mock_openai(mock_gpt_response):
    """Mock OpenAI client with async support"""
    class AsyncMockChat:
        async def create(self, *args, **kwargs):
            return type('Response', (), {
                'choices': [
                    type('Choice', (), {
                        'message': type('Message', (), {
                            'content': json.dumps(mock_gpt_response)
                        })()
                    })()
                ]
            })
            
    mock_client = MagicMock()
    mock_client.chat.completions = AsyncMockChat()
    return mock_client

@pytest.fixture
def service_analyzer(mock_openai, tmp_path):
    """Create ServiceAnalyzer with mocked dependencies"""
    # Create temporary service index file
    service_index = tmp_path / "service_index.json"
    service_index.write_text(json.dumps({"version": "1.0", "services": {}}))
    
    analyzer = ServiceAnalyzer(services_path=str(service_index))
    analyzer.openai = mock_openai
    
    # Add helper method to handle status transitions
    def analyze_with_transitions(ticket):
        ticket.update_status(TicketStatus.ANALYZING)
        result = analyzer.analyze_request(ticket)
        return result
        
    analyzer.analyze_with_transitions = analyze_with_transitions
    return analyzer

@pytest.fixture
def base_agent():
    """Create BaseAgent with mocked dependencies"""
    agent = BaseAgent()
    agent.service_registry = MagicMock()
    agent.tool_registry = MagicMock()
    
    # Create async executor mock
    executor = MagicMock()
    async def execute_service(service_def, ticket):
        if not service_def:
            return {
                "status": "error",
                "error": "Service not found",
                "error_type": "service_error"
            }
        return {
            "status": "completed",
            "results": [{"success": True, "calendar_event_id": "evt_123"}]
        }
    executor.execute_service = execute_service
    agent.executor = executor
    agent._initialized = True
    return agent

class TestTicketAgentFlow:
    @pytest.fixture
    def user_info(self):
        """Basic user info for ticket creation"""
        return {
            "user_id": "U123",
            "channel_id": "C456",
            "thread_ts": "1234567890.123",
            "username": "test_user"
        }
        
    @pytest.mark.asyncio
    async def test_basic_successful_flow(self, service_analyzer, base_agent, user_info):
        """Test successful flow from ticket creation through execution"""
        # Create initial ticket
        ticket = Ticket(
            user_info=user_info,
            original_message="Schedule a meeting with John tomorrow at 3 PM"
        )
        assert ticket.status == TicketStatus.CREATED
        
        # Service analysis phase
        analyzed_ticket = await service_analyzer.analyze_with_transitions(ticket)
        assert analyzed_ticket.status == TicketStatus.EXECUTING
        assert analyzed_ticket.service == "calendar_service"
        assert "time" in analyzed_ticket.entities
        assert "date" in analyzed_ticket.entities
        assert "attendees" in analyzed_ticket.entities
        
        # Mock successful service execution
        class AsyncSuccessExecutor:
            async def execute_service(self, service_def, ticket):
                return {
                    "status": "completed",
                    "results": [{"success": True, "calendar_event_id": "evt_123"}]
                }
        base_agent.executor = AsyncSuccessExecutor()
        
        # Agent execution phase
        await base_agent.process_ticket(analyzed_ticket)
        assert analyzed_ticket.status == TicketStatus.COMPLETED
        assert len(analyzed_ticket.execution_results) > 0
        assert analyzed_ticket.execution_results[-1]["status"] == "completed"
        
    @pytest.mark.asyncio
    async def test_flow_with_missing_information(self, service_analyzer, base_agent, user_info):
        """Test flow when service analyzer detects missing information"""
        # Create mock response with missing information
        missing_info_response = {
            "understood_request": "Schedule a meeting with John",
            "confidence": 0.8,
            "execution_steps": [
                {
                    "step_number": 1,
                    "service_id": "calendar_service",
                    "description": "Create calendar event",
                    "required_params": {
                        "attendees": ["John"]
                    },
                    "optional_params": {}
                }
            ],
            "missing_information": [
                {
                    "param": "time",
                    "service": "calendar_service",
                    "description": "What time should the meeting be scheduled for?",
                    "step_number": 1
                },
                {
                    "param": "date",
                    "service": "calendar_service",
                    "description": "What date should the meeting be scheduled for?",
                    "step_number": 1
                }
            ]
        }
        
        # Create async mock for this test
        class AsyncMockChat:
            async def create(self, *args, **kwargs):
                return type('Response', (), {
                    'choices': [
                        type('Choice', (), {
                            'message': type('Message', (), {
                                'content': json.dumps(missing_info_response)
                            })()
                        })()
                    ]
                })
                
        service_analyzer.openai.chat.completions = AsyncMockChat()
        
        # Create initial ticket
        ticket = Ticket(
            user_info=user_info,
            original_message="Schedule a meeting with John"
        )
        
        # Service analysis phase
        analyzed_ticket = await service_analyzer.analyze_with_transitions(ticket)
        assert analyzed_ticket.status == TicketStatus.WAITING_INPUT
        assert "time" in analyzed_ticket.missing_entities
        assert "date" in analyzed_ticket.missing_entities
        
    @pytest.mark.asyncio
    async def test_flow_with_execution_error(self, service_analyzer, base_agent, user_info):
        """Test flow when service execution fails"""
        # Create and analyze ticket
        ticket = Ticket(
            user_info=user_info,
            original_message="Schedule a meeting with John tomorrow at 3 PM"
        )
        analyzed_ticket = await service_analyzer.analyze_request(ticket)
        
        # Mock failed service execution
        class AsyncErrorExecutor:
            async def execute_service(self, service_def, ticket):
                return {
                    "status": "error",
                    "error": "Failed to create calendar event",
                    "error_type": "api_error"
                }
            
        base_agent.executor = AsyncErrorExecutor()
        
        # Agent execution phase
        await base_agent.process_ticket(analyzed_ticket)
        assert analyzed_ticket.status == TicketStatus.ERROR
        assert len(analyzed_ticket.error_history) > 0
        assert "Failed to create calendar event" in analyzed_ticket.error_history[-1]["message"]
        
    @pytest.mark.asyncio
    async def test_flow_with_invalid_service(self, service_analyzer, base_agent, user_info):
        """Test flow when service analyzer suggests an invalid service"""
        # Create mock response with invalid service
        invalid_service_response = {
            "understood_request": "Schedule a meeting",
            "confidence": 0.9,
            "execution_steps": [
                {
                    "step_number": 1,
                    "service_id": "nonexistent_service",
                    "description": "Create calendar event",
                    "required_params": {},
                    "optional_params": {}
                }
            ],
            "missing_information": []
        }
        
        # Override the mock response for this test
        service_analyzer.openai.chat.completions.create = MagicMock(
            return_value=type('Response', (), {
                'choices': [
                    type('Choice', (), {
                        'message': type('Message', (), {
                            'content': json.dumps(invalid_service_response)
                        })()
                    })()
                ]
            })()
        )
        
        # Create and analyze ticket
        ticket = Ticket(
            user_info=user_info,
            original_message="Schedule a meeting"
        )
        analyzed_ticket = await service_analyzer.analyze_request(ticket)
        
        # Mock service registry to return None for invalid service
        base_agent.service_registry.get_item.return_value = None
        
        # Agent execution phase
        await base_agent.process_ticket(analyzed_ticket)
        assert analyzed_ticket.status == TicketStatus.ERROR
        assert any("not found" in error["message"] for error in analyzed_ticket.error_history)
        
    @pytest.mark.asyncio
    async def test_flow_state_transitions(self, service_analyzer, base_agent, user_info):
        """Test state transitions throughout the flow"""
        # Create initial ticket
        ticket = Ticket(
            user_info=user_info,
            original_message="Schedule a meeting with John tomorrow at 3 PM"
        )
        assert ticket.status == TicketStatus.CREATED
        assert len(ticket.status_history) == 1
        
        # Service analysis phase
        analyzed_ticket = await service_analyzer.analyze_with_transitions(ticket)
        assert analyzed_ticket.status == TicketStatus.EXECUTING
        assert len(analyzed_ticket.status_history) == 3  # CREATED -> ANALYZING -> EXECUTING
        
        # Mock successful execution
        class AsyncSuccessExecutor:
            async def execute_service(self, service_def, ticket):
                return {
                    "status": "completed",
                    "results": [{"success": True}]
                }
        base_agent.executor = AsyncSuccessExecutor()
        
        # Agent execution phase
        await base_agent.process_ticket(analyzed_ticket)
        assert analyzed_ticket.status == TicketStatus.COMPLETED
        assert len(analyzed_ticket.status_history) == 4  # Added COMPLETED
        
        # Verify status transition order
        status_sequence = [entry["status"] for entry in analyzed_ticket.status_history]
        assert status_sequence == [
            TicketStatus.CREATED,
            TicketStatus.ANALYZING,
            TicketStatus.EXECUTING,
            TicketStatus.COMPLETED
        ]

if __name__ == "__main__":
    pytest.main(["-v", "test_ticket_agent_flow.py"]) 