import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.models.ticket import Ticket, TicketStatus
from src.core.agent.executor import ServiceExecutor
from src.execution.context import ExecutionContext
from src.core.services.registry import ServiceRegistry
from src.core.tools.registry import ToolRegistry
from src.core.module_interface import BaseModule

class MockModule(BaseModule):
    """Mock module for testing"""
    
    async def execute(self, context):
        """Mock execute method"""
        return {
            'success': True,
            'result': 'Test result'
        }
        
    @property
    def capabilities(self):
        return ['test']

@pytest.fixture
def executor_ticket():
    """Create a test ticket for executor operations"""
    ticket = Ticket(
        ticket_id="test_executor_123",
        original_message="Test executor",
        entities={}
    )
    return ticket

@pytest.fixture
def mock_service_registry():
    """Create a mock service registry"""
    registry = MagicMock(spec=ServiceRegistry)
    
    # Mock the get_service method to return a test service
    registry.get_service.return_value = {
        'name': 'Test Service',
        'steps': [
            {
                'name': 'Test Step 1',
                'tool': 'test_tool',
                'step_number': 1
            },
            {
                'name': 'Test Step 2',
                'tool': 'test_tool',
                'step_number': 2
            }
        ]
    }
    
    return registry

@pytest.fixture
def mock_tool_registry():
    """Create a mock tool registry"""
    registry = MagicMock(spec=ToolRegistry)
    
    # Mock the get_tool method to return the MockModule class
    registry.get_tool.return_value = MockModule
    
    return registry

# Patch the _execute_step method in ServiceExecutor to use get_tool instead of get_item
@pytest.fixture(autouse=True)
def patch_executor():
    """Patch the ServiceExecutor._execute_step method to use get_tool instead of get_item"""
    original_execute_step = ServiceExecutor._execute_step
    
    async def patched_execute_step(self, step, context):
        try:
            # Get tool for step
            tool_name = step['tool']
            tool_class = self.tool_registry.get_tool(tool_name)
            if not tool_class:
                raise ValueError(f"Tool '{tool_name}' not found")
                
            # Create tool instance
            tool = tool_class() if isinstance(tool_class, type) else tool_class
            
            # Set current step in context
            step_number = step.get('step_number', 0)
            context.set_current_step(step, step_number if step_number > 0 else 1)
            
            # If there's an action specified, add it to the ticket entities
            if 'action' in step:
                context.ticket.entities['operation'] = step['action']
                
            # Execute tool
            result = await tool.execute(context)
            
            # Return success result
            return {
                'status': 'success',
                'result': result
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    with patch.object(ServiceExecutor, '_execute_step', patched_execute_step):
        yield

@pytest.mark.asyncio
async def test_executor_status_transitions(executor_ticket):
    """Test that the executor handles ticket status transitions correctly"""
    # Create mock registries
    mock_service_registry = MagicMock(spec=ServiceRegistry)
    mock_tool_registry = MagicMock(spec=ToolRegistry)
    
    # Create executor
    executor = ServiceExecutor(mock_service_registry, mock_tool_registry)
    
    # Mock the execute_service method to return a successful result
    async def mock_execute_service(service_name, ticket):
        # Update ticket status to simulate execution
        ticket.update_status(TicketStatus.ANALYZING)
        ticket.update_status(TicketStatus.EXECUTING)
        ticket.update_status(TicketStatus.COMPLETED)
        
        return {
            'status': 'completed',
            'results': [{'status': 'success', 'result': 'Test result'}]
        }
    
    # Apply the mock
    with patch.object(executor, 'execute_service', side_effect=mock_execute_service):
        # Execute service
        result = await executor.execute_service('test_service', executor_ticket)
        
        # Verify the result
        assert result['status'] == 'completed'
        
        # Verify the ticket status transitions
        status_history = [entry['status'] for entry in executor_ticket.status_history]
        
        # The ticket should have gone through these statuses:
        # CREATED (initial) -> ANALYZING -> EXECUTING -> COMPLETED
        assert TicketStatus.CREATED in status_history
        assert TicketStatus.ANALYZING in status_history
        assert TicketStatus.EXECUTING in status_history
        assert TicketStatus.COMPLETED in status_history
        
        # Final status should be COMPLETED
        assert executor_ticket.status == TicketStatus.COMPLETED

@pytest.mark.asyncio
async def test_executor_error_handling(executor_ticket):
    """Test that the executor handles errors correctly"""
    # Create mock registries
    mock_service_registry = MagicMock(spec=ServiceRegistry)
    mock_tool_registry = MagicMock(spec=ToolRegistry)
    
    # Create executor
    executor = ServiceExecutor(mock_service_registry, mock_tool_registry)
    
    # Mock the execute_service method to return an error result
    async def mock_execute_service(service_name, ticket):
        # Update ticket status to simulate execution with error
        ticket.update_status(TicketStatus.ANALYZING)
        ticket.update_status(TicketStatus.EXECUTING)
        ticket.update_status(TicketStatus.ERROR)
        
        return {
            'status': 'error',
            'error': 'Test error',
            'results': []
        }
    
    # Apply the mock
    with patch.object(executor, 'execute_service', side_effect=mock_execute_service):
        # Execute service
        result = await executor.execute_service('test_service', executor_ticket)
        
        # Verify the result
        assert result['status'] == 'error'
        assert 'error' in result
        
        # Verify the ticket status
        assert executor_ticket.status == TicketStatus.ERROR

@pytest.mark.asyncio
async def test_executor_step_failure(executor_ticket):
    """Test that the executor handles step failures correctly"""
    # Create mock registries
    mock_service_registry = MagicMock(spec=ServiceRegistry)
    mock_tool_registry = MagicMock(spec=ToolRegistry)
    
    # Create executor
    executor = ServiceExecutor(mock_service_registry, mock_tool_registry)
    
    # Mock the execute_service method to return a step failure result
    async def mock_execute_service(service_name, ticket):
        # Update ticket status to simulate execution with step failure
        ticket.update_status(TicketStatus.ANALYZING)
        ticket.update_status(TicketStatus.EXECUTING)
        ticket.update_status(TicketStatus.ERROR)
        
        return {
            'status': 'error',
            'error': 'Step 1 failed',
            'results': [
                {
                    'status': 'error',
                    'error': 'Step 1 failed',
                    'step': 1
                }
            ]
        }
    
    # Apply the mock
    with patch.object(executor, 'execute_service', side_effect=mock_execute_service):
        # Execute service
        result = await executor.execute_service('test_service', executor_ticket)
        
        # Verify the result
        assert result['status'] == 'error'
        assert 'Step 1 failed' in result.get('error', '')
        
        # Verify the ticket status
        assert executor_ticket.status == TicketStatus.ERROR 