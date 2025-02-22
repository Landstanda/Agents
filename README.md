# AI Secretary

An intelligent AI-powered secretary that can automate any computer-based task through natural language requests via Slack.

## Overview

AI Secretary can automonously perform many tasks on a computer when prompted with natural language requests. It's designed to break a request down into steps and then uses the service index to match those steps with services offered. It then uses a series of task modules to execute the request. It troubleshoots errors, dynamically seeks solutions, and politely reports upon success, failure, and when it determines if it requires more information from the user.

### How it works

A message comes in from slack, the initial data is recorded by the Ticket and past to the Service Analyzer, which compiles the message in a prompt that includes the Service Index. This is passed to a GPT with instructions to break the request down in to steps, match those steps with services, and return the result in a JSON object. The Ticket is updated and passed to the Agent who uses the Service Definitions as a guide in how to execute each service, step by step according to the GPT, utilizing task modules.  When there is success, the Agent signals the Message Maker to notify the user. If the agent fails to accomplish the chain, the information is passed back to the Service Analyzer for either a new chain, or to signal the Message Maker to notify the user that it failed or it needs more info.

## Architecture

The system consists of core components that work together to process and execute user requests. A Ticket is created upon a request via Slack message and passed along the chain of components until the request is fulfilled. Here is the flow a successful request:

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
                                    |     GPT       |
                                    |   Analysis    |
                                    +-------+-------+
                                            |
                                    +-------v-------+
                                    |     Agent     |
                                    |   Execution   |
                                    +-------+-------+
                                            |
                                    +-------v-------+
                                    |   Message     |
                                    |    Maker      |
                                    +-------+-------+
                                            |
                                    +-------v-------+
                                    |     User      |
                                    +---------------+
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

1. **Service Analyzer** (`src/tools/service_analyzer.py`)
   - Uses GPT to analyze incoming requests
   - Breaks down requests into sequential steps
   - Matches steps to available services
   - Identifies required and optional parameters
   - Validates parameter availability
   - Returns structured execution plan

2. **Agent** (`src/tools/agent.py`)
   - Uses `service_definitions.yaml` for execution
   - Executes steps sequentially
   - Handles error recovery using service-defined retry logic
   - Tracks execution results
   - Reports success/failure status

3. **Message Maker** (`src/tools/message_maker.py`)
   - Generates user-friendly responses
   - Manages Slack communication
   - Formats execution results
   - Handles error messages
   - Requests missing information from users

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

1. Basic Request Flow:
```
User → Service Analyzer → GPT Analysis → Agent → Message Maker → User
     └── Request      └── Break into  └── Execute  └── Respond
                         Steps          Steps
```

2. Missing Information Flow:
```
User → Service Analyzer → GPT → Message Maker → User
     └── Request      └── Missing  └── Request     └── Provide
                         Params       Information     Information
                                                       ↓
                                               Service Analyzer
                                                   ↓
                                                 Agent → Execute Steps
```

3. Error Recovery Flow:
```
Step Execution → Error → Check Service Definition → Analyzer GPT w/ Steps/Errors
              └── Fail  └── Retry Count/Actions   └── New Chain or Stop
                                                       ↓
                                                  Message Maker
                                                     ↓
                                                 User Update
```

## Setup

### Prerequisites

- Python 3.8+
- Slack Workspace and Bot Token
- OpenAI API Key (GPT-4 access required)
- Required Python packages (see `requirements.txt`)

### Environment Variables

```bash
SLACK_BOT_TOKEN=your-slack-bot-token
SLACK_APP_TOKEN=your-slack-app-token
OPENAI_API_KEY=your-openai-api-key
```

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/ai-secretary.git
cd ai-secretary
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your tokens and keys
```

4. Run the assistant
```bash
python src/main.py
```

## Error Handling

The system implements robust error handling through service definitions:

1. **Retry Logic**
   - Each service defines retry counts and conditions
   - Agent automatically retries failed steps
   - Simple delay between retry attempts

2. **Missing Parameters**
   - ServiceAnalyzer identifies missing required parameters
   - MessageMaker requests missing information from user
   - Execution continues once parameters are provided

3. **Service Errors**
   - Network errors: Automatic retry
   - Authentication errors: Retry with refresh
   - Other errors: Report to user

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