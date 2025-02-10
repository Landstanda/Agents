# Office Assistant

A smart office assistant that processes requests through Slack and manages various office tasks.

## Components

### Core Components
- **Front Desk**: Handles Slack communication, message formatting, and direct execution of known tasks
- **NLPProcessor**: Performs quick, rule-based natural language processing and task classification
- **CEO**: Creates new recipes for unknown tasks and handles complex decision making
- **CookbookManager**: Stores and manages task recipes/actions
- **TaskManager**: Executes recipes and manages task state with priority-based processing
- **GPTClient**: Handles AI-powered decision making with fallback capabilities

### Component Interactions
```
User (Slack) -> Front Desk -> NLP Processor -> [Recipe Exists?]
                     ^            |
                     |           v
                     |     [Yes] TaskManager (Priority Queue)
                     |           |
                     |           v
                     ------- Response --------
                     |
                     |     [No] -> CEO -> [Create New Recipe]
                     |                          |
                     |                          v
                     |                    CookbookManager
                     |                          |
                     |                          v
                     -------- Response ----------
```

## Features

- **Intelligent Task Routing**:
  - Automatic recognition of known vs unknown tasks
  - Direct execution path for existing recipes
  - Complex task handling through CEO
  - Recipe creation and storage for future use
  - Priority-based task execution with urgency levels
  - FIFO ordering for equal-priority tasks

- **Natural Language Processing**:
  - Intent detection (email, scheduling, research, etc.)
  - Entity extraction (emails, dates, numbers)
  - Task complexity assessment
  - Recipe matching
  - Temporal context understanding
  - User context tracking
  - Urgency detection and prioritization

- **Slack Integration**:
  - Real-time message processing via Socket Mode
  - Smart response formatting
  - Thread support
  - Comprehensive error handling
  - Channel management
  - Error recovery and graceful degradation

- **Task Management**:
  - Recipe-based task matching
  - Multi-step task handling
  - Priority-based processing
  - Consultation detection
  - Error task handling and recovery
  - Task history tracking
  - Concurrent task processing

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

# Test integration flows
python -m pytest tests/test_integration_flows.py
```

### Test Coverage

The test suite includes:
- Unit tests for all components
- Integration tests for component interactions
- Flow tests for end-to-end scenarios
- Error handling and recovery tests
- Priority queue and task ordering tests
- Concurrency and race condition tests

## Architecture

### Front Desk
- Handles all Slack communication via Socket Mode
- Maintains professional tone
- Routes messages through NLP
- Formats responses for users
- Handles message deduplication
- Manages error recovery and retries

### NLP Processor
- Quick, rule-based text analysis
- Intent and entity extraction
- Urgency detection
- Temporal context analysis
- Priority assessment

### CEO
- High-level decision making with GPT integration
- Task prioritization
- Resource allocation
- Consultation management
- Fallback handling when GPT is unavailable

### Task Manager
- Priority-based task queue
- FIFO ordering for equal priorities
- Concurrent task processing
- Error handling and recovery
- Task history tracking
- Resource management

### Cookbook Manager
- Recipe matching
- Task decomposition
- Capability tracking
- Success criteria management
- Recipe validation

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
- [x] Priority-based task processing
- [x] Task history tracking
- [x] Error task handling
- [ ] Analytics dashboard
- [ ] Voice command support 