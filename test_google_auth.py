#!/usr/bin/env python3
import os
import json
import asyncio
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from pathlib import Path

# Set up logging
import logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Scopes required for Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']

async def test_auth():
    """Test Google authentication flow directly"""
    try:
        logger.info("Starting Google Auth test")
        
        # Load client configuration from credentials.json
        credentials_path = Path("credentials.json")
        if not credentials_path.exists():
            logger.error(f"Credentials file not found at {credentials_path}")
            return False
            
        with open(credentials_path, 'r') as f:
            client_config = json.load(f)
            
        logger.info(f"Loaded client config: {json.dumps(client_config, indent=2)}")
        
        # Check if we have a token file
        token_path = Path(".auth_tokens/google_workspace_token.pickle")
        creds = None
        
        if token_path.exists():
            logger.info(f"Found existing token at {token_path}")
            try:
                with open(token_path, 'rb') as token:
                    creds = Credentials.from_authorized_user_info(json.load(token), SCOPES)
            except Exception as e:
                logger.error(f"Error loading existing token: {str(e)}")
                
        # If there are no valid credentials, let's get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired credentials")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Error refreshing token: {str(e)}")
                    creds = None
            
            if not creds:
                logger.info("Starting new OAuth2 flow")
                flow = InstalledAppFlow.from_client_config(
                    client_config, 
                    SCOPES,
                    redirect_uri='http://localhost:8080'
                )
                
                # Run the flow in a separate thread to avoid blocking
                creds = await asyncio.to_thread(
                    flow.run_local_server,
                    port=8080,
                    success_message="Authentication successful! You can close this window.",
                    authorization_prompt_message="Please visit this URL to authorize this application:"
                )
                
                logger.info("Successfully obtained new credentials")
                
                # Save the credentials for the next run
                token_dir = Path(".auth_tokens")
                token_dir.mkdir(exist_ok=True)
                
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
                logger.info(f"Saved credentials to {token_path}")
        
        # At this point, we should have valid credentials
        logger.info(f"Authentication successful! Token: {creds.token[:10]}...")
        logger.info(f"Refresh token: {bool(creds.refresh_token)}")
        logger.info(f"Token valid: {creds.valid}")
        logger.info(f"Token expired: {creds.expired}")
        
        # Now let's test creating a calendar event
        await test_create_event(creds)
        
        return True
        
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        return False

async def test_create_event(creds):
    """Test creating a calendar event"""
    try:
        logger.info("Testing calendar event creation")
        
        # Build the service
        service = build('calendar', 'v3', credentials=creds)
        
        # Calculate event times
        start_time = datetime.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        # Format times for Google Calendar API
        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()
        
        # Create event details
        event = {
            'summary': 'Test Event from Python Script',
            'description': 'This is a test event created by our Python script',
            'start': {
                'dateTime': start_time_str,
                'timeZone': 'America/Los_Angeles',
            },
            'end': {
                'dateTime': end_time_str,
                'timeZone': 'America/Los_Angeles',
            },
            'attendees': [
                {'email': 'test@example.com'},
            ],
            'reminders': {
                'useDefault': True,
            },
        }
        
        # Call the Calendar API to insert the event
        logger.info("Creating event...")
        event_result = await asyncio.to_thread(
            lambda: service.events().insert(calendarId='primary', body=event).execute()
        )
        
        logger.info(f"Event created successfully: {event_result.get('htmlLink')}")
        logger.info(f"Event ID: {event_result.get('id')}")
        
        return event_result
        
    except Exception as e:
        logger.error(f"Failed to create calendar event: {str(e)}")
        return None

if __name__ == "__main__":
    # Clear existing tokens if needed
    # import shutil
    # shutil.rmtree(".auth_tokens", ignore_errors=True)
    # shutil.rmtree(".auth_tokens_backup", ignore_errors=True)
    # Path(".auth_tokens").mkdir(exist_ok=True)
    # Path(".auth_tokens_backup").mkdir(exist_ok=True)
    
    asyncio.run(test_auth()) 