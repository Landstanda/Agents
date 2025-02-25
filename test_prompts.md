# AI Secretary Test Prompts

This file contains specific prompts to test the AI Secretary functionality, particularly focusing on the Google Calendar integration.

## Calendar Functionality Test Prompts

### Basic Calendar Event Creation
```
@ai-secretary Schedule a meeting called "Test Meeting" tomorrow at 2pm
```

### Calendar Event with Description
```
@ai-secretary Schedule a team meeting tomorrow at 3pm with the description "Discussing project progress and next steps"
```

### Calendar Event with Participants
```
@ai-secretary Schedule a meeting with [insert colleague email] on Friday at 10am
```

### Calendar Event with Location
```
@ai-secretary Book a meeting room for a client call next Monday at 11am at Conference Room A
```

### Calendar Event with Duration
```
@ai-secretary Schedule a 30-minute quick sync with the team tomorrow at 9am
```

### Calendar Event with All Parameters
```
@ai-secretary Schedule a 45-minute project review meeting with [insert colleague email] tomorrow at 4pm in Meeting Room B with the description "Quarterly project review to discuss milestones and blockers"
```

## Troubleshooting Prompts

### Check Authentication Status
```
@ai-secretary Check if you're connected to my Google Calendar
```

### Retry Authentication
```
@ai-secretary Please reconnect to my Google Calendar
```

## Testing Process

1. Start the AI Secretary using the `run_ai_secretary.sh` script
2. Copy and paste each prompt into the Slack channel where the bot is active
3. Verify that the bot responds appropriately
4. Check the Google Calendar to confirm events were created correctly
5. Document any issues or unexpected behavior

## Expected Behavior

For each calendar event creation prompt, the AI Secretary should:

1. Acknowledge the request
2. Process the request through the service analyzer
3. Authenticate with Google (if not already authenticated)
4. Create the calendar event with the specified parameters
5. Respond with confirmation and a link to the created event

## Error Handling Tests

If you want to test error handling, try these prompts:

```
@ai-secretary Schedule a meeting yesterday at 2pm
```
(Should fail with a past date error)

```
@ai-secretary Schedule a meeting at invalid time
```
(Should fail with an invalid time format error)

```
@ai-secretary Schedule a meeting with invalid@email.com tomorrow at 3pm
```
(Should handle invalid email gracefully) 