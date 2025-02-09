import os
from pathlib import Path
from typing import Optional, Dict
import json
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

class CredentialManager:
    """Secure credential management utility"""
    
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()
        
        # Set up secure paths
        self.credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
        self.token_dir = os.getenv('GOOGLE_TOKEN_DIR', os.path.expanduser('~/.auth_tokens'))
        
        # Create token directory if it doesn't exist
        if not os.path.exists(self.token_dir):
            os.makedirs(self.token_dir, mode=0o700)  # Secure permissions
            
    def get_credentials_path(self) -> str:
        """Get the path to the credentials file"""
        if not self.credentials_path:
            raise ValueError("GOOGLE_CREDENTIALS_PATH not set in environment")
        
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(f"Credentials file not found at {self.credentials_path}")
            
        return self.credentials_path
        
    def get_token_path(self, service_name: str) -> str:
        """Get the path for a specific service's token file"""
        return os.path.join(self.token_dir, f"{service_name}_token.pickle")
    
    def validate_credentials_file(self) -> bool:
        """Validate the credentials file format and content"""
        try:
            creds_path = self.get_credentials_path()
            with open(creds_path, 'r') as f:
                creds_data = json.load(f)
                
            required_fields = ['client_id', 'client_secret', 'auth_uri', 'token_uri']
            return all(field in creds_data.get('installed', {}) for field in required_fields)
            
        except json.JSONDecodeError:
            logger.error("Invalid credentials file format")
            return False
        except Exception as e:
            logger.error(f"Error validating credentials: {str(e)}")
            return False
    
    def secure_token_storage(self, token_data: bytes, service_name: str) -> None:
        """Securely store token data"""
        token_path = self.get_token_path(service_name)
        
        # Write with secure permissions
        with open(token_path, 'wb') as f:
            os.chmod(token_path, 0o600)  # Read/write for owner only
            f.write(token_data)
            
    def load_token(self, service_name: str) -> Optional[bytes]:
        """Load token data if it exists"""
        token_path = self.get_token_path(service_name)
        
        if os.path.exists(token_path):
            with open(token_path, 'rb') as f:
                return f.read()
        return None 