# AI Secretary Refactoring Plan

## Goals
- Simplify and modularize the agent implementation
- Maintain compatibility with existing components (ServiceAnalyzer, MessageMaker, modules)
- Keep existing service definitions and execution patterns
- Improve code organization and maintainability
- Better error handling and state management

## New Directory Structure
```
src/
├── core/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── base.py          # Base agent interface and core agent class
│   │   ├── executor.py      # Service and step execution logic
│   │   └── state.py         # Agent state management
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── loader.py        # Service definition loading and validation
│   │   └── registry.py      # Service registration and lookup
│   │
│   └── tools/
│       ├── __init__.py
│       ├── loader.py        # Tool loading and registration
│       └── registry.py      # Tool lookup and validation
│
├── execution/
│   ├── __init__.py
│   ├── context.py           # Execution context management
│   ├── parameters.py        # Parameter processing and validation
│   └── handlers/
│       ├── __init__.py
│       ├── error.py         # Error handling logic
│       ├── retry.py         # Retry logic
│       └── success.py       # Success evaluation
│
├── models/                  # Existing models directory
│   ├── __init__.py
│   └── ticket.py           # Existing ticket system
│
├── modules/                 # Existing modules directory
│   ├── __init__.py
│   ├── google_auth.py
│   └── [other modules]
│
├── services/               # Existing services directory
│   ├── service_index.json
│   └── service_definitions.yaml
│
└── utils/                  # Shared utilities
    ├── __init__.py
    ├── logging.py
    └── validation.py
```

## Implementation Phases

### Phase 1: Core Infrastructure
1. Create new directory structure
2. Implement base agent interface
3. Create service and tool registries
4. Set up basic execution context

### Phase 2: Execution Engine
1. Implement service executor
2. Create parameter processor
3. Set up error handling system
4. Implement retry logic

### Phase 3: State Management
1. Enhance ticket system if needed
2. Implement agent state management
3. Add execution context tracking
4. Improve error tracking

### Phase 4: Integration
1. Connect with ServiceAnalyzer
2. Integrate with MessageMaker
3. Ensure module compatibility
4. Validate service execution

### Phase 5: Testing & Validation
1. Unit tests for new components
2. Integration tests
3. Service execution validation
4. Error handling verification

## Key Components

### BaseAgent
```python
class BaseAgent:
    """Core agent functionality"""
    async def initialize(self) -> None
    async def process_ticket(self, ticket: Ticket) -> None
    async def execute_service(self, service_name: str, ticket: Ticket) -> None
```

### ServiceExecutor
```python
class ServiceExecutor:
    """Service execution engine"""
    async def execute_service(self, service_def: Dict, ticket: Ticket) -> None
    async def execute_step(self, step: Dict, context: ExecutionContext) -> None
```

### ExecutionContext
```python
class ExecutionContext:
    """Manages execution state and data"""
    def __init__(self, ticket: Ticket, service: Dict)
    def update_state(self, state: Dict) -> None
    def get_parameter(self, name: str) -> Any
```

### ServiceRegistry
```python
class ServiceRegistry:
    """Service management"""
    def register_service(self, service: Dict) -> None
    def get_service(self, name: str) -> Optional[Dict]
    def validate_service(self, service: Dict) -> bool
```

### ToolRegistry
```python
class ToolRegistry:
    """Tool management"""
    def register_tool(self, name: str, tool_class: Type[BaseModule]) -> None
    def get_tool(self, name: str) -> Optional[Type[BaseModule]]
    def validate_tool(self, tool_class: Type[BaseModule]) -> bool
```

## Migration Strategy

1. **Preparation**
   - Back up existing code
   - Create new directory structure
   - Set up new package imports

2. **Incremental Implementation**
   - Implement each component in isolation
   - Unit test as we go
   - Maintain backward compatibility

3. **Integration**
   - Gradually replace old agent with new implementation
   - Validate each service works with new system
   - Ensure all modules function correctly

4. **Validation**
   - Test full request lifecycle
   - Verify error handling
   - Check performance
   - Validate state management

## Success Criteria

1. All existing services work with new implementation
2. Error handling is more robust
3. Code is more maintainable and testable
4. No regression in functionality
5. Improved state management
6. Better logging and debugging capabilities

## Notes

- Keep existing module interface (`BaseModule`)
- Maintain current service definition format
- Preserve ticket system core functionality
- Ensure backward compatibility with ServiceAnalyzer and MessageMaker 


Service Registry (High Priority)
  - YAML service definition loading
  - Service validation
  - Service dependency resolution
  - Error handling for invalid services
Service Executor (High Priority)
  - Step execution
  - Error recovery
  - Context management
  - Parameter handling
Flow Logger (Medium Priority)
  - Event logging
  - Error logging
  - Event history tracking
Execution Context (Medium Priority)
  - Variable management
  - Step tracking
  - Result storage
Success Evaluator (Low Priority)
  - Condition evaluation
  - Result validation
  - Custom criteria handling

Ticket System (src/models/ticket.py)
  - Core state management
  - Status lifecycle
  - Entity tracking
  - Conversation management
  - Error history
Module Interface (src/core/module_interface.py)
  - ModuleResponse class
  - Base module functionality
  - Response formatting
  - Error handling


Ticket-Agent Flow
  - Ticket creation → Service Analyzer → Agent execution
  - Status updates throughout the pipeline
  - Error propagation
Service Execution Chain
  - Service Registry → Tool Registry → Service Executor
  - Context management across steps
  - Error handling and recovery
Message Flow
  - User input → Ticket → Service Analyzer → Agent → Message Maker → User
  - Conversation threading
  - Status updates
Error Recovery Flow
  - Error detection → Service Definition checks → Retry logic
  - Alternative step execution
  - User notification
Authentication Flow
  - Token validation
  - Refresh handling
  - Reauthorization process
  Variable Management
  - Context variables across services
  - Entity propagation
  - Step result mapping

  ## Next Steps
  AI Secretary Development Roadmap
Phase 1: Comprehensive Testing of Existing Functionality
1. Calendar Functionality Testing
  - Basic event creation (already tested)
  - Test event creation with participants (using valid email addresses)
  - Test event creation with different time formats
  - Test event creation with different date formats
  - Test event listing functionality
  - Test event deletion functionality
2. Error Handling Testing
  - Test with invalid dates (past dates)
  - Test with invalid time formats
  - Test with invalid email addresses
  - Test with missing required parameters
3. Status Transition Testing
  - Test all possible ticket status transitions (already fixed)
  - Test error recovery paths
4. Slack Integration Testing
  - Test message sending to different channels
  - Test thread replies
  - Test handling of different message formats
  - Test handling of attachments or rich content

Phase 2: Expanding Core Functionality
1. Email Integration
  - Fix the email module loading errors
  - Implement email reading functionality
  - Implement email composition and sending
  - Implement email search and filtering
2. Document Management
  - Implement Google Docs integration
  - Add document creation functionality
  - Add document editing functionality
  - Add document sharing functionality
3. Task Management
  - Implement task tracking functionality
  - Add reminder setting capabilities
  - Add task prioritization
  - Add task delegation to team members
4. Meeting Scheduling Enhancement
  - Implement availability checking
  - Add recurring meeting support
  - Add meeting room booking
  - Implement multi-participant scheduling optimization

Phase 3: Advanced Features and Integration
1. Natural Language Processing Improvements
  - Enhance entity extraction for complex requests
  - Implement context-aware conversations
  - Add support for ambiguous requests with clarification
  - Improve handling of colloquial time expressions
2. Multi-Service Orchestration
  - Implement workflows that combine multiple services
  - Add conditional execution paths
  - Support for parallel execution of tasks
  - Add rollback capabilities for failed workflows
3. User Preference Learning
  - Implement user preference tracking
  - Add personalized responses based on user history
  - Implement smart defaults based on past behavior
  - Add proactive suggestions
4. Analytics and Reporting
  - Implement usage tracking
  - Add performance metrics dashboard
  - Generate user activity reports
  - Track most used features for optimization

Phase 4: Reliability and Scalability
1. Robust Error Recovery
  - Implement comprehensive error logging
  - Add automatic retry mechanisms with backoff
  - Implement service health monitoring
  - Add circuit breakers for failing services
2. Performance Optimization
  - Profile and optimize slow operations
  - Implement caching for frequently used data
  - Optimize database queries
  - Reduce API call overhead
3. Security Enhancements
  - Implement more robust authentication
  - Add fine-grained authorization
  - Implement secure credential storage
  - Add audit logging for sensitive operations
4. Scalability Improvements
  - Implement load balancing
  - Add support for distributed execution
  - Optimize resource usage
  - Implement rate limiting for external APIs

Testing Process Guidelines
For each feature or service, follow this testing process:
1. Unit Testing
  - Create dedicated test scripts for each module
  - Test each function with various inputs
  - Test error handling paths
  - Verify correct output formats
2. Integration Testing
  - Test interactions between modules
  - Verify data flow between components
  - Test end-to-end service execution
  - Verify correct handling of context between steps
3. User Acceptance Testing
  - Create realistic test scenarios
  - Test with actual user prompts
  - Verify responses match expectations
  - Test edge cases and unusual inputs
4.  Performance Testing
  - Measure response times
  - Test under load
  - Identify bottlenecks
  - Optimize slow operations

Implementation Strategy
For adding new functionality:
1. Research and Design
  - Identify user needs
  - Research available APIs and libraries
  - Design the module interface
  - Plan integration with existing components
2. Prototype Development
  - Create standalone test scripts
  - Implement core functionality
  - Test with sample data
  - Refine based on results
3. Integration
  - Integrate with the main application
  - Update service registry
  - Add necessary entity extraction
  - Implement error handling
4. Documentation and Testing
  - Document the new functionality
  - Create test cases
  - Add to test suite
  - Create user documentation

Next Immediate Steps
Based on the current state, here are the immediate next steps:
1. Fix Email Module Loading Errors
  - Investigate the "attempted relative import with no known parent package" errors
  - Fix import statements in affected modules
  - Test email functionality independently
2. Enhance Calendar Module
  - Add support for more date/time formats
  - Improve participant handling with email validation
  - Add support for recurring meetings
3. Improve Error Handling
  - Implement more graceful error recovery
  -  Add better error messages for users
4. Enhance logging for debugging
  - Create Comprehensive Test Suite
  - Develop automated tests for all modules
  - Create regression test suite
  - Implement continuous testing