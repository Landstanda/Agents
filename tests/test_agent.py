import pytest
import asyncio
from pathlib import Path
from src.tools.agent import Agent
from src.utils.flow_logger import FlowLogger

# Mock tool for testing
class MockCalendarTool:
    def __init__(self, flow_logger=None, **kwargs):
        self.flow_logger = flow_logger
        self.calls = []  # Track method calls

    async def execute(self, action: str, params: dict):
        self.calls.append({"action": action, "params": params})
        
        if action == "check_availability":
            return {"available": True, "conflicts": []}
        elif action == "check_attendee_availability":
            return {"all_available": True, "unavailable_attendees": []}
        elif action == "create_event":
            return {"event_id": "test_event_123", "success": True}
        elif action == "send_calendar_invites":
            return {"sent": True, "recipients": params.get("to", [])}
        
        raise ValueError(f"Unknown action: {action}")

# Create mock tool module
def create_mock_tool(tmp_path):
    tools_dir = tmp_path / "src" / "tools"
    tools_dir.mkdir(parents=True)
    
    # Create calendar.py with our mock tool
    calendar_path = tools_dir / "calendar.py"
    calendar_path.write_text("""
class CalendarTool:
    def __init__(self, flow_logger=None, **kwargs):
        self.flow_logger = flow_logger
        self.calls = []

    async def execute(self, action: str, params: dict):
        self.calls.append({"action": action, "params": params})
        
        if action == "check_availability":
            return {"available": True, "conflicts": []}
        elif action == "check_attendee_availability":
            return {"all_available": True, "unavailable_attendees": []}
        elif action == "create_event":
            return {"event_id": "test_event_123", "success": True}
        elif action == "send_calendar_invites" or action == "send_calendar_invite":
            return {"sent": True, "recipients": params.get("to", [])}
        elif action == "suggest_alternative_time":
            return {"suggested_time": "15:00"}
            
        raise ValueError(f"Unknown action: {action}")
    """)
    
    # Create failing.py for failure tests
    failing_path = tools_dir / "failing.py"
    failing_path.write_text("""
class FailingTool:
    def __init__(self, flow_logger=None, **kwargs):
        self.flow_logger = flow_logger
        self.calls = []
        self.retry_count = 0

    async def execute(self, action: str, params: dict):
        self.calls.append({"action": action, "params": params})
        
        if action == "fail_first":
            if self.retry_count < 1:
                self.retry_count += 1
                raise ValueError("First attempt failed")
            return {"success": True, "attempt": self.retry_count}
            
        if action == "always_fail":
            raise ValueError("Permanent failure")
            
        if action == "handle_failure":
            return {"handled": True}
            
        return {"success": True}
    """)
    
    # Create __init__.py
    (tools_dir / "__init__.py").touch()
    
    # Create mock executions.yaml
    services_dir = tmp_path / "src" / "services"
    services_dir.mkdir(parents=True)
    
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

    - name: "check_attendees"
      tool: "calendar"
      action: "check_attendee_availability"
      params:
        attendees: "{participants}"
        time: "{time}"
        date: "{date}"

    - name: "create_event"
      tool: "calendar"
      action: "create_event"
      params:
        summary: "Meeting with {participants}"
        start_time: "{time}"
        date: "{date}"
        attendees: "{participants}"

  response_templates:
    success: "Meeting scheduled for {date} at {time} with {participants}"
    error: "Unable to schedule meeting: {error_message}"
    """)
    
    return tmp_path

@pytest.fixture
def mock_environment(tmp_path):
    # Create mock tools directory
    tools_dir = tmp_path / "src" / "tools"
    tools_dir.mkdir(parents=True)
    
    # Create calendar.py with our mock tool
    calendar_path = tools_dir / "calendar.py"
    calendar_path.write_text("""
class CalendarTool:
    def __init__(self, flow_logger=None, **kwargs):
        self.flow_logger = flow_logger
        self.calls = []

    async def execute(self, action: str, params: dict):
        self.calls.append({"action": action, "params": params})
        
        if action == "check_availability":
            return {"available": True, "conflicts": []}
        elif action == "check_attendee_availability":
            return {"all_available": True, "unavailable_attendees": []}
        elif action == "create_event":
            return {"event_id": "test_event_123", "success": True}
        elif action == "send_calendar_invites" or action == "send_calendar_invite":
            return {"sent": True, "recipients": params.get("to", [])}
        elif action == "suggest_alternative_time":
            return {"suggested_time": "15:00"}
            
        raise ValueError(f"Unknown action: {action}")
    """)
    
    # Create failing.py for failure tests
    failing_path = tools_dir / "failing.py"
    failing_path.write_text("""
class FailingTool:
    def __init__(self, flow_logger=None, **kwargs):
        self.flow_logger = flow_logger
        self.calls = []
        self.retry_count = 0

    async def execute(self, action: str, params: dict):
        self.calls.append({"action": action, "params": params})
        
        if action == "fail_first":
            if self.retry_count < 1:
                self.retry_count += 1
                raise ValueError("First attempt failed")
            return {"success": True, "attempt": self.retry_count}
            
        if action == "always_fail":
            raise ValueError("Permanent failure")
            
        if action == "handle_failure":
            return {"handled": True}
            
        return {"success": True}
    """)
    
    # Create __init__.py
    (tools_dir / "__init__.py").touch()
    
    # Create mock executions.yaml
    services_dir = tmp_path / "src" / "services"
    services_dir.mkdir(parents=True)
    
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

    - name: "check_attendees"
      tool: "calendar"
      action: "check_attendee_availability"
      params:
        attendees: "{participants}"
        time: "{time}"
        date: "{date}"

    - name: "create_event"
      tool: "calendar"
      action: "create_event"
      params:
        summary: "Meeting with {participants}"
        start_time: "{time}"
        date: "{date}"
        attendees: "{participants}"

  response_templates:
    success: "Meeting scheduled for {date} at {time} with {participants}"
    error: "Unable to schedule meeting: {error_message}"
    """)
    
    return tmp_path

@pytest.mark.asyncio
async def test_tool_loading(mock_environment):
    # Initialize agent with mock environment
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Test tool loading
    tool = await agent._get_tool("calendar")
    assert tool is not None
    assert hasattr(tool, 'execute')
    
    # Test tool caching
    tool2 = await agent._get_tool("calendar")
    assert tool2 is tool  # Should return same instance

@pytest.mark.asyncio
async def test_tool_loading_errors(mock_environment):
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Test loading non-existent tool
    with pytest.raises(ValueError, match="Tool not found: nonexistent"):
        await agent._get_tool("nonexistent")

@pytest.mark.asyncio
async def test_service_execution(mock_environment):
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Test executing schedule_meeting service
    analysis = {
        "service": "schedule_meeting",
        "entities": {
            "time": "14:00",
            "date": "2024-03-20",
            "participants": ["John", "Alice"]
        },
        "user_info": {"user_id": "test_user"}
    }
    
    response = await agent.execute_service(analysis)
    
    # Verify response
    assert response["text"] == "Meeting scheduled for 2024-03-20 at 14:00 with ['John', 'Alice']"
    
    # Verify tool was called with correct parameters
    tool = agent.tools["calendar"]
    assert len(tool.calls) == 3  # Should have made 3 calls
    
    # Verify call sequence
    assert tool.calls[0]["action"] == "check_availability"
    assert tool.calls[1]["action"] == "check_attendee_availability"
    assert tool.calls[2]["action"] == "create_event"

@pytest.mark.asyncio
async def test_parameter_formatting(mock_environment):
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Test basic parameter formatting
    params = {
        "time": "{time}",
        "date": "{date}",
        "static": "value"
    }
    entities = {
        "time": "15:00",
        "date": "2024-03-21"
    }
    
    formatted = agent._format_params(params, entities, {})
    assert formatted["time"] == "15:00"
    assert formatted["date"] == "2024-03-21"
    assert formatted["static"] == "value"

@pytest.mark.asyncio
async def test_step_context(mock_environment):
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Test parameter formatting with step context
    step_context = {
        "create_event": {"event_id": "test_123"}
    }
    
    params = {
        "event_id": "{previous_step.result.event_id}"
    }
    
    formatted = agent._format_params(params, {}, step_context)
    assert formatted["event_id"] == "test_123"

@pytest.mark.asyncio
async def test_loop_execution(mock_environment):
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Create a service with a loop
    service_yaml = """
retry_service:
  executor_type: "calendar"
  steps:
    - name: "check_attendees"
      tool: "calendar"
      action: "check_attendee_availability"
      params:
        attendees: "{participants}"
        time: "{time}"
      loop:
        condition: "all_available"
        max_iterations: 2
        on_fail: "suggest_alternative_time"

  response_templates:
    success: "All attendees are available"
    error: "Could not find suitable time: {error_message}"
    """
    
    # Update executions file
    with open(mock_environment / "src" / "services" / "executions.yaml", 'w') as f:
        f.write(service_yaml)
    
    # Reload agent to pick up new service
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
        
    # Test executing service with loop
    analysis = {
        "service": "retry_service",
        "entities": {
            "time": "14:00",
            "participants": ["John", "Alice"]
        }
    }
    
    response = await agent.execute_service(analysis)
    assert response["text"] == "All attendees are available"
    
    # Verify loop executed correct number of times
    tool = agent.tools["calendar"]
    assert len(tool.calls) == 1  # Should succeed on first try

@pytest.mark.asyncio
async def test_failure_handling(mock_environment):
    # Create service with failure handling
    service_yaml = """
failure_test:
  executor_type: "failing"
  steps:
    - name: "retry_step"
      tool: "failing"
      action: "fail_first"
      params:
        input: "test"
      on_failure:
        max_retries: 2
        action: "fail_first"

    - name: "failing_step"
      tool: "failing"
      action: "always_fail"
      params:
        input: "test"
      on_failure:
        action: "handle_failure"

  response_templates:
    success: "Service completed successfully"
    error: "Service failed: {error_message}"
    """
    
    # Update executions file
    with open(mock_environment / "src" / "services" / "executions.yaml", 'w') as f:
        f.write(service_yaml)
    
    # Reload agent to pick up new service
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Test retry behavior
    analysis = {
        "service": "failure_test",
        "entities": {},
        "user_info": {"user_id": "test_user"}
    }
    
    response = await agent.execute_service(analysis)
    
    # Verify failure handling behavior
    tool = agent.tools["failing"]
    
    # Should have at least initial failure and retry
    retry_attempts = [call for call in tool.calls if call["action"] == "fail_first"]
    assert len(retry_attempts) >= 2
    
    # Should have a handle_failure call
    handle_attempts = [call for call in tool.calls if call["action"] == "handle_failure"]
    assert len(handle_attempts) >= 1
    
    # The always_fail step should have been attempted
    fail_attempts = [call for call in tool.calls if call["action"] == "always_fail"]
    assert len(fail_attempts) == 1

@pytest.mark.asyncio
async def test_conditional_execution(mock_environment):
    # Create service with conditions
    service_yaml = """
conditional_service:
  executor_type: "calendar"
  steps:
    - name: "check_availability"
      tool: "calendar"
      action: "check_availability"
      params:
        time: "{time}"
        date: "{date}"
      condition:
        field: "available"
        value: true

    - name: "create_event"
      tool: "calendar"
      action: "create_event"
      params:
        time: "{time}"
        date: "{date}"
        summary: "Conditional Event"

  response_templates:
    success: "Event created successfully"
    error: "Failed to create event: {error_message}"
    """
    
    # Update executions file
    with open(mock_environment / "src" / "services" / "executions.yaml", 'w') as f:
        f.write(service_yaml)
    
    # Reload agent to pick up new service
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Test conditional execution
    analysis = {
        "service": "conditional_service",
        "entities": {
            "time": "15:00",
            "date": "2024-03-21"
        }
    }
    
    response = await agent.execute_service(analysis)
    assert response["text"] == "Event created successfully"
    
    tool = agent.tools["calendar"]
    assert len(tool.calls) == 2  # Both steps should execute
    assert tool.calls[0]["action"] == "check_availability"
    assert tool.calls[1]["action"] == "create_event"

@pytest.mark.asyncio
async def test_complex_response_formatting(mock_environment):
    # Create service with complex response
    service_yaml = """
complex_response:
  executor_type: "calendar"
  steps:
    - name: "create_event"
      tool: "calendar"
      action: "create_event"
      params:
        summary: "{title}"
        time: "{time}"
        date: "{date}"
        attendees: "{participants}"

    - name: "send_invites"
      tool: "calendar"
      action: "send_calendar_invites"
      params:
        to: "{participants}"
        event_id: "{previous_step.result.event_id}"

  response_templates:
    success: "Created event '{title}' for {date} at {time}. Invited: {participants}. Event ID: {create_event.event_id}"
    error: "Failed to create event: {error_message}"
    """
    
    # Update executions file
    with open(mock_environment / "src" / "services" / "executions.yaml", 'w') as f:
        f.write(service_yaml)
    
    # Reload agent to pick up new service
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Test complex response formatting
    analysis = {
        "service": "complex_response",
        "entities": {
            "title": "Team Meeting",
            "time": "16:00",
            "date": "2024-03-22",
            "participants": ["John", "Alice", "Bob"]
        }
    }
    
    response = await agent.execute_service(analysis)
    assert "Team Meeting" in response["text"]
    assert "2024-03-22" in response["text"]
    assert "16:00" in response["text"]
    assert "test_event_123" in response["text"]  # From mock tool's event_id
    
    tool = agent.tools["calendar"]
    assert len(tool.calls) == 2
    assert tool.calls[0]["action"] == "create_event"
    assert tool.calls[1]["action"] == "send_calendar_invites"

@pytest.mark.asyncio
async def test_complex_workflow_execution(mock_environment):
    # Create service with complex multi-stage workflow
    service_yaml = """
complex_workflow:
  executor_type: "calendar"
  steps:
    - name: "initial_check"
      tool: "calendar"
      action: "check_availability"
      params:
        time: "{time}"
        date: "{date}"
      condition:
        field: "available"
        value: true
      on_failure:
        action: "suggest_alternative_time"

    - name: "attendee_check"
      tool: "calendar"
      action: "check_attendee_availability"
      params:
        attendees: "{participants}"
        time: "{time}"
        date: "{date}"
      loop:
        condition: "all_available"
        max_iterations: 2
        on_fail: "suggest_alternative_time"

    - name: "create_event"
      tool: "calendar"
      action: "create_event"
      params:
        summary: "{title}"
        time: "{time}"
        date: "{date}"
        attendees: "{participants}"
        location: "{location}"

    - name: "send_invites"
      tool: "calendar"
      action: "send_calendar_invites"
      params:
        to: "{participants}"
        event_id: "{create_event.event_id}"
        summary: "{title}"
        time: "{time}"

  response_templates:
    success: |
      Event '{title}' scheduled successfully:
      Time: {time}
      Date: {date}
      Location: {location}
      Attendees: {participants}
      Event ID: {create_event.event_id}
      Invites sent: {send_invites.sent}
    error: "Workflow failed: {error_message}"
    partial_success: "Completed with warnings: {warning_message}"
    """
    
    # Update executions file
    with open(mock_environment / "src" / "services" / "executions.yaml", 'w') as f:
        f.write(service_yaml)
    
    # Reload agent to pick up new service
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Test complex workflow execution
    analysis = {
        "service": "complex_workflow",
        "entities": {
            "title": "Strategic Planning",
            "time": "14:00",
            "date": "2024-03-22",
            "participants": ["John", "Alice", "Bob"],
            "location": "Conference Room A"
        }
    }
    
    response = await agent.execute_service(analysis)
    
    # Verify complex response formatting
    assert "Strategic Planning" in response["text"]
    assert "Conference Room A" in response["text"]
    assert "test_event_123" in response["text"]  # From mock tool's event_id
    
    # Verify step execution order and context preservation
    tool = agent.tools["calendar"]
    assert len(tool.calls) == 4  # All steps should execute
    assert tool.calls[0]["action"] == "check_availability"
    assert tool.calls[1]["action"] == "check_attendee_availability"
    assert tool.calls[2]["action"] == "create_event"
    assert tool.calls[3]["action"] == "send_calendar_invites"
    
    # Verify parameter passing between steps
    create_event_call = tool.calls[2]["params"]
    assert create_event_call["summary"] == "Strategic Planning"
    assert create_event_call["time"] == "14:00"  # Using original time since no suggestion needed

@pytest.mark.asyncio
async def test_failure_handling_and_recovery(mock_environment):
    # Create service with sophisticated failure handling
    service_yaml = """
failure_test:
  executor_type: "failing"
  steps:
    - name: "initial_attempt"
      tool: "failing"
      action: "always_fail"
      params:
        input: "test"
      on_failure:
        max_retries: 1
        action: "handle_failure"
        params:
          error: "{error_message}"

    - name: "conditional_step"
      tool: "failing"
      action: "always_fail"
      params:
        input: "{initial_attempt.result}"
      condition:
        field: "success"
        value: true
      on_failure:
        action: "handle_failure"
        continue_on_failure: true
        params:
          error: "{error_message}"

    - name: "final_step"
      tool: "failing"
      action: "handle_failure"
      params:
        context: "{initial_attempt.result}"
        error_history: "{conditional_step.error}"

  response_templates:
    success: "Service completed successfully: {final_step.result}"
    error: "Service failed: {error_message}"
    partial_success: "Completed with warnings: {warning_message}"
    """
    
    # Update executions file
    with open(mock_environment / "src" / "services" / "executions.yaml", 'w') as f:
        f.write(service_yaml)
    
    # Create mock failing tool
    class FailingTool:
        def __init__(self):
            self.calls = []

        async def always_fail(self, params):
            self.calls.append({"action": "always_fail", "params": params})
            raise ValueError("Permanent failure")

        async def handle_failure(self, params):
            self.calls.append({"action": "handle_failure", "params": params})
            return {
                "handled": True,
                "warning_message": f"Recovered from failure: {params.get('error', 'Unknown error')}"
            }

    # Create mock tools directory
    tools_dir = mock_environment / "src" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "__init__.py").touch()
    (tools_dir / "failing.py").write_text("""
from typing import Dict, Any

class FailingTool:
    def __init__(self):
        self.calls = []

    async def always_fail(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append({"action": "always_fail", "params": params})
        raise ValueError("Permanent failure")

    async def handle_failure(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append({"action": "handle_failure", "params": params})
        return {
            "handled": True,
            "warning_message": f"Recovered from failure: {params.get('error', 'Unknown error')}"
        }
""")

    # Reload agent to pick up new service
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Test failure handling and recovery
    analysis = {
        "service": "failure_test",
        "entities": {},
        "user_info": {"user_id": "test_user"}
    }
    
    response = await agent.execute_service(analysis)
    
    # Verify failure handling behavior
    tool = agent.tools["failing"]
    assert len(tool.calls) >= 3  # Initial fail + handle failure + final step

    # Verify action sequence
    actions = [call["action"] for call in tool.calls]
    assert "always_fail" in actions  # Initial failure
    assert actions.count("handle_failure") >= 2  # At least two recovery attempts

    # Verify error reporting - we should get a warning since we used continue_on_failure: true
    assert "warning" in response["text"].lower() or "recovered from failure" in response["text"].lower()

@pytest.mark.asyncio
async def test_invalid_service(mock_environment):
    agent = Agent(
        executions_path=str(mock_environment / "src" / "services" / "executions.yaml"),
        tools_path=str(mock_environment / "src" / "tools"),
        flow_logger=FlowLogger()
    )
    
    # Test with non-existent service
    analysis = {
        "service": "nonexistent_service",
        "entities": {}
    }
    
    response = await agent.execute_service(analysis)
    assert "error" in response["text"].lower()
    assert "no execution plan found" in response["params"]["error_message"].lower() 