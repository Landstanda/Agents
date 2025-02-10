# Changelog

All notable changes to this project will be documented in this file.

## [0.2.1] - 2024-01-21

### Added
- Socket Mode implementation replacing polling system
- GPT client availability checking
- Message deduplication using timestamps
- Enhanced error handling and user feedback

### Changed
- Improved CEO response handling with better fallbacks
- Enhanced thread handling in Front Desk
- Better logging for events and responses
- Updated error messages to be more user-friendly

### Fixed
- Double message responses issue
- GPT client initialization errors
- Socket Mode connection stability
- Message processing in threads

## [0.2.0] - 2024-01-20

### Added
- NLP Processor for quick text analysis
  - Intent detection
  - Entity extraction
  - Urgency detection
  - Temporal context analysis
  - User context tracking
- Enhanced Front Desk capabilities
  - Integration with NLP Processor
  - Improved response formatting
  - Better error handling
  - Socket mode support
- Comprehensive test suite
  - NLP processor tests
  - Front Desk integration tests
  - Socket mode request tests

### Changed
- Updated Front Desk to use NLP processing before CEO consultation
- Improved message handling architecture
- Enhanced documentation with architecture details
- Updated README with new components and features

### Fixed
- Urgency detection accuracy
- Socket mode request handling
- Response formatting consistency

## [0.1.0] - 2024-01-19

### Added
- Initial CEO implementation
- Basic Cookbook Manager
- Recipe matching functionality
- Simple Slack integration
- Basic test coverage 