# Chain Definitions

This document defines the available chains in the system, their requirements, and usage patterns.

## email_processing_chain

```python
# Chain Name: EmailProcessingChain
# Status: Implemented & Tested
# Version: 1.0

Input_Variables:
- text (required): Natural language request describing the email processing task
- folder: Target folder for processed emails (default: Inbox)
- label: Label to apply to processed emails
- urgent: Whether to handle as urgent (default: false)
- archive: Whether to archive processed emails (default: false)
- notify_team: Whether to notify team about processed emails (default: false)

Success_Criteria:
- All specified emails are processed
- Labels are correctly applied
- Urgent emails are properly flagged
- Team is notified if requested
- Emails are archived if specified

Module_Sequence:
- EmailReaderModule: Fetch and manage emails
- DataCleanerModule: Clean and analyze email content
- NotificationModule: Handle urgent notifications
- SlackModule: Send team notifications
- GoogleDriveModule: Archive emails if requested

Example_Usage:
```python
result = await chain.execute({
    'text': 'Process urgent emails from clients and notify the team',
    'folder': 'Inbox',
    'label': 'Client',
    'urgent': True,
    'notify_team': True
})
```
```

## web_research_chain

```python
# Chain Name: WebResearchChain
# Status: Implemented & Tested
# Version: 1.0

Input_Variables:
- text (required): Natural language request describing the research task
- topic: Research topic (defaults to text)
- depth: How deep to follow links (default: 1)
- max_pages: Maximum pages to process (default: 10)
- save_format: Format to save results (default: 'doc')
- use_browser: Whether to use browser automation (default: false)

Success_Criteria:
- Research topic is properly analyzed
- Relevant information is extracted
- Content is cleaned and organized
- Results are saved in specified format
- Links are properly followed to specified depth

Module_Sequence:
- BrowserAutomationModule: Navigate and extract content if use_browser is true
- CoreRequestModule: Make HTTP requests if not using browser
- HTMLParserModule: Extract content from HTML
- DataCleanerModule: Clean and analyze content
- GoogleDocsModule: Save and organize research results

Example_Usage:
```python
result = await chain.execute({
    'text': 'Research the latest developments in AI and create a summary',
    'depth': 2,
    'max_pages': 20,
    'save_format': 'doc'
})
```
```

## business_communication_chain

```python
# Chain Name: BusinessCommunicationChain
# Status: Implemented & Tested
# Version: 1.0

Input_Variables:
- text (required): Natural language request describing the communication task
- communication_type: Type of communication (email, slack, trello)
- subject: Subject/title of the communication
- content: Main content
- tone: Desired tone (formal, casual, etc.)
- send_email: Whether to send email
- email_recipients: List of email recipients
- send_slack: Whether to send Slack message
- slack_channel: Target Slack channel
- create_trello: Whether to create Trello card
- trello_list_id: Target Trello list
- trello_comment: Comment for Trello card
- notify_additional: Whether to send additional notifications
- attachments: List of attachments

Success_Criteria:
- Communication context is properly retrieved
- Content is properly formatted and validated
- Messages are delivered through specified channels
- Attachments are properly handled
- Trello cards are created if specified
- Additional notifications are sent if requested

Module_Sequence:
- BusinessContextModule: Get business context for communication
- DataCleanerModule: Format and validate content
- EmailSenderModule: Send emails if requested
- SlackModule: Send Slack messages if requested
- TrelloModule: Create cards if requested
- NotificationModule: Send additional notifications

Example_Usage:
```python
result = await chain.execute({
    'text': 'Send project update to team via email and Slack',
    'subject': 'Project Update',
    'send_email': True,
    'email_recipients': ['team@company.com'],
    'send_slack': True,
    'slack_channel': 'project-updates'
})
```
```

## document_management_chain

```python
# Chain Name: DocumentManagementChain
# Status: Planned
# Version: 1.0

Input_Variables:
- text (required): Natural language request describing the document management task
- operation: Type of operation (create, update, organize, archive)
- doc_type: Type of document
- content: Document content
- metadata: Additional metadata
- permissions: Access permissions
- storage: Storage location

Success_Criteria:
- Document operations are completed successfully
- Metadata is properly applied
- Permissions are correctly set
- Storage location is properly managed
- Version control is maintained if applicable

Module_Sequence:
- DocManagementModule: Handle document operations
- FileTransferModule: Manage file transfers
- GoogleDriveModule: Handle cloud storage
- DataCleanerModule: Clean and validate content
- NotificationModule: Notify relevant parties

Example_Usage:
```python
result = await chain.execute({
    'text': 'Create a new project document and share with the team',
    'operation': 'create',
    'doc_type': 'project',
    'permissions': ['team-read', 'admin-write']
})
```
```

## project_management_chain

```python
# Chain Name: ProjectManagementChain
# Status: Planned
# Version: 1.0

Input_Variables:
- text (required): Natural language request describing the project management task
- project: Project identifier
- task_type: Type of task
- assignee: Task assignee
- due_date: Task due date
- priority: Task priority
- dependencies: Task dependencies
- notifications: Notification preferences

Success_Criteria:
- Project/task is properly created or updated
- Assignments are correctly made
- Dependencies are properly tracked
- Notifications are sent to relevant parties
- Project timeline is maintained

Module_Sequence:
- ProjectSyncModule: Manage project synchronization
- TrelloModule: Handle task management
- SlackModule: Send team notifications
- NotificationModule: Handle individual notifications
- BusinessContextModule: Maintain project context

Example_Usage:
```python
result = await chain.execute({
    'text': 'Create a new high-priority task for the website redesign',
    'project': 'website-redesign',
    'task_type': 'feature',
    'priority': 'high',
    'assignee': 'design-team'
})
```
```

## scheduling_chain

```python
# Chain Name: SchedulingChain
# Status: Implemented & Tested
# Version: 1.1

Input_Variables:
- text (required): Natural language request describing the scheduling task
- time (required): Meeting time (supports both relative and absolute formats)
  Examples:
  - Relative: "tomorrow at 9:00 AM", "next week at 2pm"
  - Absolute: "2024-03-25 14:00", "March 25th at 2:00 PM"
- participants: List of meeting participants (optional)
- duration: Meeting duration in minutes (default: 60)
- location: Meeting location or video link
- description: Meeting description or agenda
- notify: Whether to send notifications (default: true)

Success_Criteria:
- Time is properly extracted and validated
- Meeting is scheduled at the correct time
- Participants are properly notified
- Calendar events are created
- Meeting details are properly recorded

Module_Sequence:
- NLPProcessor: Extract and validate time entities
- CookbookManager: Match and validate scheduling recipe
- CalendarModule: Create calendar events
- NotificationModule: Send meeting notifications
- SlackModule: Send team notifications

Example_Usage:
```python
result = await chain.execute({
    'text': 'Schedule a team meeting for tomorrow at 2pm',
    'time': 'tomorrow at 2:00 PM',
    'participants': ['@john', '@mary'],
    'description': 'Weekly team sync'
})
```
```