import pytest
import os
import sys
from pathlib import Path
from src.tools.agent import Agent

@pytest.fixture
def agent(tmp_path):
    """Create Agent with test tools."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    
    # Create test tool file
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
    
    # Create Agent instance
    agent = Agent(str(tools_dir))
    agent.load_tools()  # Reload tools after adding to Python path
    
    # Clean up sys.path after test
    yield agent
    sys.path.remove(str(tmp_path))

@pytest.mark.asyncio
async def test_execute_service_success(agent):
    """Test successful service execution."""
    service = {
        "name": "Test Service",
        "steps": [
            {
                "tool": "test_tool",
                "action": "test_action",
                "params": {"param1": "test_value"}
            }
        ],
        "success_criteria": ["Test completed"]
    }
    
    context = {"test_param": "test_value"}
    
    result = await agent.execute_service(service, context)
    
    assert result["status"] == "success"
    assert result["results"][0]["result"]["message"] == "Test completed with test_value"

@pytest.mark.asyncio
async def test_execute_service_invalid_format(agent):
    """Test service execution with invalid format."""
    service = {
        "name": "Invalid Service",
        # Missing steps
    }
    
    context = {}
    
    result = await agent.execute_service(service, context)
    
    assert result["status"] == "error"
    assert "invalid service format" in result["error"].lower()

@pytest.mark.asyncio
async def test_execute_service_busy(agent):
    """Test service execution when agent is busy."""
    # Set agent as busy
    agent.is_busy = True
    
    service = {
        "name": "Test Service",
        "steps": [
            {
                "tool": "test_tool",
                "action": "test_action",
                "params": {"param1": "test_value"}
            }
        ]
    }
    
    context = {}
    
    result = await agent.execute_service(service, context)
    
    assert result["status"] == "error"
    assert "Agent is busy with another service" == result["error"]
    
    # Reset agent busy state
    agent.is_busy = False

@pytest.mark.asyncio
async def test_execute_service_missing_tool(agent):
    """Test service execution with missing tool."""
    service = {
        "name": "Test Service",
        "steps": [
            {
                "tool": "nonexistent_tool",
                "action": "test_action",
                "params": {"param1": "test_value"}
            }
        ]
    }
    
    context = {}
    
    result = await agent.execute_service(service, context)
    
    assert result["status"] == "error"
    assert "tool not found" in result["error"].lower() 