from typing import Dict, Any, List
from src.core.module_interface import BaseModule
from src.execution.context import ExecutionContext
from src.utils.logging import get_logger
from src.utils.token_manager import TokenManager
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import json
import asyncio
from pathlib import Path

logger = get_logger(__name__)

class GoogleAuthModule(BaseModule):
    """Module for handling Google Workspace authentication"""
    
    def __init__(self):
        logger.debug("\n=== Initializing Google Auth Module ===")
        self.SCOPES = [
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/docs',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        logger.debug(f"🔐 Requested scopes: {json.dumps(self.SCOPES, indent=2)}")
        self.creds = None
        self.token_manager = TokenManager()
        self.service_name = 'google_workspace'
        self.service = None
        logger.debug("✓ GoogleAuthModule initialized")

    def _get_client_config(self) -> Dict[str, Any]:
        """Get client configuration from credentials file or environment variables"""
        # First try to load from credentials.json file
        credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        if os.path.exists(credentials_path):
            try:
                with open(credentials_path, 'r') as f:
                    logger.debug(f"Loading client config from {credentials_path}")
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading credentials from {credentials_path}: {str(e)}")
                
        # Fall back to environment variables
        logger.debug("Falling back to environment variables for client config")
        return {
            "installed": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "project_id": os.getenv("GOOGLE_PROJECT_ID"),
                "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
                "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
                "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_CERT_URL"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uris": os.getenv("GOOGLE_REDIRECT_URIS", "http://localhost").split(",")
            }
        }

    async def _run_local_server(self, flow, port):
        """Run local server in a thread pool"""
        return await asyncio.to_thread(
            flow.run_local_server,
            port=port,
            success_message="Authentication successful! You can close this window.",
            authorization_prompt_message="Please visit this URL to authorize this application:"
        )

    async def _refresh_credentials(self, creds):
        """Refresh credentials in a thread pool"""
        try:
            return await asyncio.to_thread(creds.refresh, Request())
        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            if "invalid_grant" in str(e):
                self.creds = None  # Clear invalid credentials
                return None  # Return None to trigger reauthorization
            raise

    async def execute(self, context: ExecutionContext, **params) -> Dict[str, Any]:
        """Handle Google authentication flow"""
        try:
            logger.debug("\n=== Starting Google Authentication Flow ===")
            logger.debug(f"Current working directory: {os.getcwd()}")
            
            # Load existing token if available
            logger.debug("🔄 Attempting to load existing token...")
            
            # First try to load from the same location as our test script
            token_path = Path(".auth_tokens/google_workspace_token.pickle")
            if token_path.exists():
                logger.debug(f"✓ Found existing token at {token_path}")
                try:
                    with open(token_path, 'r') as f:
                        token_data = json.load(f)
                    self.creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)
                    logger.debug(f"Token loaded directly. Valid: {self.creds.valid}, Expired: {self.creds.expired}")
                    
                    # If token is expired but has refresh token, refresh it
                    if self.creds and self.creds.expired and self.creds.refresh_token:
                        logger.debug("🔄 Refreshing expired credentials")
                        await self._refresh_credentials(self.creds)
                        
                        # Save the refreshed credentials
                        if self.creds and self.creds.valid:
                            token_info = {
                                'token': self.creds.token,
                                'refresh_token': self.creds.refresh_token,
                                'token_uri': self.creds.token_uri,
                                'client_id': self.creds.client_id,
                                'client_secret': self.creds.client_secret,
                                'scopes': self.creds.scopes
                            }
                            
                            with open(token_path, 'w') as token:
                                json.dump(token_info, token)
                            logger.debug(f"✓ Refreshed credentials saved to {token_path}")
                            
                            # Also save via TokenManager for backup
                            self.token_manager.store_token(self.service_name, self.creds)
                            logger.debug("✓ Refreshed credentials also saved via TokenManager")
                except Exception as e:
                    logger.error(f"Error loading token directly: {str(e)}")
                    self.creds = None
            
            # If still no valid credentials, try TokenManager
            if not self.creds or not self.creds.valid:
                # Fall back to TokenManager
                token_data = self.token_manager.load_token(self.service_name)
                if token_data:
                    logger.debug("✓ Found existing token via TokenManager, deserializing...")
                    try:
                        self.creds = token_data
                        logger.debug(f"Token loaded. Valid: {self.creds.valid}, Expired: {self.creds.expired}")
                        
                        # If token is expired but has refresh token, refresh it
                        if self.creds and self.creds.expired and self.creds.refresh_token:
                            logger.debug("🔄 Refreshing expired credentials from TokenManager")
                            await self._refresh_credentials(self.creds)
                            
                            # Save the refreshed credentials
                            if self.creds and self.creds.valid:
                                self.token_manager.store_token(self.service_name, self.creds)
                                logger.debug("✓ Refreshed credentials saved via TokenManager")
                                
                                # Also save to file for test compatibility
                                token_info = {
                                    'token': self.creds.token,
                                    'refresh_token': self.creds.refresh_token,
                                    'token_uri': self.creds.token_uri,
                                    'client_id': self.creds.client_id,
                                    'client_secret': self.creds.client_secret,
                                    'scopes': self.creds.scopes
                                }
                                
                                with open(token_path, 'w') as token:
                                    json.dump(token_info, token)
                                logger.debug(f"✓ Refreshed credentials also saved to {token_path}")
                    except Exception as e:
                        logger.error(f"Error deserializing token: {str(e)}")
                        self.creds = None
                else:
                    logger.debug("ℹ️ No existing token found")
                
            # If credentials are expired or don't exist, refresh or create new ones
            if not self.creds or not self.creds.valid:
                logger.debug("🔄 Credentials need refresh or creation")
                
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logger.debug("🔄 Refreshing expired credentials")
                    await self._refresh_credentials(self.creds)
                else:
                    logger.debug("🔐 Starting new OAuth2 flow...")
                    
                    # Get client configuration
                    client_config = self._get_client_config()
                    
                    # Create OAuth2 flow
                    flow = InstalledAppFlow.from_client_config(
                        client_config, 
                        self.SCOPES,
                        redirect_uri='http://localhost:8080'
                    )
                    
                    # Try different ports for local server
                    ports = [8080, 8090, 8888, 9000]
                    for port in ports:
                        try:
                            logger.info(f"🌐 Attempting to start local server on port {port}...")
                            self.creds = await self._run_local_server(flow, port)
                            break
                        except OSError as e:
                            logger.warning(f"⚠️ Port {port} failed: {str(e)}")
                            continue
                    
                    # If all ports failed, try random port
                    if not self.creds:
                        logger.info("🔄 Trying random port...")
                        self.creds = await self._run_local_server(flow, 0)  # 0 means random port
                    
                    # Save the new credentials
                    if self.creds:
                        logger.debug("💾 Saving new credentials...")
                        
                        # Create token directory if it doesn't exist
                        token_dir = Path(".auth_tokens")
                        token_dir.mkdir(exist_ok=True)
                        
                        # Save token to file for test compatibility
                        token_info = {
                            'token': self.creds.token,
                            'refresh_token': self.creds.refresh_token,
                            'token_uri': self.creds.token_uri,
                            'client_id': self.creds.client_id,
                            'client_secret': self.creds.client_secret,
                            'scopes': self.creds.scopes
                        }
                        
                        with open(token_path, 'w') as token:
                            json.dump(token_info, token)
                        logger.debug(f"✓ Credentials saved to {token_path}")
                        
                        # Also save via TokenManager for backup
                        self.token_manager.store_token(self.service_name, self.creds)
                        logger.debug("✓ Credentials also saved via TokenManager")
                        
            # If we still don't have valid credentials, authentication failed
            if not self.creds or not self.creds.valid:
                error_msg = "Failed to obtain valid credentials"
                logger.error(f"❌ {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # Prepare credential info for context
            credential_info = {
                'valid': self.creds.valid,
                'expired': self.creds.expired,
                'has_refresh_token': bool(self.creds.refresh_token),
                'scopes': self.creds.scopes,
                'token': self.creds.token[:50] + '...' if self.creds.token else None,
                'refresh_token': bool(self.creds.refresh_token),
                'token_uri': self.creds.token_uri,
                'client_id': self.creds.client_id,
                'client_secret': '[REDACTED]'
            }
            
            # Store credentials in context for other modules to use
            context.set_variable('google_credentials', self.creds)
            context.set_variable('google_credential_info', credential_info)
            
            return {
                'success': True,
                'credentials': self.creds,
                'credential_info': credential_info,
                'scopes': self.SCOPES
            }
            
        except Exception as e:
            error_msg = f"Authentication failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }

    @property
    def capabilities(self) -> List[str]:
        return ['google_auth', 'oauth2', 'credentials'] 