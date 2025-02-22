import os
from pathlib import Path
from typing import Optional, Dict, Any
import json
from dotenv import load_dotenv
import logging
import aiofiles
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

logger = logging.getLogger(__name__)

class CredentialManager:
    """Secure credential management utility"""
    
    def __init__(self):
        """Initialize the credential manager"""
        logger.debug("\n=== Initializing Credential Manager ===")
        
        # Load environment variables from .env file
        load_dotenv()
        logger.debug("Loaded environment variables")
        
        # Set up secure paths
        self.credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
        self.token_dir = os.getenv('GOOGLE_TOKEN_DIR', os.path.expanduser('~/.auth_tokens'))
        
        logger.debug(f"Credentials path: {self.credentials_path}")
        logger.debug(f"Token directory: {self.token_dir}")
        
        # Define scopes for different services
        self.scopes = {
            'gmail': ['https://www.googleapis.com/auth/gmail.modify'],
            'calendar': ['https://www.googleapis.com/auth/calendar'],
            'drive': ['https://www.googleapis.com/auth/drive.file']
        }
        
        # Create token directory if it doesn't exist
        if not os.path.exists(self.token_dir):
            logger.debug(f"Creating token directory: {self.token_dir}")
            try:
                os.makedirs(self.token_dir, mode=0o700)  # Secure permissions
                logger.debug("✓ Token directory created with secure permissions")
            except Exception as e:
                logger.error(f"Failed to create token directory: {str(e)}")
                raise
        else:
            logger.debug("Token directory already exists")
            
    def get_credentials_path(self) -> str:
        """Get the path to the credentials file"""
        logger.debug("Getting credentials path...")
        
        if not self.credentials_path:
            error_msg = "GOOGLE_CREDENTIALS_PATH not set in environment"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if not os.path.exists(self.credentials_path):
            error_msg = f"Credentials file not found at {self.credentials_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        logger.debug(f"✓ Found credentials at: {self.credentials_path}")
        return self.credentials_path
        
    def get_token_path(self, service_name: str) -> str:
        """Get the path for a specific service's token file"""
        token_path = os.path.join(self.token_dir, f"{service_name}_token.pickle")
        logger.debug(f"Token path for {service_name}: {token_path}")
        return token_path
    
    async def validate_credentials_file(self) -> bool:
        """Validate the credentials file format and content"""
        logger.debug("Validating credentials file...")
        try:
            creds_path = self.get_credentials_path()
            async with aiofiles.open(creds_path, 'r') as f:
                creds_data = json.loads(await f.read())
                
            required_fields = ['client_id', 'client_secret', 'auth_uri', 'token_uri']
            is_valid = all(field in creds_data.get('installed', {}) for field in required_fields)
            
            if is_valid:
                logger.debug("✓ Credentials file is valid")
            else:
                logger.error("❌ Invalid credentials file format")
                missing_fields = [field for field in required_fields if field not in creds_data.get('installed', {})]
                logger.error(f"Missing fields: {missing_fields}")
                
            return is_valid
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid credentials file format: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error validating credentials: {str(e)}")
            return False
    
    async def secure_token_storage(self, token_data: bytes, service_name: str) -> None:
        """Securely store token data"""
        token_path = self.get_token_path(service_name)
        logger.debug(f"Storing token for {service_name} at {token_path}")
        
        try:
            # Write with secure permissions
            async with aiofiles.open(token_path, 'wb') as f:
                os.chmod(token_path, 0o600)  # Read/write for owner only
                await f.write(token_data)
            logger.debug("✓ Token stored successfully")
                
        except Exception as e:
            logger.error(f"Failed to store token: {str(e)}")
            raise
            
    async def load_token(self, service_name: str) -> Optional[bytes]:
        """Load token data if it exists"""
        token_path = self.get_token_path(service_name)
        logger.debug(f"Loading token for {service_name} from {token_path}")
        
        if os.path.exists(token_path):
            try:
                async with aiofiles.open(token_path, 'rb') as f:
                    token_data = await f.read()
                logger.debug("✓ Token loaded successfully")
                return token_data
            except Exception as e:
                logger.error(f"Failed to load token: {str(e)}")
                raise
        else:
            logger.debug("No existing token found")
        return None

    async def get_credentials(self, service_name: str) -> Credentials:
        """Get valid credentials for a Google API service"""
        if service_name not in self.scopes:
            raise ValueError(f"Unknown service: {service_name}")
            
        creds = None
        token_path = self.get_token_path(service_name)
        
        # Load existing token
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials available, refresh or get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Load client secrets
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.get_credentials_path(),
                    self.scopes[service_name]
                )
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for future use
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        return creds 