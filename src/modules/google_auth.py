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
        """Get client configuration from environment variables"""
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
            token_data = self.token_manager.load_token(self.service_name)
            if token_data:
                logger.debug("✓ Found existing token, deserializing...")
                try:
                    self.creds = token_data
                    logger.debug(f"Token loaded. Valid: {self.creds.valid}, Expired: {self.creds.expired}")
                except Exception as e:
                    logger.error(f"Error deserializing token: {str(e)}")
                    self.creds = None
            else:
                logger.debug("ℹ️ No existing token found")
                
            # If credentials are expired or don't exist, refresh or create new ones
            if not self.creds or not self.creds.valid:
                logger.debug("🔄 Credentials need refresh or creation")
                
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logger.debug("🔄 Refreshing expired credentials...")
                    try:
                        await self._refresh_credentials(self.creds)
                        if self.creds:
                            logger.debug("✓ Credentials refreshed successfully")
                        else:
                            logger.info("🔄 Token refresh failed, starting new OAuth2 flow...")
                    except Exception as e:
                        logger.error(f"Error refreshing credentials: {str(e)}")
                        self.creds = None

                if not self.creds or not self.creds.valid:
                    logger.debug("🔐 Starting new OAuth2 flow...")
                    # Start OAuth2 flow with client config from env
                    client_config = self._get_client_config()
                    
                    try:
                        # Try specific ports in case some are blocked
                        for port in [8080, 8090, 8888, 9000]:
                            try:
                                logger.info(f"🌐 Attempting to start local server on port {port}...")
                                flow = InstalledAppFlow.from_client_config(
                                    client_config,
                                    self.SCOPES
                                )
                                self.creds = await self._run_local_server(flow, port)
                                logger.debug(f"✓ Successfully authenticated on port {port}")
                                break
                            except OSError as e:
                                logger.warning(f"⚠️ Port {port} failed: {str(e)}")
                                continue
                        else:
                            # If no ports worked, try random port as last resort
                            logger.info("🔄 Trying random port...")
                            flow = InstalledAppFlow.from_client_config(
                                client_config,
                                self.SCOPES
                            )
                            self.creds = await self._run_local_server(flow, 0)
                            logger.debug("✓ Successfully authenticated on random port")
                    except Exception as e:
                        error = f"Failed to start local server: {str(e)}"
                        context.store_result(1, None, success=False, error=error)
                        return {"success": False, "error": error}

                # Save the credentials securely
                logger.debug("💾 Saving new credentials...")
                try:
                    self.token_manager.store_token(self.service_name, self.creds)
                    logger.debug("✓ Credentials saved successfully")
                except Exception as e:
                    logger.warning(f"Warning: Error saving credentials: {str(e)}")
                    # Continue even if saving fails - we still have valid credentials in memory

            # Create result with credential state
            result = {
                "success": True,
                "credentials": self.creds,  # Include the actual credentials object
                "credential_info": {  # Move credential info to a separate key
                    "valid": self.creds.valid,
                    "expired": self.creds.expired,
                    "has_refresh_token": bool(self.creds.refresh_token),
                    "scopes": self.creds.scopes,
                    "token": self.creds.token,
                    "refresh_token": bool(self.creds.refresh_token),
                    "token_uri": self.creds.token_uri,
                    "client_id": self.creds.client_id,
                    "client_secret": "[REDACTED]"
                },
                "scopes": self.SCOPES
            }
            
            # Store result in context
            context.store_result(1, result, success=True)
            return result

        except Exception as e:
            error = f"Authentication failed: {str(e)}"
            context.store_result(1, None, success=False, error=error)
            return {"success": False, "error": error}

    @property
    def capabilities(self) -> List[str]:
        return ['google_auth', 'oauth2', 'credentials'] 