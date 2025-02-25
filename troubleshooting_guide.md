# AI Secretary Troubleshooting Guide

This guide provides steps to diagnose and fix common issues that might arise during testing of the AI Secretary.

## Common Issues and Solutions

### Slack Connection Issues

#### Bot Not Responding to Messages

1. **Check Slack Bot Token**: Ensure `SLACK_BOT_TOKEN` is correctly set in your environment.
2. **Check Slack App Token**: Ensure `SLACK_APP_TOKEN` is correctly set in your environment.
3. **Verify Bot User ID**: Check the logs to see if the bot successfully authenticated with Slack and received a bot user ID.
4. **Check Event Subscription**: Ensure the bot is subscribed to the `app_mention` event in your Slack app settings.
5. **Check Socket Mode**: Ensure Socket Mode is enabled in your Slack app settings.

#### Error in Logs: "Invalid Slack token"

1. Regenerate your Slack tokens in the Slack API dashboard.
2. Update your environment variables with the new tokens.
3. Restart the application.

### Google Authentication Issues

#### Authentication Failure

1. **Check Credentials File**: Ensure the Google credentials file exists at the path specified by `GOOGLE_CREDENTIALS_PATH`.
2. **Check Token Directory**: Ensure the `.auth_tokens` directory exists and is writable.
3. **Check Scopes**: Ensure the requested scopes match the scopes authorized in your Google Cloud project.
4. **Reauthorize**: Delete the token file in `.auth_tokens` and restart the application to trigger a new authentication flow.

#### Browser Authentication Not Working

1. Ensure you're using a machine with a graphical interface.
2. Check if the port (8080, 8090, etc.) is available and not blocked by a firewall.
3. Try running the application with a different port by modifying the `google_auth.py` file.

### Service Analyzer Issues

#### Error: "No response from GPT"

1. **Check OpenAI API Key**: Ensure `OPENAI_API_KEY` is correctly set in your environment.
2. **Check API Quota**: Verify you haven't exceeded your OpenAI API quota.
3. **Check Network**: Ensure your machine has internet access and can reach the OpenAI API.

#### Error: "Invalid JSON from GPT"

1. Check the logs for the exact response from GPT.
2. Modify the prompt in `service_analyzer.py` to be more explicit about the required JSON format.
3. Implement a more robust JSON parsing mechanism.

### Calendar Operation Issues

#### Error: "Failed to create event"

1. **Check Authentication**: Ensure you're properly authenticated with Google.
2. **Check Date/Time Format**: Ensure the date and time are in the correct format (YYYY-MM-DD and HH:MM).
3. **Check Required Parameters**: Ensure all required parameters are provided.
4. **Check Calendar Access**: Ensure the authenticated user has access to the calendar.

#### Error: "Invalid time format"

1. Check the logs for the exact time format being used.
2. Modify the time parsing logic in `google_calendar.py` to handle more time formats.
3. Ensure the time is in 24-hour format (HH:MM).

## Debugging Techniques

### Enabling Verbose Logging

To get more detailed logs, modify the logging level in `main.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change to logging.INFO for less verbose logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('ai_secretary.log')
    ]
)
```

### Checking Component Status

To check the status of various components:

1. **Slack Connection**: Look for "Office Assistant is running and connected to Slack!" in the logs.
2. **Google Authentication**: Look for "Token loaded. Valid: True" in the logs.
3. **Service Analyzer**: Look for "request_analyzed" events in the logs.
4. **Calendar Operations**: Look for "Successfully built calendar service" in the logs.

### Inspecting Token Files

To inspect the token files:

1. Check if `.auth_tokens/google_workspace_token.pickle` exists.
2. Check if there are backup tokens in `.auth_tokens_backup/`.

### Testing Individual Components

To test individual components:

1. **Google Authentication**: Run a test script that only authenticates with Google.
2. **Calendar Operations**: Run a test script that creates a calendar event directly.
3. **Service Analyzer**: Run a test script that analyzes a request without executing it.

## Creating Specific Tests

If you encounter issues with a specific functionality, create a targeted test script:

1. Create a new Python file in the `tests/` directory.
2. Import only the components needed for the test.
3. Create a simple async function that tests the specific functionality.
4. Run the test script with `python -m tests.your_test_script`.

Example test script for Google Calendar:

```python
import asyncio
import os
from src.modules.google_auth import GoogleAuthModule
from src.modules.google_calendar import GoogleCalendarModule
from src.execution.context import ExecutionContext
from src.models import Ticket

async def test_calendar():
    # Initialize auth module
    auth_module = GoogleAuthModule()
    
    # Create a test ticket
    ticket = Ticket(
        original_message="Schedule a test meeting tomorrow at 2pm",
        user_info={"user_id": "test_user"},
        channel_id="test_channel"
    )
    
    # Create execution context
    context = ExecutionContext(ticket=ticket)
    
    # Authenticate
    auth_result = await auth_module.execute(context)
    print(f"Auth result: {auth_result}")
    
    # Store auth result in context
    context.store_result(1, auth_result)
    
    # Initialize calendar module
    calendar_module = GoogleCalendarModule()
    
    # Set up entities for calendar operation
    ticket.entities = {
        "time": "14:00",
        "date": "2023-06-01",
        "description": "Test Meeting",
        "participants": [],
        "operation": "create_event"
    }
    
    # Execute calendar operation
    calendar_result = await calendar_module.execute(context)
    print(f"Calendar result: {calendar_result}")

if __name__ == "__main__":
    asyncio.run(test_calendar())
```

## Reporting Issues

When reporting issues:

1. Include the full error message and stack trace from the logs.
2. Describe the steps to reproduce the issue.
3. Include the prompt that triggered the issue.
4. Include the relevant sections of the logs.
5. Specify the environment (OS, Python version, etc.).

## Recovering from Critical Failures

If the application crashes or becomes unresponsive:

1. Stop the application (Ctrl+C).
2. Check the logs for errors.
3. Fix any identified issues.
4. Restart the application.

If the application is stuck in an authentication loop:

1. Stop the application.
2. Delete the token files in `.auth_tokens/`.
3. Restart the application and complete the authentication flow.

## Monitoring Live Tests

During live testing:

1. Keep the terminal with the application logs open.
2. Monitor the logs for errors or warnings.
3. Check the Google Calendar periodically to verify events are being created.
4. Document any issues or unexpected behavior.
5. Use the test prompts in `test_prompts.md` to systematically test functionality. 