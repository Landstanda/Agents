from typing import Dict, Any, List
from src.core.module_interface import BaseModule
from src.utils.logging import get_logger
from src.utils.credential_manager import CredentialManager
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import pickle
import json
from googleapiclient.discovery import build
import asyncio

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
        self.credential_manager = CredentialManager()
        self.service_name = 'google_workspace'
        self.service = None
        logger.debug("✓ GoogleAuthModule initialized")

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
                raise ValueError("Token refresh failed - needs reauthorization") from e
            raise

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Google authentication flow"""
        try:
            logger.debug("\n=== Starting Google Authentication Flow ===")
            logger.debug(f"Current working directory: {os.getcwd()}")
            
            # Validate credentials file
            logger.debug("🔍 Validating credentials file...")
            try:
                creds_path = self.credential_manager.get_credentials_path()
                logger.debug(f"Credentials path: {creds_path}")
                logger.debug(f"Credentials file exists: {os.path.exists(creds_path)}")
                logger.debug(f"Credentials file permissions: {oct(os.stat(creds_path).st_mode)[-3:]}")
            except Exception as e:
                logger.error(f"Error accessing credentials file: {str(e)}")
                raise
            
            if not await self.credential_manager.validate_credentials_file():
                logger.error("❌ Invalid credentials file")
                raise ValueError("Invalid credentials file")
            logger.debug("✓ Credentials file is valid")

            # Check token directory
            token_dir = self.credential_manager.token_dir
            logger.debug(f"Token directory: {token_dir}")
            logger.debug(f"Token directory exists: {os.path.exists(token_dir)}")
            if os.path.exists(token_dir):
                logger.debug(f"Token directory permissions: {oct(os.stat(token_dir).st_mode)[-3:]}")

            # Load existing token if available
            logger.debug("🔄 Attempting to load existing token...")
            token_data = await self.credential_manager.load_token(self.service_name)
            if token_data:
                logger.debug("✓ Found existing token, deserializing...")
                try:
                    self.creds = pickle.loads(token_data)
                    logger.debug(f"Token loaded. Valid: {self.creds.valid if self.creds else False}, Expired: {self.creds.expired if self.creds else True}")
                except Exception as e:
                    logger.error(f"Error deserializing token: {str(e)}")
                    self.creds = None
            else:
                logger.debug("ℹ️ No existing token found")
                
            # If credentials are expired or don't exist, refresh or create new ones
            if not self.creds or not self.creds.valid:
                logger.debug("🔄 Credentials need refresh or creation")
                
                try:
                    if self.creds and self.creds.expired and self.creds.refresh_token:
                        logger.debug("🔄 Refreshing expired credentials...")
                        try:
                            await self._refresh_credentials(self.creds)
                            logger.debug("✓ Credentials refreshed successfully")
                        except Exception as e:
                            logger.error(f"Error refreshing credentials: {str(e)}")
                            raise
                except ValueError as e:
                    if "needs reauthorization" in str(e):
                        logger.info("🔄 Token refresh failed, starting new OAuth2 flow...")
                        self.creds = None  # Force new OAuth2 flow
                    else:
                        raise

                if not self.creds or not self.creds.valid:
                    logger.debug("🔐 Starting new OAuth2 flow...")
                    # Start OAuth2 flow with credentials file
                    creds_path = self.credential_manager.get_credentials_path()
                    logger.debug(f"Using credentials file: {creds_path}")
                    
                    if not os.path.exists(creds_path):
                        error_msg = f"Credentials file not found at: {creds_path}"
                        logger.error(f"❌ {error_msg}")
                        raise FileNotFoundError(error_msg)
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        creds_path,
                        self.SCOPES
                    )
                    
                    try:
                        # Try specific ports in case some are blocked
                        for port in [8080, 8090, 8888, 9000]:
                            try:
                                logger.info(f"🌐 Attempting to start local server on port {port}...")
                                self.creds = await self._run_local_server(flow, port)
                                logger.debug(f"✓ Successfully authenticated on port {port}")
                                break
                            except OSError as e:
                                logger.warning(f"⚠️ Port {port} failed: {str(e)}")
                                continue
                        else:
                            # If no ports worked, try random port as last resort
                            logger.info("🔄 Trying random port...")
                            self.creds = await self._run_local_server(flow, 0)
                            logger.debug("✓ Successfully authenticated on random port")
                    except Exception as e:
                        logger.error(f"❌ Failed to start local server: {str(e)}", exc_info=True)
                        raise

                # Save the credentials securely
                logger.debug("💾 Saving new credentials...")
                try:
                    token_data = pickle.dumps(self.creds)
                    await self.credential_manager.secure_token_storage(token_data, self.service_name)
                    logger.debug("✓ Credentials saved successfully")
                except Exception as e:
                    logger.error(f"Error saving credentials: {str(e)}")
                    raise

            # Verify final credential state
            logger.debug("\n=== Final Credential State ===")
            logger.debug(f"Valid: {self.creds.valid}")
            logger.debug(f"Expired: {self.creds.expired}")
            logger.debug(f"Has refresh token: {bool(self.creds.refresh_token)}")
            logger.debug(f"Scopes: {json.dumps(self.creds.scopes, indent=2)}")
            
            return {
                'success': True,
                'credentials': self.creds,
                'scopes': self.SCOPES
            }

        except Exception as e:
            logger.error(f"❌ Authentication failed: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        logger.debug(f"Validating params: {json.dumps(params, indent=2)}")
        is_valid = isinstance(params, dict)
        logger.debug(f"Params validation {'passed' if is_valid else 'failed'}")
        return is_valid

    @property
    def capabilities(self) -> List[str]:
        return ['google_auth', 'oauth2', 'credentials'] 