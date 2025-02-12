import pytest
from src.tools.nlp import NLPAnalyzer
from src.tools.agent import Agent
from src.tools.message_maker import MessageMaker
from src.tools.service_maker import ServiceMaker
import yaml
import sys

@pytest.fixture
async def test_system(tmp_path, mock_openai, mock_slack, monkeypatch):
    """Create test system with all components."""
    # Set up environment variables
    monkeypatch.setenv("SLACK_BOT_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    
    # Set up services file
    services_file = tmp_path / "services.yaml"
    services = {
        "test_service": {
            "name": "Test Service",
            "description": "A test service",
            "intent": "test_intent",
            "triggers": ["test this"],
            "required_entities": ["test_param"],
            "steps": [
                {
                    "tool": "test_tool",
                    "action": "test_action",
                    "params": {"param1": "{test_param}"}
                }
            ],
            "success_criteria": ["Test completed"]
        }
    }
    
    with open(services_file, "w") as f:
        yaml.safe_dump(services, f)
    
    # Set up tools directory
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    tool_file = tools_dir / "test_tool.py"
    with open(tool_file, "w") as f:
        f.write("""
class TestTool:
    \"\"\"A test tool for testing.\"\"\"
    
    async def test_action(self, param1):
        return {"status": "success", "message": f"Test completed with {param1}"}
""")
    
    # Add tools directory to Python path
    sys.path.insert(0, str(tmp_path))
    
    # Create components
    nlp = NLPAnalyzer(str(services_file))
    agent = Agent(str(tools_dir))
    message_maker = MessageMaker()
    message_maker.openai = mock_openai
    message_maker.slack = mock_slack
    service_maker = ServiceMaker(str(services_file))
    service_maker.openai = mock_openai
    
    yield {
        "nlp": nlp,
        "agent": agent,
        "message_maker": message_maker,
        "service_maker": service_maker
    }
    
    # Cleanup
    sys.path.remove(str(tmp_path))

@pytest.mark.asyncio
async def test_known_service_flow(test_system):
    """Test complete flow for a known service."""
    # 1. Process message through NLP
    message = "test this with test_param=test_value"
    user_info = {"id": "U123", "real_name": "Test User"}
    
    nlp_result = test_system["nlp"].analyze_message(message, user_info)
    assert nlp_result["status"] == "matched"
    assert nlp_result["service"] == "test_service"
    
    # 2. Execute service through Agent
    service = {
        "name": "Test Service",
        "steps": [
            {
                "tool": "test_tool",
                "action": "test_action",
                "params": {"param1": nlp_result["entities"]["test_param"]}
            }
        ]
    }
    result = await test_system["agent"].execute_service(service, nlp_result["entities"])
    assert result["status"] == "success"
    
    # 3. Send completion message
    context = {
        "type": "completion",
        "details": {
            "service": "Test Service",
            "results": result["results"]
        }
    }
    await test_system["message_maker"].send_message("C123", context)

@pytest.mark.asyncio
async def test_unknown_service_flow(test_system):
    """Test complete flow for an unknown service that needs to be created."""
    # 1. Process message through NLP
    message = "do something new"
    user_info = {"id": "U123", "real_name": "Test User"}
    
    nlp_result = test_system["nlp"].analyze_message(message, user_info)
    assert nlp_result["status"] == "unknown"
    
    # 2. Create new service
    context = {"nlp_result": nlp_result}
    service_result = await test_system["service_maker"].create_service(message, context)
    assert service_result["status"] == "success"
    
    # 3. Execute new service
    result = await test_system["agent"].execute_service(service_result["service"], {})
    assert result["status"] == "success"
    
    # 4. Send completion message
    context = {
        "type": "completion",
        "details": {
            "results": result["results"]
        }
    }
    await test_system["message_maker"].send_message("C123", context)

@pytest.mark.asyncio
async def test_incomplete_info_flow(test_system):
    """Test flow when missing required information."""
    # 1. Process message through NLP
    message = "test this"  # Missing required param
    user_info = {"id": "U123", "real_name": "Test User"}
    
    nlp_result = test_system["nlp"].analyze_message(message, user_info)
    assert nlp_result["status"] == "incomplete"
    
    # 2. Request missing information
    context = {
        "type": "info_request",
        "details": {
            "missing_info": nlp_result["missing_entities"],
            "message": "Please provide the test parameter"
        }
    }
    await test_system["message_maker"].send_message("C123", context)

@pytest.mark.asyncio
async def test_error_handling_flow(test_system):
    """Test flow when errors occur during execution."""
    # 1. Process message through NLP
    message = "test this param1=invalid"
    user_info = {"id": "U123", "real_name": "Test User"}
    
    nlp_result = test_system["nlp"].analyze_message(message, user_info)
    assert nlp_result["status"] == "matched"
    
    # 2. Execute service (will fail due to invalid param)
    result = await test_system["agent"].execute_service(nlp_result["service"], nlp_result["entities"])
    assert result["status"] == "error"
    
    # 3. Send error message
    context = {
        "type": "error",
        "details": {
            "error": result["error"]
        }
    }
    await test_system["message_maker"].send_message("C123", context) 