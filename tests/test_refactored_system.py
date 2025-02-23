import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch

from src.models import Ticket, TicketStatus
from src.core.registry.tools import ToolRegistry
from src.core.registry.services import ServiceRegistry
from src.core.agent.executor import ServiceExecutor
from src.core.agent.base import Agent
from src.execution.context import ExecutionContext, StepResult
from src.core.module_interface import BaseModule

# Test data
TEST_SERVICE = {
    'name': 'test_service',
    'version': '1.0.0',
    'steps': [
        {
            'name': 'step1',
            'tool': 'test_tool',
            'action': 'execute',
            'params': {
                'test_param': 'value1'
            }
        },
        {
            'name': 'step2',
            'tool': 'test_tool',
            'action': 'execute',
            'params': {
                'test_param': 'value2'
            },
            'depends_on': [1]
        }
    ]
}

class FailingTool(BaseModule):
    async def execute(self, context: ExecutionContext, **params) -> Dict[str, Any]:
        raise Exception("Test error")

    @property
    def capabilities(self):
        return ['test_capability']

class TestTool(BaseModule):
    """Mock tool for testing"""
    async def execute(self, context: ExecutionContext, **params) -> Dict[str, Any]:
        return {'success': True, 'data': params}
    
    @property
    def capabilities(self):
        return ['test_capability']

@pytest.fixture
async def service_registry():
    """Create and initialize a service registry for testing"""
    registry = ServiceRegistry()
    await registry.load_services()
    # Add test service
    await registry.add_service_version('test_service', TEST_SERVICE)
    return registry

@pytest.fixture
async def tool_registry():
    """Create and initialize a tool registry for testing"""
    registry = ToolRegistry()
    await registry.register_tool('test_tool', TestTool)
    return registry

@pytest.fixture
async def executor(service_registry, tool_registry):
    """Create and initialize a service executor for testing"""
    sr = await service_registry
    tr = await tool_registry
    return ServiceExecutor(sr, tr)

@pytest.fixture
async def agent(service_registry, tool_registry):
    """Create and initialize an agent for testing"""
    sr = await service_registry
    tr = await tool_registry
    agent = Agent()
    agent.service_registry = sr
    agent.tool_registry = tr
    agent.executor = ServiceExecutor(sr, tr)
    agent._initialized = True
    return agent

@pytest.fixture
def ticket():
    """Create a test ticket"""
    return Ticket(
        ticket_id='test_123',
        original_message='Test request',
        service='test_service',
        entities={'test_param': 'value1'}
    )

@pytest.mark.asyncio
async def test_tool_registry_validation(tool_registry):
    """Test tool validation with service requirements"""
    # Test valid tool
    registry = await tool_registry
    assert await registry.validate_tool(TestTool, TEST_SERVICE)
    
    # Test invalid tool
    class InvalidTool:
        pass
    
    assert not await registry.validate_tool(InvalidTool, TEST_SERVICE)

@pytest.mark.asyncio
async def test_service_registry_versioning(service_registry):
    """Test service versioning functionality"""
    # Test version management
    registry = await service_registry
    service_v1 = TEST_SERVICE.copy()
    service_v1['version'] = '1.0.0'
    
    service_v2 = TEST_SERVICE.copy()
    service_v2['version'] = '2.0.0'
    
    await registry.add_service_version('test_service', service_v1)
    await registry.add_service_version('test_service', service_v2)
    
    # Verify versions
    assert registry.get_service('test_service')['version'] == '2.0.0'
    assert registry.get_service('test_service', version='1.0.0')['version'] == '1.0.0'

@pytest.mark.asyncio
async def test_execution_context_management(ticket):
    """Test execution context state management"""
    context = ExecutionContext(ticket, TEST_SERVICE)
    
    # Test variable management
    context.set_variable('test_var', 'test_value')
    assert context.get_variable('test_var') == 'test_value'
    
    # Test nested variables
    context.set_variable('nested.var', 'nested_value')
    assert context.get_variable('nested.var') == 'nested_value'
    
    # Test step results
    context.next_step(TEST_SERVICE['steps'][0])
    context.store_result(1, {'data': 'result'}, success=True)
    
    assert len(context.step_results) == 1
    assert context.step_results[1].success

@pytest.mark.asyncio
async def test_executor_synchronization(executor, ticket):
    """Test service executor synchronization"""
    # Test parallel execution
    exec_instance = await executor
    
    async def execute_service():
        return await exec_instance.execute_service(TEST_SERVICE, ticket)
    
    # Run multiple executions in parallel
    results = await asyncio.gather(
        execute_service(),
        execute_service(),
        execute_service()
    )
    
    # Verify all executions completed successfully
    assert all(result['status'] == 'completed' for result in results)

@pytest.mark.asyncio
async def test_error_propagation(agent, ticket):
    """Test error handling and propagation"""
    # Mock a failing tool
    agent_instance = await agent
    await agent_instance.tool_registry.register_tool('failing_tool', FailingTool)

    # Create test service that uses failing tool
    failing_service = {
        'name': 'failing_service',
        'version': '1.0.0',
        'steps': [
            {
                'name': 'failing_step',
                'tool': 'failing_tool',
                'parameters': {}
            }
        ]
    }

    await agent_instance.service_registry.add_service_version('failing_service', failing_service)

    # Update ticket to use failing service
    ticket.service = 'failing_service'
    ticket.entities = {}  # Clear entities as they're not needed for this test

    # Process ticket and verify error handling
    await agent_instance.process_ticket(ticket)
    assert ticket.status == TicketStatus.ERROR
    assert len(ticket.errors) > 0
    assert "Test error" in ticket.errors[0]['message']

@pytest.mark.asyncio
async def test_full_execution_flow(agent, ticket):
    """Test complete execution flow"""
    # Process ticket
    agent_instance = await agent
    await agent_instance.process_ticket(ticket)
    
    # Verify execution completed successfully
    assert ticket.status == TicketStatus.COMPLETED
    assert len(ticket.execution_results) > 0
    assert not ticket.errors

@pytest.mark.asyncio
async def test_context_rollback(executor, ticket):
    """Test execution context rollback functionality"""
    context = ExecutionContext(ticket, TEST_SERVICE)
    
    # Set up initial state
    context.set_variable('test_var', 'test_value')
    context.next_step(TEST_SERVICE['steps'][0])
    context.store_result(1, {'data': 'result'}, success=True)
    
    # Perform rollback
    context.rollback()
    
    # Verify state was reset
    assert len(context.step_results) == 0
    assert context.current_step is None
    assert 'test_var' not in context.variables
    assert all(key in context.variables for key in ticket.entities.keys())

@pytest.mark.asyncio
async def test_service_validation(service_registry):
    """Test service definition validation"""
    # Test valid service
    registry = await service_registry
    assert await registry.validate_service(TEST_SERVICE)
    
    # Test invalid service
    invalid_service = TEST_SERVICE.copy()
    del invalid_service['steps']
    with pytest.raises(ValueError):
        await registry.validate_service(invalid_service)

@pytest.mark.asyncio
async def test_integration_flow(agent):
    """Test complete integration flow"""
    # Create and process ticket
    agent_instance = await agent
    ticket = Ticket(
        ticket_id='test_integration',
        original_message='Test integration flow',
        service='test_service',
        entities={'test_param': 'value1'}
    )
    
    await agent_instance.process_ticket(ticket)
    
    # Verify complete flow
    assert ticket.status == TicketStatus.COMPLETED
    assert len(ticket.execution_results) > 0
    assert not ticket.errors 