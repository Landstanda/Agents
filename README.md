# AI Secretary

An intelligent AI-powered secretary that can automate any computer-based task through natural language requests via Slack.

## Overview

AI Secretary can automonously perform many tasks on a computer when prompted with natural language requests. It's designed to break a request down into steps and then uses the service index to match those steps with services offered. It then uses a series of task modules to execute the request. It troubleshoots errors, dynamically seeks solutions, and politely reports upon success, failure, and when it determines if it requires more information from the user.

### How it works

A message comes in from slack, the initial data is recorded by the Ticket and past to the Service Analyzer, which compiles the message in a prompt that includes the Service Index. This is passed to a GPT with instructions to break the request down in to steps, match those steps with services, and return the result in a JSON object. The Ticket is updated and passed to the Agent who uses the Service Definitions as a guide in how to execute each service, step by step according to the GPT, utilizing task modules.  When there is success, the Agent signals the Message Maker to notify the user. If the agent fails to accomplish the chain, the information is passed back to the Service Analyzer for either a new chain, or to signal the Message Maker to notify the user that it failed or it needs more info.

## Architecture

The system consists of core components that work together to process and execute user requests. Here is the enhanced flow of a successful request:

```
                                    +----------------+
                                    |     Slack     |
                                    |   Interface   |
                                    +-------+-------+
                                            |
                                    +-------v-------+
                                    |   Service     |
                                    |   Analyzer    |
                                    +-------+-------+
                                            |
                                    +-------v-------+
                                    |     Agent     |
                                    |   (Core)      |
                                    +-------+-------+
                                            |
                              +-------------+-------------+
                              |                          |
                       +------v------+            +------v------+
                       |   Tool      |            |  Service    |
                       | Registry    |            |  Registry   |
                       +------+------+            +------+------+
                              |                          |
                              |                    +-----v------+
                              |                    |  Service   |
                              |                    | Executor   |
                              |                    +-----+------+
                              |                          |
                              +-------------+------------+
                                           |
                                    +------v------+
                                    |   Tools     |
                                    | Execution   |
                                    +------+------+
                                           |
                                    +------v------+
                                    |  Message    |
                                    |   Maker     |
                                    +------+------+
                                           |
                                    +------v------+
                                    |    User     |
                                    +-------------+
```

### Service File Structure

The system uses two main files for service definitions:

1. **Service Index** (`src/services/service_index.json`):
   - Used by GPT for understanding and breaking down user requests
   - Contains high-level service information and examples
   - Example format:
```json
{
    "service_name": {
        "name": "Human-Readable Name",
        "description": "Detailed description of what the service does",
        "examples": [
            "Example request 1",
            "Example request 2"
        ],
        "combination_examples": [
            {
                "request": "Complex request example",
                "services": [
                    {
                        "service1": "Why this service is needed"
                    },
                    {
                        "service2": "Purpose in this combination"
                    }
                ]
            }
        ],
        "required_entities": [
            "entity1",
            "entity2"
        ],
        "optional_entities": [
            "optional1",
            "optional2"
        ],
        "outputs": [
            "Output 1 description",
            "Output 2 description"
        ]
    }
}
```

2. **Service Definitions** (`src/services/service_definitions.yaml`):
   - Used by Agent for executing services
   - Contains technical implementation details and error handling
   - Example format:
```yaml
service_name:
  name: "Service Name"
  required_entities:
    - entity1
    - entity2
  optional_entities:
    - optional1
    - optional2
    - optional3
    - optional4
  steps:
    - name: "Step Name"
      tool: tool_name
      action: execute
      params: {}
      on_success:
        - condition: "response.get('success')"
          next_step: next_step_id
      on_error:
        - action: "retry"
          max_attempts: 3

    - name: "Next Step"
      tool: another_tool
      id: next_step_id
      action: execute
      params:
        operation: "operation_name"
        param1: "{entity1}"
        param2: "{entity2 if entity2 else 'default'}"
      on_success:
        - condition: "response.get('success') and response.get('data')"
          next_step: complete
      on_error:
        - condition: "error.get('type') == 'specific_error'"
          action: "specific_action"
        - condition: "error.get('type') == 'auth_error'"
          action: "retry"
          next_step: "authenticate"
        - action: "notify_error"

  success_criteria:
    - "response.get('success')"
    - "response.get('data')"
  error_handling:
    retry_count: 3
    delay_seconds: 5
    conditions:
      network_error: true
      rate_limit: true
```

### Core Components

1. **Agent Core** (`src/core/agent/`)
   - Base agent interface and implementation
   - Service execution coordination
   - State management
   - Error handling and recovery

2. **Service Registry** (`src/core/registry/services.py`)
   - Manages service definitions and versions
   - Validates service configurations
   - Handles service dependencies
   - Supports service versioning

3. **Tool Registry** (`src/core/registry/tools.py`)
   - Dynamic tool loading and validation
   - Capability-based tool matching
   - Tool dependency management
   - Runtime tool validation

4. **Service Executor** (`src/core/agent/executor.py`)
   - Handles step-by-step execution
   - Manages execution context
   - Provides error recovery
   - Handles parallel execution

5. **Execution Context** (`src/execution/context.py`)
   - Manages execution state
   - Handles variable storage and retrieval
   - Tracks execution progress
   - Stores step results

6. **Service Analyzer** (`src/tools/service_analyzer.py`)
   - Uses GPT for request analysis
   - Matches requests to services
   - Handles missing information
   - Creates execution plans

7. **Message Maker** (`src/tools/message_maker.py`)
   - Generates user responses
   - Handles error messages
   - Manages conversation flow
   - Formats execution results

### Ticket System

The Ticket system (`src/models/ticket.py`) is a fundamental component that acts as the central state manager for request processing. It maintains the complete lifecycle of a user request from initial message to final response.

#### Ticket Structure
1. **Core Identification**
   - Unique ticket ID
   - Creation timestamp
   - User and channel information
   - Thread tracking for multi-message conversations

2. **Request Processing State**
   - Original message
   - Identified intent
   - Selected service
   - Required and provided entities (parameters)
   - Missing entity tracking
   - Current status (CREATED, ANALYZING, EXECUTING, etc.)

3. **Conversation Management**
   - Tracks both incoming (user) and outgoing (assistant) messages
   - Maintains conversation history with timestamps
   - Stores message metadata and context

4. **Execution Tracking**
   - Complete execution plan with ordered steps
   - Step-by-step results
   - Error history with types and descriptions
   - Created service records
   - Final execution results

#### Status Lifecycle
```
CREATED → ANALYZING → EXECUTING → COMPLETED
                   ↘ WAITING_INPUT ↗
                   ↘ SERVICE_CREATION ↗
                   ↘ ERROR
```

#### Key Features
1. **State Management**
   - Maintains consistent state across all system components
   - Tracks progress through the execution pipeline
   - Records all state changes and events

2. **Error Handling**
   - Captures and categorizes errors
   - Maintains error history
   - Supports retry mechanisms
   - Tracks failed services and steps

3. **Multi-Message Support**
   - Handles conversation threads
   - Maintains context across multiple messages
   - Supports incremental information gathering

4. **Data Persistence**
   - Serializable to/from dictionary format
   - Supports ticket reconstruction
   - Maintains complete audit trail

5. **Component Integration**
   - Provides interfaces for each system component
   - Ensures data consistency
   - Facilitates component communication
   - Controls access to ticket data

#### Usage Example
```python
# Ticket lifecycle example
ticket = Ticket(
    user_info={"user_id": "U123", "channel_id": "C456"},
    original_message="Schedule a meeting with John tomorrow"
)

# Status updates as request processes
ticket.update_status(TicketStatus.ANALYZING)
ticket.add_incoming_message("What time should I schedule it for?")
ticket.update_status(TicketStatus.WAITING_INPUT)
ticket.add_outgoing_message("What time would you like the meeting?")
ticket.add_incoming_message("3 PM")
ticket.update_status(TicketStatus.EXECUTING)
ticket.add_execution_step({"step": "create_calendar_event", ...})
ticket.store_step_result(1, {"status": "success", ...})
ticket.update_status(TicketStatus.COMPLETED)
```

### System Flows

1. **Basic Request Flow**:
```
User → Service Analyzer → Agent Core → Tool Registry → Service Executor → Tools → Message Maker → User
     └── Request      └── Analyze    └── Coordinate └── Load Tools  └── Execute    └── Run   └── Respond
```

2. **Service Execution Flow**:
```
Service Executor → Load Service → Validate Tools → Execute Steps → Handle Results → Update Context
                └── Version     └── Capabilities └── Sequential └── Success/    └── Store
                    Check          Check           Execution      Error          Results
```

3. **Tool Execution Flow**:
```
Tool Registry → Load Tool → Validate → Initialize → Execute → Handle Result
             └── Check    └── Check   └── Setup    └── Run   └── Process
                Version     Deps        Context      Tool      Output
```

4. **Error Recovery Flow**:
```
Error Detection → Check Service Definition → Retry Logic → Alternative Steps → User Update
               └── Error Type            └── Attempt   └── Fallback      └── Status
                  Classification            Count         Options          Message
```

## Authentication and Security

### Google Workspace Authentication

The system uses a robust OAuth2-based authentication system for Google Workspace:

1. **Token Management**
   - Secure token storage in `.auth_tokens` directory
   - Automatic token refresh handling
   - Scope validation and management
   - Graceful reauthorization when needed

2. **Authentication Flow**
```
Check Token → Valid → Use Existing Token
          └── Invalid → Check Refresh Token → Valid → Refresh Token
                                          └── Invalid → Start OAuth2 Flow
```

3. **Security Measures**
   - Encrypted token storage
   - Secure credential handling
   - Environment-based configuration
   - Scope-based access control

## Setup

### Prerequisites

- Python 3.8+
- Slack Workspace and Bot Token
- OpenAI API Key (GPT-4 access required)
- Google Workspace Account
- Required Python packages (see `requirements.txt`)

### Environment Variables

```bash
# Slack Configuration
SLACK_BOT_TOKEN=your-slack-bot-token
SLACK_APP_TOKEN=your-slack-app-token

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key

# Google Authentication
GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
GOOGLE_TOKEN_DIR=/path/to/.auth_tokens
GOOGLE_API_SCOPES=gmail.modify,drive.file,calendar,docs,spreadsheets
```

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/ai-secretary.git
cd ai-secretary
```

2. Create and activate virtual environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Set up Google credentials
   - Create a Google Cloud Project
   - Enable required APIs (Calendar, Gmail, etc.)
   - Create OAuth 2.0 credentials
   - Download credentials.json
   - Place in location specified by GOOGLE_CREDENTIALS_PATH

6. First run and authentication
```bash
python src/main.py
# Follow OAuth2 flow in browser when prompted
```

### Development Setup

For development and testing:

1. Install development dependencies
```bash
pip install -r requirements-dev.txt
```

2. Run tests
```bash
pytest tests/
```

3. Run specific test suites
```bash
pytest tests/test_integration.py  # Integration tests
pytest tests/test_google_calendar.py  # Calendar tests
pytest tests/test_refactored_system.py  # New system tests
```

## Error Handling

The system implements a comprehensive error handling system through multiple layers:

1. **Service-Level Error Handling**
   - Defined in service definitions
   - Supports multiple retry strategies
   - Custom error recovery actions
   - Step dependency management

```yaml
steps:
  - name: "example_step"
    tool: "example_tool"
    retry_strategy:
      max_attempts: 3
      delay_seconds: 5
      backoff_factor: 2
    error_handling:
      - condition: "error.type == 'auth_error'"
        action: "refresh_auth"
      - condition: "error.type == 'rate_limit'"
        action: "wait_and_retry"
      - condition: "error.type == 'validation_error'"
        action: "request_user_input"
```

2. **Execution Context Error Handling**
   - Step result tracking
   - Error state management
   - Variable persistence
   - Rollback capabilities

3. **Tool-Level Error Handling**
   - Tool-specific error types
   - Automatic retry logic
   - Resource cleanup
   - State recovery

4. **System-Level Error Recovery**
   - Service executor recovery
   - Tool registry management
   - Authentication refresh
   - System state maintenance

5. **Error Types and Actions**

| Error Type | Default Action | Alternative Actions |
|------------|---------------|-------------------|
| auth_error | refresh_auth | reauthorize, notify_user |
| rate_limit | wait_and_retry | skip_step, notify_user |
| validation_error | request_user_input | use_defaults, skip_step |
| network_error | retry | fail_fast, use_cached |
| system_error | notify_admin | restart_service, failover |

6. **Recovery Strategies**
   - Step retry with backoff
   - Alternative service paths
   - Graceful degradation
   - User intervention requests
   - Automatic service recreation

7. **Error Reporting**
   - Detailed error logging
   - User-friendly messages
   - Error categorization
   - Recovery suggestions
   - Admin notifications

## Limitations

Current implementation limitations:

1. Sequential Execution Only
   - Steps are executed in order
   - No parallel execution
   - No step dependencies

2. Simple Retry Logic
   - Fixed retry count from service definition
   - Simple delay between retries
   - No complex fallback strategies

3. Parameter Handling
   - No parameter passing between steps
   - No dynamic parameter interpolation
   - Simple required/optional parameter validation