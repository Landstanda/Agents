# Office Assistant

A smart office assistant that processes requests through Slack and manages various office tasks.

## Components

### Core Components
- **CEO**: Makes high-level decisions about how to handle requests
- **CookbookManager**: Matches requests to appropriate recipes/actions
- **FrontDesk**: Handles Slack communication and message formatting
- **NLPProcessor**: Performs quick, rule-based natural language processing
- **GPTClient**: Handles AI-powered decision making with fallback capabilities

### Component Interactions
```
User (Slack) -> Front Desk -> NLP Processor -> CEO -> Cookbook Manager
                     ^                            |
                     |                           v
                     -------- Response ----------
```

## Features

- **Socket Mode Integration**:
  - Real-time event processing
  - Automatic reconnection handling
  - Thread support
  - Message deduplication

- **Natural Language Processing**:
  - Intent detection (email, scheduling, research, etc.)
  - Entity extraction (emails, dates, numbers)
  - Urgency detection
  - Temporal context understanding
  - User context tracking

- **Slack Integration**:
  - Real-time message processing via Socket Mode
  - Smart response formatting
  - Thread support
  - Comprehensive error handling
  - Channel management

- **Task Management**:
  - Recipe-based task matching
  - Multi-step task handling
  - Priority-based processing
  - Consultation detection

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables in `.env`:
```
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_APP_TOKEN=xapp-your-token
OPENAI_API_KEY=your-openai-key
```

3. Configure your Slack app:
   - Enable Socket Mode
   - Subscribe to these events:
     - message.channels
     - message.groups
     - app_mention
   - Add necessary bot scopes:
     - chat:write
     - channels:history
     - channels:join
     - channels:read
     - groups:history
     - app_mentions:read

## Running the Service

Start the Front Desk service:
```bash
python run_front_desk.py
```

For testing Socket Mode specifically:
```bash
python test_socket_mode.py
```

## Testing

Run the test suite:
```bash
python -m pytest tests/
```

Run specific test modules:
```bash
# Test NLP processor
python -m pytest tests/test_nlp_processor.py

# Test Front Desk
python -m pytest tests/test_front_desk.py

# Test CEO responses
python -m pytest tests/test_ceo_responses.py
```

## Architecture

### Front Desk
- Handles all Slack communication via Socket Mode
- Maintains professional tone
- Routes messages through NLP
- Formats responses for users
- Handles message deduplication

### NLP Processor
- Quick, rule-based text analysis
- Intent and entity extraction
- Urgency detection
- Temporal context analysis

### CEO
- High-level decision making with GPT integration
- Task prioritization
- Resource allocation
- Consultation management
- Fallback handling when GPT is unavailable

### Cookbook Manager
- Recipe matching
- Task decomposition
- Capability tracking
- Success criteria management

## Logging

Logs are written to:
- Console (INFO level)
- front_desk.log (DEBUG level)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## Development Status

- [x] Socket Mode integration
- [x] NLP processing
- [x] CEO decision making
- [x] Recipe matching
- [x] Response formatting
- [x] Error recovery
- [x] Thread support
- [ ] Analytics dashboard
- [ ] Voice command support 