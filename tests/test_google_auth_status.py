import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.models.ticket import Ticket, TicketStatus
from src.modules.google_auth import GoogleAuthModule
from src.execution.context import ExecutionContext

@pytest.fixture
def auth_ticket():
    """Create a test ticket for auth operations"""
    ticket = Ticket(
        ticket_id="test_auth_123",
        original_message="Authenticate with Google",
        entities={}
    )
    return ticket

@pytest.fixture
def mock_context(auth_ticket):
    """Create a mock execution context"""
    context = MagicMock(spec=ExecutionContext)
    context.ticket = auth_ticket
    return context

@pytest.mark.asyncio
async def test_auth_module_success(mock_context):
    """Test that the GoogleAuthModule handles success correctly"""
    # Create module
    auth_module = GoogleAuthModule()
    
    # Mock the credentials
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.expired = False
    mock_creds.token = "test_token"
    mock_creds.refresh_token = "test_refresh_token"
    mock_creds.token_uri = "https://oauth2.googleapis.com/token"
    mock_creds.client_id = "test_client_id"
    mock_creds.client_secret = "test_client_secret"
    mock_creds.scopes = ["https://www.googleapis.com/auth/calendar"]
    
    # Patch the token manager
    with patch.object(auth_module, 'token_manager') as mock_token_manager:
        mock_token_manager.load_token.return_value = mock_creds
        
        # Execute the module
        result = await auth_module.execute(mock_context)
        
        # Verify the result
        assert result["success"] is True
        assert "credentials" in result
        
        # The module should NOT have set the ticket status
        # That should be handled by the executor
        assert mock_context.ticket.status == TicketStatus.CREATED

@pytest.mark.asyncio
async def test_auth_module_failure(mock_context):
    """Test that the GoogleAuthModule handles failure correctly"""
    # Create module
    auth_module = GoogleAuthModule()
    
    # Patch the token manager to return None (no token)
    with patch.object(auth_module, 'token_manager') as mock_token_manager:
        mock_token_manager.load_token.return_value = None
        
        # Patch the _get_client_config method to raise an exception
        with patch.object(auth_module, '_get_client_config', side_effect=Exception("Test error")):
            
            # Execute the module
            result = await auth_module.execute(mock_context)
            
            # Verify the result
            assert result["success"] is False
            assert "error" in result
            
            # The module should NOT have set the ticket status
            # That should be handled by the executor
            assert mock_context.ticket.status == TicketStatus.CREATED 