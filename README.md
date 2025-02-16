# AI Secretary

An intelligent AI-powered secretary that can automate any computer-based task through natural language requests via Slack.

## Overview

AI Secretary is a sophisticated system that processes natural language requests from Slack, automatically executes tasks using existing service definitions, and can even create new services on the fly when encountering novel requests. It acts as a bridge between human intent and computer execution, making task automation accessible through simple conversation.

## Architecture

The system consists of core components that work together to process and execute user requests:

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

The system uses two separate YAML files for service definitions:

1. **Service Index** (`service_index.yaml`):
   - Used by GPT for understanding and breaking down user requests
   - Contains high-level service information and examples
   - Example format:
```yaml
service_name:
  name: "Human-Readable Name"
  description: "Detailed description of what the service does"
  examples:
    - "Example request 1"
    - "Example request 2"
  combination_examples:
    - request: "Complex request example"
      services:
        - service1: "Why this service is needed"
        - service2: "Purpose in this combination"
  required_entities:
    - entity1
    - entity2
  optional_entities:
    - optional1
    - optional2
  outputs:
    - "Output 1 description"
    - "Output 2 description"
```

2. **Service Definitions** (`service_definitions.yaml`):
   - Used by Agent for executing services
   - Contains technical implementation details and error handling
   - Example format:
```yaml
service_name:
  implementation:
    type: "python_function"
    module: "path.to.module"
    function: "function_name"
  parameters:
    - name: "param1"
      type: "string"
      description: "Parameter description"
  error_handling:
    retry_count: 3
    fallback: "alternative_service"
  constraints:
    rate_limit: "10/minute"
    timeout: 30
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
Step Execution → Error → Check Service Definition → Retry/Report
              └── Fail  └── Retry Count/Actions   └── Continue/Stop
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