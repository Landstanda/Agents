from typing import Dict, Any, List
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from ..utils.credential_manager import CredentialManager
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import pickle

logger = get_logger(__name__)

class GoogleAuthModule(BaseModule):
    """Module for handling Google Workspace authentication"""
    
    def __init__(self):
        self.SCOPES = [
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/docs',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        self.creds = None
        self.credential_manager = CredentialManager()
        self.service_name = 'google_workspace'

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Google authentication flow"""
        try:
            # Validate credentials file
            if not self.credential_manager.validate_credentials_file():
                raise ValueError("Invalid credentials file")

            # Load existing token if available
            token_data = self.credential_manager.load_token(self.service_name)
            if token_data:
                self.creds = pickle.loads(token_data)

            # If credentials are expired or don't exist, refresh or create new ones
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    # Start OAuth2 flow with credentials file
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credential_manager.get_credentials_path(),
                        self.SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)

                # Save the credentials securely
                token_data = pickle.dumps(self.creds)
                self.credential_manager.secure_token_storage(token_data, self.service_name)

            return {
                'credentials': self.creds,
                'scopes': self.SCOPES,
                **params
            }

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        return isinstance(params, dict)

    @property
    def capabilities(self) -> List[str]:
        return ['google_auth', 'oauth2', 'credentials'] 