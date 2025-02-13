import pytest
from pathlib import Path
from src.tools.nlp import NLPAnalyzer
from src.tools.agent import Agent
from src.utils.flow_logger import FlowLogger

@pytest.fixture
def mock_environment(tmp_path):
    # Create services directory
    services_dir = tmp_path / "src" / "services"
    services_dir.mkdir(parents=True)
    
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
  optional_entities:
    - location
    - participants

help:
  name: Help
  description: Show available commands
  intent: help
  triggers:
    - help
    - what can you do
    - show commands
""")

    # Create executions.yaml
    executions_path = services_dir / "executions.yaml"
    executions_path.write_text("""
schedule_meeting:
  executor_type: "calendar"
  steps:
    - name: "check_availability"
      tool: "calendar"
      action: "check_availability"
      params:
        time: "{time}"
        date: "{date}"

  response_templates:
    success: "Meeting scheduled for {date} at {time}"
    error: "Failed to schedule meeting: {error_message}"

help:
  executor_type: "help"
  steps:
    - name: "show_help"
      tool: "help"
      action: "show_capabilities"
      params: {}
      
  response_templates:
    success: "Available commands: {show_help.capabilities}"
    error: "Failed to show help: {error_message}"
""")

    # Create tools directory with calendar tool
    tools_dir = tmp_path / "src" / "tools"
    tools_dir.mkdir(parents=True)
    
    # Create calendar.py
    calendar_path = tools_dir / "calendar.py"
    calendar_path.write_text("""
class CalendarTool:
    def __init__(self, flow_logger=None):
        self.flow_logger = flow_logger
        self.calls = []

    async def execute(self, action: str, params: dict):
        self.calls.append({"action": action, "params": params})
        if action == "check_availability":
            return {"available": True}
        return {"success": True}
""")

    # Create help.py
    help_path = tools_dir / "help.py"
    help_path.write_text("""
class HelpTool:
    def __init__(self, flow_logger=None):
        self.flow_logger = flow_logger
        self.calls = []

    async def execute(self, action: str, params: dict = None):
        self.calls.append({"action": action, "params": params or {}})
        if action == "show_capabilities":
            return {
                "capabilities": [
                    "Schedule meetings",
                    "Get help"
                ]
            }
        return {"success": True}
""")
    
    (tools_dir / "__init__.py").touch()
    
    return tmp_path

@pytest.mark.asyncio
async def test_nlp_intent_recognition(mock_environment):
    """Test basic intent recognition."""
    analyzer = await NLPAnalyzer.create(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        flow_logger=FlowLogger()
    )
    
    # Test meeting scheduling intent
    result = await analyzer.analyze_message(
        "schedule a meeting tomorrow at 2pm",
        {"user_id": "test_user"}
    )
    
    assert result["status"] == "matched"
    assert result["service"] == "schedule_meeting"
    assert result["intent"] == "schedule_meeting"
    assert "time" in result["entities"]
    assert "date" in result["entities"]
    
    # Test help intent
    result = await analyzer.analyze_message(
        "what can you do?",
        {"user_id": "test_user"}
    )
    
    assert result["status"] == "matched"
    assert result["service"] == "help"
    assert result["intent"] == "help"

@pytest.mark.asyncio
async def test_nlp_entity_extraction(mock_environment):
    """Test entity extraction from messages."""
    analyzer = await NLPAnalyzer.create(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        flow_logger=FlowLogger()
    )
    
    result = await analyzer.analyze_message(
        "schedule a meeting with John and Alice tomorrow at 2:30pm in Conference Room A",
        {"user_id": "test_user"}
    )
    
    assert result["status"] == "matched"
    assert "time" in result["entities"]
    assert result["entities"]["time"] == "14:30"
    assert "date" in result["entities"]
    assert "tomorrow" in result["entities"]["date"]
    assert "participants" in result["entities"]
    assert len(result["entities"]["participants"]) == 2
    assert "John" in result["entities"]["participants"]
    assert "Alice" in result["entities"]["participants"]
    assert "location" in result["entities"]
    assert "Conference Room A" in result["entities"]["location"]

@pytest.mark.asyncio
async def test_nlp_missing_entities(mock_environment):
    """Test handling of missing required entities."""
    analyzer = await NLPAnalyzer.create(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        flow_logger=FlowLogger()
    )
    
    result = await analyzer.analyze_message(
        "schedule a meeting",
        {"user_id": "test_user"}
    )
    
    assert result["status"] == "incomplete"
    assert "missing_entities" in result
    assert "time" in result["missing_entities"]
    assert "date" in result["missing_entities"]

@pytest.mark.asyncio
async def test_nlp_agent_integration(mock_environment):
    """Test integration between NLP analyzer and Agent."""
    analyzer = await NLPAnalyzer.create(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        flow_logger=FlowLogger()
    )
    
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Test complete flow from message to execution
    nlp_result = await analyzer.analyze_message(
        "schedule a meeting tomorrow at 2pm",
        {"user_id": "test_user"}
    )
    
    assert nlp_result["status"] == "matched"
    assert nlp_result["entities"]["time"] == "14:00"
    
    # Pass NLP result to agent
    agent_response = await agent.execute_service(nlp_result)
    
    assert "scheduled" in agent_response["text"].lower()
    assert "14:00" in agent_response["text"]
    assert "tomorrow" in agent_response["text"]

@pytest.mark.asyncio
async def test_nlp_agent_help_flow(mock_environment):
    """Test help command flow through NLP and Agent."""
    analyzer = await NLPAnalyzer.create(
        services_path=str(mock_environment / "src" / "services" / "services.yaml"),
        flow_logger=FlowLogger()
    )
    
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    nlp_result = await analyzer.analyze_message(
        "what can you do?",
        {"user_id": "test_user"}
    )
    
    assert nlp_result["status"] == "matched"
    assert nlp_result["service"] == "help"
    
    agent_response = await agent.execute_service(nlp_result)
    
    assert "commands" in agent_response["text"].lower()
    assert "schedule meetings" in agent_response["text"].lower() 