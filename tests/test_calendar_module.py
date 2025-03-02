#!/usr/bin/env python3
import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from src.execution.context import ExecutionContext
from src.models import Ticket
from src.modules.google_auth import GoogleAuthModule
from src.modules.google_calendar import GoogleCalendarModule

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_calendar_module():
    """Test the Google Calendar module directly"""
    try:
        logger.info("Starting Google Calendar module test")
        
        # Create a test ticket
        ticket = Ticket(
            original_message="Schedule a dinner with Gabi tomorrow night at 7",
            user_info={"user_id": "test_user"},
            channel_id="test_channel"
        )
        
        # Add entities to the ticket
        ticket.entities = {
            "time": "7pm",
            "date": "tomorrow",
            "description": "Dinner",
            "participants": "Gabi",
            "operation": "create_event"
        }
        
        # Create a mock service definition
        service_def = {
            "name": "schedule_meeting",
            "description": "Schedule a meeting on Google Calendar",
            "steps": [
                {
                    "name": "authenticate",
                    "tool": "google_auth",
                    "action": "authenticate"
                },
                {
                    "name": "create_event",
                    "tool": "google_calendar",
                    "action": "create_event"
                }
            ]
        }
        
        # Create execution context
        context = ExecutionContext(ticket=ticket, service=service_def)
        
        # First authenticate with Google
        logger.info("Authenticating with Google...")
        auth_module = GoogleAuthModule()
        auth_result = await auth_module.execute(context)
        
        logger.info(f"Auth result: {auth_result}")
        
        if not auth_result.get('success'):
            logger.error(f"Authentication failed: {auth_result.get('error')}")
            return False
        
        # Store the authentication result in the context
        context.store_result(1, auth_result, success=auth_result.get('success', False))
        
        # Initialize and execute calendar module
        logger.info("Executing calendar operation...")
        calendar_module = GoogleCalendarModule()
        result = await calendar_module.execute(context)
        
        logger.info(f"Calendar result: {result}")
        
        if result.get('success'):
            logger.info(f"✅ Event created successfully: {result.get('event_link')}")
            return True
        else:
            logger.error(f"❌ Failed to create event: {result.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"Test failed with exception: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(test_calendar_module()) 