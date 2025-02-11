# Office Assistant

A smart office assistant that processes requests through Slack and manages various office tasks.

## Security Notice

⚠️ **Important**: This project uses various API keys and tokens. Never commit these directly to the repository. Always use environment variables and keep your `.env` file private.

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/office-assistant.git
cd office-assistant
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your actual credentials
```

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

## Recipe Management

### Recipe Creation Process
1. **CEO Analysis**: When an unknown request is received, the CEO component analyzes it using GPT-4 and available ingredients
2. **Recipe Generation**: A new recipe is created following the standard YAML format:
   ```yaml
   name: <clear name>
   description: <clear description>
   intent: <main intent>
   common_triggers:
     - <trigger phrase 1>
     - <trigger phrase 2>
   required_entities:
     - <required entity 1>
     - <required entity 2>
   steps:
     - action: <ingredient action>
       params:
         param1: value1
   success_criteria:
     - <criterion 1>
     - <criterion 2>
   ```
3. **Validation**: The recipe is validated against available ingredients
4. **Storage**: Valid recipes are stored in `src/office/cookbook/recipes.yaml`
5. **NLP Update**: NLP processors automatically refresh their lexicons
6. **Testing**: New recipes should be tested using the test suite in `tests/test_office_flow.py`

### Recipe Testing
To test a recipe:
1. Add test cases to `tests/test_office_flow.py`
2. Include both successful and error scenarios
3. Test the complete flow:
   - NLP processing
   - Recipe matching
   - Entity collection
   - Task execution
4. Monitor the detailed logging output to verify each step

### Recipe Requirements
When creating new recipes:
1. Use only actions from `src/office/cookbook/ingredients.yaml`
2. Ensure all required fields are present
3. Provide clear success criteria
4. Include common trigger phrases
5. List all required entities

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

### Request Tracker Flow
```
User Message → FrontDesk
  ↓
Request Created
  ↓
NLP Processing → Updates intent/entities
  ↓
Cookbook Matching → Updates recipe/requirements
  ↓
[If needed] CEO Consultation → Updates priority/recipe
  ↓
Task Manager Execution → Updates status/completion
  ↓
Response to User
```

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

The system uses a comprehensive logging system with multiple log types:

### Flow Logging
- **Location**: `logs/flow_logs/`
- **Format**: `log_HHMMam_MonDD.txt` (e.g., `log_1123am_Feb11.txt`)
- **Purpose**: Tracks the complete flow of user interactions and system responses
- **Features**:
  - One log file per session
  - Clear session start header
  - Timestamped events
  - Structured component logging
  - Detailed event information
  - Error tracking

Example flow log format:
```
================================================================================
Session Started: 11:23:55 AM Feb 11, 2025
================================================================================

================================================================================
[11:23:55 AM] System - Initialization
----------------------------------------
status: initialized
components:
  - FrontDesk
  - NLPProcessor
  - CookbookManager
  - TaskManager
  - CEO
  - RequestTracker
```

### System Logging
- **Debug Log**: `logs/front_desk_debug_YYYYMMDD.log`
  - Detailed debugging information
  - Component initialization
  - State changes
  - Performance metrics

- **Error Log**: `logs/front_desk_error_YYYYMMDD.log`
  - Error tracking
  - Exception details
  - Stack traces
  - Recovery attempts

### Console Output
- Real-time status updates
- Service initialization
- Component status
- Critical errors
- User interactions

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

## Security and Credentials

The following credentials are required:

1. **Slack Configuration**
   - Bot Token (`SLACK_BOT_TOKEN`)
   - App Token (`SLACK_APP_TOKEN`)
   - Required scopes:
     - channels:manage
     - chat:write
     - channels:read
     - channels:join
     - channels:history
     - groups:history
     - im:history
     - conversations.connect:write
     - app_mentions:read
     - im:write
     - groups:read
     - mpim:history
     - mpim:write
     - users:read

2. **OpenAI Configuration**
   - API Key (`OPENAI_API_KEY`)

3. **Google Configuration**
   - Credentials file
   - Token directory
   - Required scopes for Gmail, Drive, Calendar, etc.

4. **Trello Configuration**
   - API Key
   - Token

5. **Email Configuration**
   - IMAP settings
   - App-specific password

## Environment Variables

Copy `.env.example` to `.env` and fill in your credentials. Never commit the `.env` file to version control. 