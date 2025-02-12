#!/usr/bin/env python3

from src.modules.google_auth import GoogleAuthModule
from src.utils.logging import get_logger

logger = get_logger(__name__)

def test_auth():
    """Test Google authentication setup"""
    try:
        logger.info("Initializing Google Auth Module...")
        auth_module = GoogleAuthModule()
        
        logger.info("Attempting authentication...")
        result = auth_module.execute({})
        
        if result['credentials'] and result['credentials'].valid:
            logger.info("✓ Authentication successful!")
            logger.info("✓ Token stored securely in .auth_tokens directory")
            logger.info("✓ The following scopes were authorized:")
            for scope in result['scopes']:
                logger.info(f"  - {scope}")
        else:
            logger.error("Authentication failed - credentials invalid")
            
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        logger.info("This might be because the API is not yet activated. Try again in a few minutes.")
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        
if __name__ == "__main__":
    test_auth() 