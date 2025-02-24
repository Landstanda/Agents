import asyncio
import logging
from src.modules.google_auth import GoogleAuthModule
from src.models import Ticket, TicketStatus
import pytest
from pathlib import Path
import os
import pickle
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from google.oauth2.credentials import Credentials
from src.execution.context import ExecutionContext
from src.utils.credential_manager import CredentialManager

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test Data
MOCK_CREDS_PATH = "/home/jeff/Agents/credentials.json"
MOCK_TOKEN_DATA = {
    "token": "mock_token",
    "refresh_token": "mock_refresh_token",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "mock_client_id",
    "client_secret": "mock_secret",
    "scopes": [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/calendar"
    ]
}

class MockCredentials:
    """Mock credentials class that can be pickled"""
    def __init__(self, valid=True, expired=False):
        self.valid = valid
        self.expired = expired
        self.refresh_token = "mock_refresh_token"
        self.token = "mock_token"
        self.token_uri = "https://oauth2.googleapis.com/token"
        self.client_id = "mock_client_id"
        self.client_secret = "mock_secret"
        self.scopes = [
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/calendar"
        ]

    def refresh(self, request):
        if hasattr(self, '_refresh_error'):
            raise self._refresh_error
        self.valid = True
        self.expired = False

@pytest.fixture
def ticket():
    """Create a test ticket"""
    ticket = Ticket(
        user_info={"user_id": "test_user", "channel_id": "test_channel"},
        original_message="Schedule a meeting",
        service="schedule_meeting"
    )
    ticket.current_step = "Authenticate"
    return ticket

@pytest.fixture
def mock_credentials():
    return MockCredentials()

@pytest.fixture
def mock_credential_manager():
    manager = Mock(spec=CredentialManager)
    manager.get_credentials_path = Mock(return_value=MOCK_CREDS_PATH)
    manager.validate_credentials_file = AsyncMock(return_value=True)
    manager.load_token = AsyncMock(return_value=None)
    manager.secure_token_storage = AsyncMock()
    return manager

@pytest.fixture
def mock_context():
    context = Mock(spec=ExecutionContext)
    context.store_result = Mock()
    return context

@pytest.fixture
def auth_module(mock_credential_manager):
    module = GoogleAuthModule()
    module.credential_manager = mock_credential_manager
    return module

@pytest.mark.asyncio
async def test_google_auth_real_credentials(mock_context):
    """Test authentication with real credentials"""
    try:
        logger.info("\n=== Testing Google Auth with Real Credentials ===")

        # Initialize auth module
        auth_module = GoogleAuthModule()

        # Execute authentication
        result = await auth_module.execute(mock_context)

        assert result["success"] is True
        assert "credentials" in result
        assert result["credentials"]["valid"] is True

    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise

@pytest.mark.asyncio
async def test_google_auth_token_reuse(mock_context):
    """Test that subsequent authentications reuse the token"""
    try:
        logger.info("\n=== Testing Token Reuse ===")

        # First authentication
        auth_module = GoogleAuthModule()
        first_result = await auth_module.execute(mock_context)

        # Second authentication should reuse token
        second_result = await auth_module.execute(mock_context)

        assert first_result["success"] is True
        assert second_result["success"] is True
        assert first_result["credentials"]["token"] == second_result["credentials"]["token"]

    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise

class TestGoogleAuthFlow:
    """Test suite for Google authentication flow"""

    @pytest.mark.asyncio
    async def test_initial_auth_flow(self, auth_module, mock_context, mock_credentials):
        """Test initial authentication flow with no existing token"""
        # Mock the OAuth2 flow
        mock_flow = Mock()
        mock_flow.run_local_server = Mock(return_value=mock_credentials)
        
        with patch('os.path.exists', return_value=True), \
             patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file', 
                  return_value=mock_flow):
            result = await auth_module.execute(mock_context)
            
        assert result["success"] is True
        assert result["credentials"]["valid"] is True
        assert result["credentials"]["has_refresh_token"] is True
        assert mock_context.store_result.called

    @pytest.mark.asyncio
    async def test_token_refresh_flow(self, auth_module, mock_context, mock_credentials):
        """Test token refresh flow with expired token"""
        # Set up expired credentials
        mock_credentials.valid = False
        mock_credentials.expired = True
        
        # Create a picklable credentials object
        stored_creds = MockCredentials(valid=False, expired=True)
        
        # Mock token loading
        auth_module.credential_manager.load_token.return_value = pickle.dumps(stored_creds)
        
        with patch('os.path.exists', return_value=True), \
             patch('google.oauth2.credentials.Credentials', return_value=mock_credentials):
            result = await auth_module.execute(mock_context)
            
        assert result["success"] is True
        assert mock_context.store_result.called

    @pytest.mark.asyncio
    async def test_reauthorization_flow(self, auth_module, mock_context, mock_credentials):
        """Test reauthorization flow when refresh fails"""
        # Set up expired credentials that fail to refresh
        mock_credentials.valid = True  # New credentials from OAuth flow should be valid
        mock_credentials.expired = False  # New credentials should not be expired
        
        # Create a picklable credentials object for the expired token
        stored_creds = MockCredentials(valid=False, expired=True)
        stored_creds._refresh_error = ValueError("invalid_grant: Token has been revoked")
        
        # Mock token loading to return the expired token
        auth_module.credential_manager.load_token.return_value = pickle.dumps(stored_creds)
        
        # Mock new OAuth2 flow
        mock_flow = Mock()
        mock_flow.run_local_server = Mock(return_value=mock_credentials)
        
        with patch('os.path.exists', return_value=True), \
             patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file',
                  return_value=mock_flow), \
             patch('google.oauth2.credentials.Credentials', return_value=mock_credentials), \
             patch('pickle.dumps', return_value=b'mock_token_data'):
            result = await auth_module.execute(mock_context)
            
        assert result["success"] is True
        assert result["credentials"]["valid"] is True
        assert not result["credentials"]["expired"]
        assert mock_flow.run_local_server.called
        assert mock_context.store_result.called

    @pytest.mark.asyncio
    async def test_invalid_credentials_file(self, auth_module, mock_context):
        """Test handling of invalid credentials file"""
        auth_module.credential_manager.validate_credentials_file.return_value = False
        
        with patch('os.path.exists', return_value=True):
            result = await auth_module.execute(mock_context)
            
        assert result["success"] is False
        assert "Invalid credentials" in result.get("error", "")
        assert mock_context.store_result.called

    @pytest.mark.asyncio
    async def test_missing_credentials_file(self, auth_module, mock_context):
        """Test handling of missing credentials file"""
        # Mock file not found
        with patch('os.path.exists', return_value=False):
            result = await auth_module.execute(mock_context)
            
        assert result["success"] is False
        assert "not found" in result["error"]
        assert mock_context.store_result.called

    @pytest.mark.asyncio
    async def test_port_fallback_mechanism(self, auth_module, mock_context, mock_credentials):
        """Test port fallback mechanism when primary ports are blocked"""
        # Mock OAuth2 flow with port failures
        mock_flow = Mock()
        mock_flow.run_local_server = Mock(side_effect=[
            OSError("Port 8080 in use"),  # First port fails
            OSError("Port 8090 in use"),  # Second port fails
            mock_credentials  # Third port succeeds
        ])
        
        with patch('os.path.exists', return_value=True), \
             patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file',
                  return_value=mock_flow):
            result = await auth_module.execute(mock_context)
            
        assert result["success"] is True
        assert mock_flow.run_local_server.call_count >= 2
        assert mock_context.store_result.called

    @pytest.mark.asyncio
    async def test_token_storage(self, auth_module, mock_context, mock_credentials):
        """Test secure token storage after successful authentication"""
        # Mock OAuth2 flow
        mock_flow = Mock()
        mock_flow.run_local_server = Mock(return_value=mock_credentials)
        
        # Mock successful token storage
        auth_module.credential_manager.secure_token_storage.return_value = True
        
        with patch('os.path.exists', return_value=True), \
             patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file',
                  return_value=mock_flow), \
             patch('pickle.dumps', return_value=b'mock_token_data'):
            result = await auth_module.execute(mock_context)
            
        assert result["success"] is True
        assert auth_module.credential_manager.secure_token_storage.called
        assert mock_context.store_result.called

    @pytest.mark.asyncio
    async def test_scope_validation(self, auth_module, mock_context, mock_credentials):
        """Test scope validation in credentials"""
        # Mock OAuth2 flow
        mock_flow = Mock()
        mock_flow.run_local_server = Mock(return_value=mock_credentials)
        
        with patch('os.path.exists', return_value=True), \
             patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file',
                  return_value=mock_flow):
            result = await auth_module.execute(mock_context)
            
        assert result["success"] is True
        assert "scopes" in result
        assert isinstance(result["scopes"], list)
        assert all(isinstance(scope, str) for scope in result["scopes"])
        assert "gmail.modify" in str(result["scopes"])
        assert "calendar" in str(result["scopes"])

    def test_module_capabilities(self, auth_module):
        """Test module capabilities"""
        capabilities = auth_module.capabilities
        
        assert isinstance(capabilities, list)
        assert "google_auth" in capabilities
        assert "oauth2" in capabilities
        assert "credentials" in capabilities

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 