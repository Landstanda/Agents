import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional, Type

from src.core.registry.service_registry import ServiceRegistry
from src.core.registry.tool_registry import ToolRegistry
from src.core.agent.base_agent import BaseAgent
from src.core.agent.executor import ServiceExecutor
from src.core.module_interface import BaseModule
from src.models import Ticket, TicketStatus

# Mock Components
class MockTool(BaseModule):
    """Mock tool for testing"""
    capabilities = ["test_capability"]
    
    async def execute(self, **kwargs):
        """Mock execute method"""
        return {"status": "success"}

# Base fixtures for all tests
@pytest.fixture
def basic_ticket():
    """Create a basic ticket for testing"""
    return Ticket(
        original_message="test message",
        user_info={"user": "test_user"},
        channel_id="test_channel"
    )

class TestAgentInitialization:
    """Tests for agent initialization and basic setup"""
    
    def test_agent_creation(self):
        """Test basic agent creation without initialization"""
        agent = BaseAgent()
        assert not agent._initialized
        assert agent.service_registry is None
        assert agent.tool_registry is None
        assert agent.executor is None
    
    @pytest.mark.asyncio
    async def test_agent_initialization_with_mocks(self):
        """Test agent initialization with mock components"""
        # Create base agent
        agent = BaseAgent()
        
        # Create mock services
        mock_services = {
            "test_service": {
                "name": "Test Service",
                "steps": [
                    {
                        "name": "test_step",
                        "tool": "test_tool",
                        "action": "execute"
                    }
                ]
            }
        }
        
        # Create mock tools
        mock_tools = {
            "test_tool": MockTool
        }
        
        # Set up service registry
        with patch('src.core.registry.service_registry.ServiceRegistry') as MockServiceRegistry:
            service_registry = MockServiceRegistry.return_value
            service_registry.initialize = AsyncMock()
            service_registry.load_items = AsyncMock()
            service_registry.items = mock_services
            service_registry.initialized = False
            
            # Set up tool registry
            with patch('src.core.registry.tool_registry.ToolRegistry') as MockToolRegistry:
                tool_registry = MockToolRegistry.return_value
                tool_registry.initialize = AsyncMock()
                tool_registry.load_items = AsyncMock()
                tool_registry.items = mock_tools
                tool_registry.initialized = False
                
                # Set up executor
                with patch('src.core.agent.executor.ServiceExecutor') as MockExecutor:
                    executor = MockExecutor.return_value
                    
                    # Assign mocks to agent
                    agent.service_registry = service_registry
                    agent.tool_registry = tool_registry
                    agent.executor = executor
                    
                    # Initialize agent
                    await agent.initialize()
                    
                    # Verify initialization
                    assert agent._initialized
                    assert service_registry.initialize.called
                    assert tool_registry.initialize.called
                    assert len(service_registry.items) == len(mock_services)
                    assert len(tool_registry.items) == len(mock_tools)

class TestRegistryIntegration:
    """Tests for registry integration and component interaction"""
    
    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing"""
        return {
            "test_service": {
                "name": "Test Service",
                "steps": [
                    {
                        "name": "test_step",
                        "tool": "test_tool",
                        "action": "execute",
                        "params": {"test_param": "test_value"}
                    }
                ]
            }
        }
    
    @pytest.fixture
    def mock_tools(self):
        """Create mock tools for testing"""
        return {
            "test_tool": MockTool
        }
    
    @pytest.mark.asyncio
    async def test_registry_initialization(self, mock_services, mock_tools):
        """Test registry initialization and service/tool loading"""
        with patch('src.core.registry.service_registry.ServiceRegistry') as MockServiceRegistry:
            service_registry = MockServiceRegistry.return_value
            service_registry.initialize = AsyncMock()
            service_registry.load_items = AsyncMock()
            service_registry.items = mock_services
            service_registry.initialized = False
            
            with patch('src.core.registry.tool_registry.ToolRegistry') as MockToolRegistry:
                tool_registry = MockToolRegistry.return_value
                tool_registry.initialize = AsyncMock()
                tool_registry.load_items = AsyncMock()
                tool_registry.items = mock_tools
                tool_registry.initialized = False
                
                # Create and initialize agent
                agent = BaseAgent()
                agent.service_registry = service_registry
                agent.tool_registry = tool_registry
                await agent.initialize()
                
                # Verify initialization
                assert agent._initialized
                assert service_registry.initialize.called
                assert tool_registry.initialize.called
                assert len(service_registry.items) == len(mock_services)
                assert len(tool_registry.items) == len(mock_tools)
    
    @pytest.mark.asyncio
    async def test_service_lookup(self, mock_services, mock_tools):
        """Test service lookup and validation"""
        with patch('src.core.registry.service_registry.ServiceRegistry') as MockServiceRegistry:
            service_registry = MockServiceRegistry.return_value
            service_registry.initialize = AsyncMock()
            service_registry.load_items = AsyncMock()
            service_registry.items = mock_services
            service_registry.get_item = MagicMock(return_value=mock_services["test_service"])
            service_registry.initialized = True
            
            with patch('src.core.registry.tool_registry.ToolRegistry') as MockToolRegistry:
                tool_registry = MockToolRegistry.return_value
                tool_registry.initialize = AsyncMock()
                tool_registry.load_items = AsyncMock()
                tool_registry.items = mock_tools
                tool_registry.get_item = MagicMock(return_value=MockTool)
                tool_registry.initialized = True
                
                # Create and initialize agent
                agent = BaseAgent()
                agent.service_registry = service_registry
                agent.tool_registry = tool_registry
                agent._initialized = True
                
                # Test service lookup
                service = agent.service_registry.get_item("test_service")
                assert service is not None
                assert service["name"] == "Test Service"
                assert len(service["steps"]) == 1
                
                # Test tool lookup
                tool_class = agent.tool_registry.get_item("test_tool")
                assert tool_class is not None
                assert tool_class == MockTool
    
    @pytest.mark.asyncio
    async def test_invalid_service_lookup(self, mock_services, mock_tools):
        """Test handling of invalid service lookups"""
        with patch('src.core.registry.service_registry.ServiceRegistry') as MockServiceRegistry:
            service_registry = MockServiceRegistry.return_value
            service_registry.initialize = AsyncMock()
            service_registry.items = mock_services
            service_registry.get_item = MagicMock(return_value=None)  # Simulate missing service
            service_registry.initialized = True
            
            with patch('src.core.registry.tool_registry.ToolRegistry') as MockToolRegistry:
                tool_registry = MockToolRegistry.return_value
                tool_registry.initialize = AsyncMock()
                tool_registry.items = mock_tools
                tool_registry.initialized = True
                
                # Create and initialize agent
                agent = BaseAgent()
                agent.service_registry = service_registry
                agent.tool_registry = tool_registry
                agent._initialized = True
                
                # Test invalid service lookup
                service = agent.service_registry.get_item("nonexistent_service")
                assert service is None

class TestServiceExecution:
    """Tests for service execution functionality"""
    
    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing"""
        return {
            "test_service": {
                "name": "Test Service",
                "steps": [
                    {
                        "name": "test_step",
                        "tool": "test_tool",
                        "action": "execute",
                        "params": {"test_param": "test_value"}
                    }
                ]
            }
        }
    
    @pytest.fixture
    def mock_tools(self):
        """Create mock tools for testing"""
        return {
            "test_tool": MockTool
        }
    
    @pytest.fixture
    async def configured_agent(self, mock_services, mock_tools):
        """Create a pre-configured agent for service execution tests"""
        # Create and configure agent
        agent = BaseAgent()
        
        # Set up service registry
        service_registry = MagicMock(spec=ServiceRegistry)
        service_registry.initialize = AsyncMock()
        service_registry.items = mock_services
        service_registry.get_item = MagicMock(return_value=mock_services["test_service"])
        service_registry.initialized = True
        agent.service_registry = service_registry
        
        # Set up tool registry
        tool_registry = MagicMock(spec=ToolRegistry)
        tool_registry.initialize = AsyncMock()
        tool_registry.items = mock_tools
        tool_registry.get_item = MagicMock(return_value=MockTool)
        tool_registry.initialized = True
        agent.tool_registry = tool_registry
        
        # Set up executor
        executor = MagicMock(spec=ServiceExecutor)
        executor.execute_service = AsyncMock(return_value={
            "status": "success",
            "results": [{"step": 1, "result": "test_result"}]
        })
        agent.executor = executor
        
        # Mark as initialized
        agent._initialized = True
        
        return agent
    
    @pytest.mark.asyncio
    async def test_basic_service_execution(self, configured_agent, basic_ticket):
        """Test basic service execution flow"""
        # Get configured agent
        agent = await configured_agent
        
        # Configure ticket
        basic_ticket.service = "test_service"
        
        # Execute service
        result = await agent.execute_service("test_service", basic_ticket)
        
        # Verify execution
        assert result["status"] == "success"
        assert agent.executor.execute_service.called
        assert len(result["results"]) == 1
        assert result["results"][0]["step"] == 1
    
    @pytest.mark.asyncio
    async def test_ticket_processing(self, configured_agent, basic_ticket):
        """Test ticket processing flow"""
        # Get configured agent
        agent = await configured_agent
        
        # Configure ticket
        basic_ticket.service = "test_service"
        
        # Process ticket
        await agent.process_ticket(basic_ticket)
        
        # Verify processing
        assert agent.executor.execute_service.called
        assert basic_ticket.status != TicketStatus.ERROR
        assert len(basic_ticket.execution_results) > 0
    
    @pytest.mark.asyncio
    async def test_service_execution_with_params(self, configured_agent, basic_ticket):
        """Test service execution with parameters"""
        # Get configured agent
        agent = await configured_agent
        
        # Configure ticket with parameters
        basic_ticket.service = "test_service"
        basic_ticket.entities = {"test_param": "custom_value"}
        
        # Execute service
        result = await agent.execute_service("test_service", basic_ticket)
        
        # Verify execution
        assert result["status"] == "success"
        assert agent.executor.execute_service.called
        
        # Verify parameters were passed
        call_args = agent.executor.execute_service.call_args
        assert call_args is not None
        service_def, ticket = call_args[0]
        assert service_def["steps"][0]["params"]["test_param"] == "test_value"

class TestErrorHandling:
    """Tests for error handling scenarios"""
    
    @pytest.fixture
    async def error_prone_agent(self):
        """Create an agent configured to simulate errors"""
        agent = BaseAgent()
        
        # Configure registries
        service_registry = MagicMock(spec=ServiceRegistry)
        service_registry.initialized = True
        service_registry.get_item.return_value = {
            "name": "Test Service",
            "steps": [{"name": "test_step", "tool": "test_tool"}]
        }
        
        tool_registry = MagicMock(spec=ToolRegistry)
        tool_registry.initialized = True
        
        # Configure executor to raise an exception
        executor = MagicMock(spec=ServiceExecutor)
        executor.execute_service = AsyncMock(side_effect=Exception("Test error"))
        
        # Set up agent
        agent.service_registry = service_registry
        agent.tool_registry = tool_registry
        agent.executor = executor
        agent._initialized = True
        
        return agent
    
    @pytest.mark.asyncio
    async def test_execution_error_handling(self, error_prone_agent, basic_ticket):
        """Test handling of execution errors"""
        basic_ticket.service = "test_service"
        await error_prone_agent.process_ticket(basic_ticket)
        
        assert basic_ticket.status == TicketStatus.ERROR
        assert len(basic_ticket.errors) > 0
        assert "Test error" in basic_ticket.errors[0]["error"]
    
    @pytest.mark.asyncio
    async def test_invalid_service_handling(self, configured_agent, basic_ticket):
        """Test handling of invalid service requests"""
        basic_ticket.service = "nonexistent_service"
        configured_agent.service_registry.get_item.return_value = None
        
        await configured_agent.process_ticket(basic_ticket)
        assert basic_ticket.status == TicketStatus.ERROR 