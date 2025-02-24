import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json
from datetime import datetime

from src.models import Ticket, TicketStatus
from src.tools.service_analyzer import ServiceAnalyzer
from src.tools.message_maker import MessageMaker
from src.core.agent.base_agent import BaseAgent

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
    """Mock OpenAI client with responses for both service analyzer and message maker"""
    class AsyncMockChat:
        async def create(self, *args, **kwargs):
            # Extract the prompt from kwargs
            messages = kwargs.get('messages', [])
            system_prompt = next((msg['content'] for msg in messages if msg['role'] == 'system'), '')
            user_prompt = next((msg['content'] for msg in messages if msg['role'] == 'user'), '')
            
            # If this is a service analyzer request (looking for JSON)
            if "execution_steps" in system_prompt or "execution_steps" in user_prompt:
                response_content = json.dumps(mock_gpt_response)
            else:
                # This is a message maker request
                if 'error' in user_prompt.lower():
                    response_content = "I apologize, but there was an issue with your request. The operation failed due to a technical error. Please try again or contact support if the issue persists."
                elif 'missing information' in user_prompt.lower():
                    response_content = "I need some additional information to proceed with your request. Could you please provide the missing details so I can help you better?"
                elif 'new service' in user_prompt.lower() or 'workflow' in user_prompt.lower():
                    response_content = "I've created a new workflow service to handle your request. This service is designed to automate the process efficiently. You can now use this service for similar requests in the future."
                else:
                    response_content = "I've successfully processed your request. The operation has been completed as specified."
            
            return type('Response', (), {
                'choices': [
                    type('Choice', (), {
                        'message': type('Message', (), {
                            'content': response_content
                        })()
                    })
                ]
            })
    
    mock_client = MagicMock()
    mock_client.chat.completions = AsyncMockChat()
    return mock_client

@pytest.fixture
def mock_slack():
    """Mock Slack client"""
    class AsyncMockSlack:
        async def chat_postMessage(self, *args, **kwargs):
            return {"ok": True, "ts": "1234567890.123456"}
    
    return AsyncMockSlack()

@pytest.fixture
def service_analyzer(mock_openai, tmp_path):
    """Create ServiceAnalyzer with mocked dependencies"""
    service_index = tmp_path / "service_index.json"
    service_index.write_text(json.dumps({"version": "1.0", "services": {}}))
    
    analyzer = ServiceAnalyzer(services_path=str(service_index))
    analyzer.openai = mock_openai
    return analyzer

@pytest.fixture
def message_maker(mock_openai, mock_slack):
    """Create MessageMaker with mocked dependencies"""
    return MessageMaker(use_mock=True, mock_openai=mock_openai, mock_slack=mock_slack)

@pytest.fixture
def base_agent():
    """Create BaseAgent with mocked dependencies"""
    agent = BaseAgent()
    agent.service_registry = MagicMock()
    agent.tool_registry = MagicMock()
    
    executor = MagicMock()
    async def execute_service(service_def, ticket):
        return {
            "status": "completed",
            "results": [{"success": True, "calendar_event_id": "evt_123"}]
        }
    executor.execute_service = execute_service
    agent.executor = executor
    agent._initialized = True
    return agent

class TestMessageFlow:
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
    async def test_successful_message_flow(self, service_analyzer, base_agent, message_maker, user_info):
        """Test complete successful message flow from user input to response"""
        # Create initial ticket
        ticket = Ticket(
            user_info=user_info,
            original_message="Schedule a meeting with John tomorrow at 3 PM"
        )
        assert ticket.status == TicketStatus.CREATED

        # Service analysis phase
        await service_analyzer.analyze_request(ticket)
        assert ticket.status == TicketStatus.EXECUTING
        assert ticket.service == "calendar_service"
        assert len(ticket.entities) > 0

        # Agent execution phase
        await base_agent.process_ticket(ticket)
        assert ticket.status == TicketStatus.COMPLETED
        assert len(ticket.execution_results) > 0

        # Message generation and sending phase
        await message_maker.send_message(ticket)
        assert len(ticket.outgoing_messages) > 0
        assert ticket.final_response is not None

    @pytest.mark.asyncio
    async def test_flow_with_missing_information(self, service_analyzer, base_agent, message_maker, user_info, mock_openai):
        """Test flow when missing information is detected"""
        # Modify mock GPT response to indicate missing information
        missing_info_response = {
            "understood_request": "Schedule a meeting with John",
            "confidence": 0.8,
            "execution_steps": [
                {
                    "step_number": 1,
                    "service_id": "calendar_service",
                    "description": "Create calendar event",
                    "required_params": {"attendees": ["John"]},
                    "optional_params": {}
                }
            ],
            "missing_information": [
                {
                    "param": "time",
                    "description": "What time should the meeting be scheduled for?",
                    "step_number": 1
                }
            ]
        }

        class ModifiedAsyncMockChat:
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

        service_analyzer.openai.chat.completions = ModifiedAsyncMockChat()

        # Create ticket and process
        ticket = Ticket(
            user_info=user_info,
            original_message="Schedule a meeting with John"
        )

        await service_analyzer.analyze_request(ticket)
        assert ticket.status == TicketStatus.WAITING_INPUT
        assert "time" in ticket.missing_entities

        # Generate message requesting missing information
        await message_maker.send_message(ticket)
        assert len(ticket.outgoing_messages) > 0
        assert any("time" in msg.content.lower() for msg in ticket.outgoing_messages)

    @pytest.mark.asyncio
    async def test_flow_with_execution_error(self, service_analyzer, base_agent, message_maker, user_info):
        """Test flow when service execution fails"""
        # Create ticket
        ticket = Ticket(
            user_info=user_info,
            original_message="Schedule a meeting with John tomorrow at 3 PM"
        )

        # Service analysis phase
        await service_analyzer.analyze_request(ticket)

        # Modify agent to simulate execution error
        async def mock_execute_error(service_def, ticket):
            return {
                "status": "error",
                "error": "Failed to create calendar event",
                "error_type": "api_error"
            }
        base_agent.executor.execute_service = mock_execute_error

        # Agent execution phase
        await base_agent.process_ticket(ticket)
        assert ticket.status == TicketStatus.ERROR
        assert len(ticket.error_history) > 0

        # Message generation for error
        await message_maker.send_message(ticket)
        assert len(ticket.outgoing_messages) > 0
        assert any("failed" in msg.content.lower() for msg in ticket.outgoing_messages)

    @pytest.mark.asyncio
    async def test_flow_with_service_creation(self, service_analyzer, base_agent, message_maker, user_info):
        """Test flow when a new service needs to be created"""
        # Create ticket with request requiring service creation
        ticket = Ticket(
            user_info=user_info,
            original_message="Create a new workflow to handle expense reports"
        )
        ticket.update_status(TicketStatus.SERVICE_CREATION)
        ticket.created_services.append({
            "name": "expense_workflow",
            "definition": {
                "name": "Expense Report Workflow",
                "steps": ["validate_report", "approve_expenses", "process_payment"]
            }
        })

        # Message generation for service creation
        await message_maker.send_message(ticket)
        assert len(ticket.outgoing_messages) > 0
        assert any("workflow" in msg.content.lower() for msg in ticket.outgoing_messages)

    @pytest.mark.asyncio
    async def test_conversation_threading(self, service_analyzer, base_agent, message_maker, user_info):
        """Test conversation threading through the message flow"""
        # Create initial ticket with thread
        ticket = Ticket(
            user_info=user_info,
            original_message="Schedule a meeting with John tomorrow at 3 PM"
        )

        # Process through all phases
        await service_analyzer.analyze_request(ticket)
        await base_agent.process_ticket(ticket)
        await message_maker.send_message(ticket)

        # Add user response in same thread
        ticket.add_incoming_message("Can we make it 4 PM instead?")
        ticket.update_status(TicketStatus.ANALYZING)

        # Process response
        await service_analyzer.analyze_request(ticket)
        await base_agent.process_ticket(ticket)
        await message_maker.send_message(ticket)

        # Verify conversation threading
        assert len(ticket.conversation_history) >= 4  # Initial request, response, follow-up, final response
        assert all(msg.get("thread_ts") == ticket.thread_ts for msg in ticket.conversation_history)

    @pytest.mark.asyncio
    async def test_status_updates_in_flow(self, service_analyzer, base_agent, message_maker, user_info):
        """Test status updates throughout the message flow"""
        ticket = Ticket(
            user_info=user_info,
            original_message="Schedule a meeting with John tomorrow at 3 PM"
        )

        # Track status changes
        status_changes = []
        status_changes.append(ticket.status)

        # Analysis phase
        await service_analyzer.analyze_request(ticket)
        status_changes.append(ticket.status)

        # Execution phase
        await base_agent.process_ticket(ticket)
        status_changes.append(ticket.status)

        # Message phase
        await message_maker.send_message(ticket)
        status_changes.append(ticket.status)

        # Verify status progression
        assert TicketStatus.CREATED in status_changes
        assert TicketStatus.ANALYZING in status_changes or TicketStatus.EXECUTING in status_changes
        assert TicketStatus.COMPLETED in status_changes
        assert len(status_changes) >= 3  # At least 3 status changes should occur 