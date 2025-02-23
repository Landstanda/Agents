import asyncio
import logging
from src.modules.google_auth import GoogleAuthModule
from src.models import Ticket, TicketStatus
import pytest
from pathlib import Path
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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

@pytest.mark.asyncio
async def test_google_auth_real_credentials(ticket):
    """Test authentication with real credentials"""
    try:
        logger.info("\n=== Testing Google Auth with Real Credentials ===")
        
        # Initialize auth module
        auth_module = GoogleAuthModule()
        
        # Execute authentication
        result = await auth_module.execute(ticket, {})
        
        # Log the result structure
        logger.info("\nAuthentication Result:")
        logger.info(f"Success: {result.get('success')}")
        logger.info(f"Has Credentials: {'credentials' in result}")
        if 'credentials' in result:
            creds_info = result['credentials']
            logger.info(f"Credentials Valid: {creds_info.get('valid')}")
            logger.info(f"Has Refresh Token: {creds_info.get('has_refresh_token')}")
            logger.info(f"Scopes: {creds_info.get('scopes')}")
        
        # Verify result structure
        assert result["success"] is True, f"Authentication failed: {result.get('error', 'Unknown error')}"
        assert "credentials" in result, "No credentials in result"
        assert result["credentials"]["valid"] is True, "Credentials are not valid"
        assert result["credentials"]["has_refresh_token"] is True, "No refresh token"
        assert len(result["credentials"]["scopes"]) > 0, "No scopes in credentials"
        
        # Verify ticket updates
        assert ticket.step_results.get("Authenticate") == result, "Step results not stored in ticket"
        assert not ticket.errors, f"Unexpected errors in ticket: {ticket.errors}"
        
        logger.info("✓ Authentication test passed successfully")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise

@pytest.mark.asyncio
async def test_google_auth_token_reuse(ticket):
    """Test that subsequent authentications reuse the token"""
    try:
        logger.info("\n=== Testing Token Reuse ===")
        
        # First authentication
        auth_module = GoogleAuthModule()
        first_result = await auth_module.execute(ticket, {})
        assert first_result["success"] is True, "First authentication failed"
        
        # Second authentication should reuse token
        second_result = await auth_module.execute(ticket, {})
        assert second_result["success"] is True, "Second authentication failed"
        
        # Verify token reuse
        assert second_result["credentials"]["token"] == first_result["credentials"]["token"], \
            "Token was not reused"
        
        logger.info("✓ Token reuse test passed successfully")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 