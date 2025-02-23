import asyncio
import os
import json
import pickle
from datetime import datetime, timedelta
from src.modules.google_calendar import GoogleCalendarModule
from src.execution.context import ExecutionContext
from src.models.ticket import Ticket

async def test_calendar():
    try:
        # Create a test ticket
        ticket = Ticket(
            user_info={"user_id": "test_user", "channel_id": "test_channel", "thread_ts": "test_thread"},
            original_message="Schedule dinner with Gabi tomorrow at 7 PM"
        )
        
        # Create a minimal service definition
        service = {
            "name": "calendar_service",
            "description": "Test calendar service",
            "steps": [
                {
                    "name": "create_event",
                    "module": "google_calendar",
                    "action": "create_event"
                }
            ]
        }
        
        # Create execution context
        context = ExecutionContext(ticket=ticket, service=service)
        
        # Load credentials from file
        creds_path = os.environ.get('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
        with open(creds_path) as f:
            creds_data = json.load(f)
            installed = creds_data.get('installed', {})
            
        # Load token from saved file
        token_dir = os.environ.get('GOOGLE_TOKEN_DIR', '.auth_tokens')
        token_path = os.path.join(token_dir, 'google_workspace_token.pickle')
        
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
                print(f"Loaded token from {token_path}")
                
                # Set up auth result with credentials
                context.store_result(
                    step_number=1,
                    result={
                        "success": True,
                        "credentials": {
                            "token": creds.token,
                            "refresh_token": creds.refresh_token,
                            "token_uri": installed.get('token_uri'),
                            "client_id": installed.get('client_id'),
                            "client_secret": installed.get('client_secret'),
                            "scopes": creds.scopes
                        }
                    }
                )
        else:
            print(f"Token file not found at {token_path}")
            return
        
        # Set up test event details
        tomorrow = datetime.now() + timedelta(days=1)
        event_time = tomorrow.replace(hour=19, minute=0, second=0, microsecond=0)
        
        # Add test data to context
        ticket.entities = {
            "time": event_time.strftime("%H:%M"),
            "date": event_time.strftime("%Y-%m-%d"),
            "description": "Dinner with Gabi",
            "participants": ["gabi@example.com"],
            "duration": 60
        }
        
        # Create calendar module and execute
        calendar_module = GoogleCalendarModule()
        result = await calendar_module.execute(context)
        print(f"Calendar result: {result}")
        
    except Exception as e:
        print(f"Error during calendar test: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_calendar()) 