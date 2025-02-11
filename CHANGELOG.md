# Changelog

All notable changes to this project will be documented in this file.

## [0.2.1] - 2024-03-21

### Added
- Comprehensive time entity validation in test suite
- Flexible time format handling in NLP processor
- Enhanced test cases for time entity flow
- Improved validation in cookbook manager for time entities

### Changed
- Updated time entity extraction to support both relative and absolute formats
- Refined test assertions to be more robust and descriptive
- Improved error messages in time validation tests
- Enhanced cookbook validation to properly handle time entities

### Fixed
- Time entity validation in cookbook manager
- Time format mismatch between NLP and cookbook
- Test expectations for time formats
- Entity validation flow in integration tests

## [0.2.0] - 2024-03-20

### Added
- Priority-based task queue implementation in TaskManager
- FIFO ordering for tasks with equal priority
- Enhanced error handling and recovery mechanisms
- Task history tracking with detailed execution results
- Comprehensive test suite for integration flows
- Urgency detection in NLP processor
- Error task handling with proper status tracking
- Concurrent task processing capabilities

### Changed
- Improved recipe validation in CookbookManager
- Enhanced message handling in FrontDesk
- Updated task execution flow to support priorities
- Expanded test coverage for all components
- Refined error recovery strategies

### Fixed
- Task queue overflow handling
- Error propagation in task execution
- Recipe matching with missing entities
- Message deduplication logic
- Concurrent task processing issues

## [0.1.0] - 2024-03-15

### Added
- Initial implementation of Office Assistant
- Slack integration via Socket Mode
- Basic NLP processing
- Recipe-based task execution
- CEO decision making
- Basic error handling 