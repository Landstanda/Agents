import asyncio
import os
from src.modules.google_auth import GoogleAuthModule
from src.execution.context import ExecutionContext
from src.models import Ticket

async def test_auth():
    # Create a test ticket
    ticket = Ticket(ticket_id="test_auth", original_message="Test auth")
    
    # Create execution context
    context = ExecutionContext(ticket, {"name": "test_service"})
    
    # Initialize Google Auth module
    auth_module = GoogleAuthModule()
    
    try:
        # Execute auth flow
        result = await auth_module.execute(context)
        print("Auth result:", result)
    except Exception as e:
        print("Error during auth:", str(e))

if __name__ == "__main__":
    asyncio.run(test_auth()) 