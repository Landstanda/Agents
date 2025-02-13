import pytest
from pathlib import Path
import yaml
import json
from datetime import datetime
from src.tools.nlp import NLPAnalyzer, Ticket, TicketStatus
from src.tools.agent import Agent
from src.tools.service_maker import ServiceMaker
from src.tools.message_maker import MessageMaker
from src.utils.flow_logger import FlowLogger

@pytest.fixture
def mock_environment(tmp_path):
    # Create directory structure
    services_dir = tmp_path / "src" / "services"
    tools_dir = tmp_path / "src" / "tools"
    services_dir.mkdir(parents=True)
    tools_dir.mkdir(parents=True)
    
    # Create services.yaml
    services_path = services_dir / "services.yaml"
    services_path.write_text("""
schedule_meeting:
  name: Schedule Meeting
  description: Schedule a meeting with specified participants
  intent: schedule_meeting
  triggers:
    - schedule a meeting
    - set up a meeting
    - book a meeting
  required_entities:
    - time
    - date
    - participants
  optional_entities:
    - location
    """)
    
    # Create executions.yaml
    executions_path = services_dir / "executions.yaml"
    executions_path.write_text("""
schedule_meeting:
  executor_type: "calendar"
  steps:
    - name: "validate_time"
      tool: "calendar"
      action: "check_availability"
      params:
        time: "{time}"
        date: "{date}"

    - name: "create_event"
      tool: "calendar"
      action: "create_event"
      params:
        summary: "Meeting with {participants}"
        time: "{time}"
        date: "{date}"
        attendees: "{participants}"
        location: "{location}"

  response_templates:
    success: "Meeting scheduled for {date} at {time}"
    error: "Failed to schedule meeting: {error_message}"
    """)
    
    # Create mock calendar tool
    calendar_path = tools_dir / "calendar.py"
    calendar_path.write_text("""
class CalendarTool:
    def __init__(self, flow_logger=None):
        self.flow_logger = flow_logger
        self.calls = []

    async def check_availability(self, time: str, date: str):
        self.calls.append({"action": "check_availability", "params": {"time": time, "date": date}})
        return {"available": True}

    async def create_event(self, summary: str, time: str, date: str, attendees: list, location: str = None):
        self.calls.append({
            "action": "create_event",
            "params": {
                "summary": summary,
                "time": time,
                "date": date,
                "attendees": attendees,
                "location": location
            }
        })
        return {"event_id": "test_123", "success": True}
    """)
    
    # Create __init__.py
    (tools_dir / "__init__.py").touch()
    
    return tmp_path

@pytest.mark.asyncio
async def test_ticket_creation_and_basic_flow(mock_environment):
    """Test the basic flow of creating and updating a ticket."""
    # Create components
    analyzer = await NLPAnalyzer.create(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        flow_logger=FlowLogger()
    )
    
    # Test initial message analysis
    message = "schedule a meeting tomorrow at 2pm with John and Alice in Conference Room A"
    user_info = {"user_id": "test_user", "channel_id": "test_channel"}
    
    ticket = await analyzer.analyze_message(message, user_info)
    
    # Verify ticket creation and initial state
    assert ticket.original_message == message
    assert ticket.status == TicketStatus.EXECUTING
    assert ticket.service == "schedule_meeting"
    assert ticket.intent == "schedule_meeting"
    assert len(ticket.messages) == 1
    assert ticket.messages[0]["source"] == "user"
    
    # Verify entity extraction
    assert ticket.entities["time"] == "14:00"
    assert "tomorrow" in ticket.entities["date"]
    assert len(ticket.entities["participants"]) == 2
    assert "Conference Room A" in ticket.entities["location"]

@pytest.mark.asyncio
async def test_ticket_missing_entities(mock_environment):
    """Test handling of missing required entities."""
    analyzer = await NLPAnalyzer.create(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        flow_logger=FlowLogger()
    )
    
    message = "schedule a meeting"
    user_info = {"user_id": "test_user", "channel_id": "test_channel"}
    
    ticket = await analyzer.analyze_message(message, user_info)
    
    assert ticket.status == TicketStatus.WAITING_INPUT
    assert "time" in ticket.missing_entities
    assert "date" in ticket.missing_entities
    assert "participants" in ticket.missing_entities

@pytest.mark.asyncio
async def test_ticket_service_execution(mock_environment):
    """Test executing a service with a ticket."""
    analyzer = await NLPAnalyzer.create(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        flow_logger=FlowLogger()
    )
    
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    message = "schedule a meeting tomorrow at 2pm with John and Alice in Conference Room A"
    user_info = {"user_id": "test_user", "channel_id": "test_channel"}
    
    # Analyze message
    ticket = await analyzer.analyze_message(message, user_info)
    assert ticket.status == TicketStatus.EXECUTING
    
    # Execute service
    result = await agent.execute_service(ticket)
    
    # Verify execution results
    assert result["status"] == "success"
    assert len(ticket.steps_executed) == 2
    assert ticket.steps_executed[0]["action"] == "check_availability"
    assert ticket.steps_executed[1]["action"] == "create_event"

@pytest.mark.asyncio
async def test_ticket_service_creation(mock_environment):
    """Test creating a new service for an unknown request."""
    analyzer = await NLPAnalyzer.create(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        flow_logger=FlowLogger()
    )
    
    service_maker = ServiceMaker(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        tools_path=str(mock_environment / "src" / "tools")
    )
    
    message = "remind me to take a break every hour"
    user_info = {"user_id": "test_user", "channel_id": "test_channel"}
    
    # Analyze message
    ticket = await analyzer.analyze_message(message, user_info)
    assert ticket.status == TicketStatus.SERVICE_CREATION
    
    # Create service
    ticket = await service_maker.create_service(ticket)
    
    # Verify service creation
    assert len(ticket.created_services) == 1
    created_service = ticket.created_services[0]
    assert "remind" in created_service["name"].lower()
    assert "break" in created_service["description"].lower()
    assert len(created_service["steps"]) > 0

@pytest.mark.asyncio
async def test_ticket_message_generation(mock_environment, monkeypatch):
    """Test generating messages based on ticket state."""
    # Mock Slack and OpenAI clients
    class MockSlack:
        async def chat_postMessage(self, channel, text, thread_ts=None):
            return {"ok": True, "ts": "test_ts"}
    
    class MockOpenAI:
        def __init__(self):
            class Chat:
                def __init__(self):
                    class Completions:
                        async def create(self, model, messages, temperature, max_tokens):
                            class MockResponse:
                                def __init__(self):
                                    class Choice:
                                        def __init__(self):
                                            class Message:
                                                def __init__(self):
                                                    self.content = "I've scheduled your meeting for tomorrow at 2 PM with John and Alice in Conference Room A."
                                            self.message = Message()
                                    self.choices = [Choice()]
                            return MockResponse()
                    self.completions = Completions()
                async def create(self, model, messages, temperature, max_tokens):
                    return await self.completions.create(model, messages, temperature, max_tokens)
            self.chat = Chat()
    
    # Create and initialize components
    analyzer = await NLPAnalyzer.create(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        flow_logger=FlowLogger()
    )
    
    message_maker = MessageMaker()
    message_maker.slack = MockSlack()
    message_maker.openai = MockOpenAI()
    
    # Test message flow
    message = "schedule a meeting tomorrow at 2pm with John and Alice in Conference Room A"
    user_info = {"user_id": "test_user", "channel_id": "test_channel"}
    
    # Create and process ticket
    ticket = await analyzer.analyze_message(message, user_info)
    ticket.channel_id = "test_channel"
    
    # Generate response
    await message_maker.send_message(ticket)
    
    # Verify message history
    assert len(ticket.messages) == 2
    assert ticket.messages[0]["source"] == "user"
    assert ticket.messages[1]["source"] == "assistant"
    assert "scheduled" in ticket.messages[1]["message"].lower()

@pytest.mark.asyncio
async def test_ticket_error_handling(mock_environment):
    """Test error handling and recovery in the ticket system."""
    analyzer = await NLPAnalyzer.create(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        flow_logger=FlowLogger()
    )
    
    # Test with empty message
    ticket = await analyzer.analyze_message("", {"user_id": "test_user"})
    
    assert ticket.status == TicketStatus.ERROR
    assert len(ticket.errors) == 1
    assert ticket.errors[0]["type"] == "validation_error"
    
    # Test with invalid service
    ticket = await analyzer.analyze_message("do something impossible", {"user_id": "test_user"})
    
    assert ticket.status == TicketStatus.SERVICE_CREATION
    assert len(ticket.errors) == 0  # Not an error, just needs service creation

@pytest.mark.asyncio
async def test_full_ticket_lifecycle(mock_environment, monkeypatch):
    """Test a complete ticket lifecycle from creation to completion."""
    # Mock Slack and OpenAI
    class MockSlack:
        async def chat_postMessage(self, channel, text, thread_ts=None):
            return {"ok": True, "ts": "test_ts"}
    
    class MockOpenAI:
        def __init__(self):
            class Chat:
                def __init__(self):
                    class Completions:
                        async def create(self, model, messages, temperature, max_tokens):
                            class MockResponse:
                                def __init__(self):
                                    class Choice:
                                        def __init__(self):
                                            class Message:
                                                def __init__(self):
                                                    self.content = "I've scheduled your meeting for tomorrow at 2 PM."
                                            self.message = Message()
                                    self.choices = [Choice()]
                            return MockResponse()
                    self.completions = Completions()
                async def create(self, model, messages, temperature, max_tokens):
                    return await self.completions.create(model, messages, temperature, max_tokens)
            self.chat = Chat()
    
    # Initialize components
    analyzer = await NLPAnalyzer.create(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        flow_logger=FlowLogger()
    )
    
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    message_maker = MessageMaker()
    message_maker.slack = MockSlack()
    message_maker.openai = MockOpenAI()
    
    # Start ticket lifecycle
    message = "schedule a meeting tomorrow at 2pm with John and Alice in Conference Room A"
    user_info = {"user_id": "test_user", "channel_id": "test_channel"}
    
    # 1. Create and analyze ticket
    ticket = await analyzer.analyze_message(message, user_info)
    assert ticket.status == TicketStatus.EXECUTING
    
    # 2. Execute service
    result = await agent.execute_service(ticket)
    assert result["status"] == "success"
    
    # 3. Update ticket with results
    ticket.execution_results = result["results"]
    ticket.update_status(TicketStatus.COMPLETED)
    
    # 4. Generate response
    ticket.channel_id = "test_channel"
    await message_maker.send_message(ticket)
    
    # Verify final state
    assert ticket.status == TicketStatus.COMPLETED
    assert len(ticket.messages) == 2
    assert len(ticket.steps_executed) == 2
    assert ticket.final_response is not None 