import pytest
import asyncio
import os
import json
from pathlib import Path
from typing import Generator
from src.core.agent import BaseAgent
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Google API scopes for testing
SCOPES = ['https://www.googleapis.com/auth/calendar']

def pytest_configure(config):
    """Configure pytest with asyncio markers"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
async def google_auth_token():
    """Set up Google authentication token once for the entire test session."""
    token_path = Path(".auth_tokens/google_workspace_token.pickle")
    token_dir = Path(".auth_tokens")
    token_dir.mkdir(exist_ok=True)
    
    # Check if we have a valid token
    creds = None
    if token_path.exists():
        try:
            with open(token_path, 'r') as f:
                token_data = json.load(f)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as e:
            print(f"Error loading token: {str(e)}")
    
    # If no valid credentials, create new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Load client configuration from credentials.json
            credentials_path = Path("credentials.json")
            if not credentials_path.exists():
                raise FileNotFoundError(f"Credentials file not found at {credentials_path}")
                
            with open(credentials_path, 'r') as f:
                client_config = json.load(f)
            
            # Create and run the flow
            flow = InstalledAppFlow.from_client_config(
                client_config, 
                SCOPES,
                redirect_uri='http://localhost:8080'
            )
            
            # This will open a browser window for authentication
            # It should only happen once per test session
            creds = await asyncio.to_thread(
                flow.run_local_server,
                port=8080,
                success_message="Authentication successful! You can close this window.",
                authorization_prompt_message="Please visit this URL to authorize this application:"
            )
        
        # Save the credentials for the rest of the tests
        token_info = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        
        with open(token_path, 'w') as token:
            json.dump(token_info, token)
        print(f"✓ Credentials saved to {token_path}")
    
    return creds

@pytest.fixture
async def agent(event_loop):
    """Create and initialize a BaseAgent instance"""
    agent = BaseAgent()
    await agent.initialize()
    return agent 