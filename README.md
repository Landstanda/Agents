# AI Secretary

An intelligent AI-powered secretary that can automate any computer-based task through natural language requests via Slack.

## Overview

AI Secretary can automonously perform many tasks on a computer when prompted with natural language requests. It's designed to break a request down into steps and then uses the service index to match those steps with services offered. It then uses a series of task modules to execute the request. It troubleshoots errors, dynamically seeks solutions, and politely reports upon success, failure, and when it determines if it requires more information from the user.

### How it works

A message comes in from slack, the initial data is recorded by the Ticket and past to the Service Analyzer, which compiles the message in a prompt that includes the Service Index. This is passed to a GPT with instructions to break the request down in to steps, match those steps with services, and return the result in a JSON object. The Ticket is updated and passed to the Agent who uses the Service Definitions as a guide in how to execute each service, step by step according to the GPT, utilizing task modules.  When there is success, the Agent signals the Message Maker to notify the user. If the agent fails to accomplish the chain, the information is passed back to the Service Analyzer for either a new chain, or to signal the Message Maker to notify the user that it failed or it needs more info.

## Architecture

The system consists of several interconnected components that work together to process and execute user requests. The architecture is fully asynchronous and supports graceful error handling and shutdown.

### Component Overview

1. **Office Assistant** (`src/main.py`)
   - Main application entry point
   - Handles Slack integration
   - Manages task lifecycle
   - Provides graceful shutdown

2. **Request Orchestrator** (`src/core/orchestrator.py`)
   - Coordinates between components
   - Manages request flow
   - Handles async task tracking
   - Provides error recovery

3. **Service Analyzer** (`src/tools/service_analyzer.py`)
   - Uses GPT-4 for request analysis
   - Maps natural language to services
   - Creates execution plans
   - Validates service requirements

4. **Agent Chain**
   The agent chain consists of several components that work together:

   a) **Base Agent** (`src/core/agent/base_agent.py`)
      - Provides core agent functionality
      - Manages component initialization
      - Handles service execution
      - Coordinates error recovery

   b) **Service Registry** (`src/core/registry/service_registry.py`)
      - Manages service definitions
      - Validates service configurations
      - Handles service versioning
      - Provides service lookup

   c) **Tool Registry** (`src/core/registry/tool_registry.py`)
      - Dynamic tool loading
      - Tool validation
      - Capability matching
      - Tool lifecycle management

   d) **Service Executor** (`src/core/agent/executor.py`)
      - Executes service steps
      - Manages execution context
      - Handles step retry logic
      - Provides error recovery

5. **Flow Logger** (`src/utils/flow_logger.py`)
   - Event tracking
   - Error logging
   - Execution history
   - Debug information

### System Flows

1. **Request Processing Flow**
```
User Message → Slack Interface → Office Assistant → Request Orchestrator → Service Analyzer → Agent Chain → Response
```

2. **Service Analysis Flow**
```
Request → GPT Analysis → Service Mapping → Execution Plan → Validation → Agent Chain
```

3. **Service Execution Flow**
```
Execution Plan → Service Registry → Tool Registry → Service Executor → Tool Execution → Results
```

4. **Error Recovery Flow**
```
Error Detection → Retry Strategy → Alternative Steps → User Notification → Status Update
```

### Service Configuration

The system uses two complementary service definition files:

1. **Service Index** (`src/services/service_index.json`)
   Used by GPT for understanding requests:
   ```json
   {
       "service_name": {
           "name": "Human-Readable Name",
           "description": "Service description",
           "examples": ["Example 1", "Example 2"],
           "required_entities": ["entity1"],
           "optional_entities": ["optional1"],
           "outputs": ["output1"]
       }
   }
   ```

2. **Service Definitions** (`src/services/service_definitions.yaml`)
   Used by the Agent for execution:
   ```yaml
   service_name:
     name: "Service Name"
     steps:
       - name: "Step Name"
         tool: tool_name
         action: action_name
         params:
           param1: value1
         on_error:
           - action: retry
             max_attempts: 3
   ```

### Error Handling

The system implements multi-level error handling:

1. **Request Level**
   - Timeout handling
   - Invalid request detection
   - Missing information handling

2. **Analysis Level**
   - GPT response validation
   - Service mapping errors
   - Missing parameter detection

3. **Execution Level**
   - Step retry logic
   - Alternative service paths
   - Tool execution errors

4. **System Level**
   - Component initialization errors
   - Resource cleanup
   - Graceful shutdown

### Async Task Management

The system uses asyncio for concurrent operations:

1. **Task Tracking**
   - Pending task management
   - Timeout handling
   - Resource cleanup

2. **Graceful Shutdown**
   - Signal handling
   - Task cancellation
   - Resource cleanup

3. **Error Recovery**
   - Async retry logic
   - Parallel execution
   - State management

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
