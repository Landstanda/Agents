# Office Assistant

A smart office assistant that processes requests through Slack and manages various office tasks.

## Components

### Core Components
- **CEO**: Makes high-level decisions about how to handle requests
- **CookbookManager**: Matches requests to appropriate recipes/actions
- **FrontDesk**: Handles Slack communication and message formatting
- **NLPProcessor**: Performs quick, rule-based natural language processing

### Component Interactions
```
User (Slack) -> Front Desk -> NLP Processor -> CEO -> Cookbook Manager
                     ^                                      |
                     |                                      v
                     -------- Formatted Response -----------
```

## Features

- **Natural Language Processing**:
  - Intent detection (email, scheduling, research, etc.)
  - Entity extraction (emails, dates, numbers)
  - Urgency detection
  - Temporal context understanding
  - User context tracking

- **Slack Integration**:
  - Real-time message processing
  - Smart response formatting
  - Thread support
  - Error handling

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
   - Add necessary bot scopes:
     - chat:write
     - im:history
     - im:read
     - im:write
     - app_mentions:read

## Running the Service

Start the Front Desk service:
```bash
python run_front_desk.py
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
```

## Architecture

### Front Desk
- Handles all Slack communication
- Maintains professional tone
- Routes messages through NLP
- Formats responses for users

### NLP Processor
- Quick, rule-based text analysis
- Intent and entity extraction
- Urgency detection
- Temporal context analysis

### CEO
- High-level decision making
- Task prioritization
- Resource allocation
- Consultation management

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

- [x] Basic Slack integration
- [x] NLP processing
- [x] CEO decision making
- [x] Recipe matching
- [x] Response formatting
- [ ] Advanced error recovery
- [ ] Multi-channel support
- [ ] Analytics dashboard 