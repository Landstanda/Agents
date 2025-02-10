#!/usr/bin/env python3

from typing import Dict, Any, List
from datetime import datetime
import json
from ...modules.base_chain import Chain
from ...utils.logging import get_logger

logger = get_logger(__name__)

class EmailProcessingChain(Chain):
    """Chain for processing and organizing emails"""
    
    def __init__(self):
        # Initialize base chain with name and version
        super().__init__("email_processing_chain", "1.0")
        
        # Required modules
        from ...modules.email_reader import EmailReaderModule
        from ...modules.data_cleaner import DataCleanerModule
        from ...modules.notification import NotificationModule
        from ...modules.slack_integration import SlackModule
        from ...modules.google_drive import GoogleDriveModule
        
        # Initialize modules
        self.modules = {
            'email_reader': EmailReaderModule(),
            'data_cleaner': DataCleanerModule(),
            'notification': NotificationModule(),
            'slack': SlackModule(),
            'drive': GoogleDriveModule()
        }
        
        # Define required and optional variables
        self.required_variables = ['text']  # Natural language request
        self.optional_variables = [
            'folder',      # Target folder for processed emails
            'label',       # Label to apply to processed emails
            'urgent',      # Whether to handle as urgent
            'archive',     # Whether to archive processed emails
            'notify_team'  # Whether to notify team about processed emails
        ]
        
        # Define success criteria
        self.success_criteria = [
            "All specified emails are processed",
            "Labels are correctly applied",
            "Urgent emails are properly flagged",
            "Team is notified if requested",
            "Emails are archived if specified"
        ]
    
    def _initialize_keywords(self) -> List[str]:
        """Initialize keywords for request matching"""
        return [
            'email',
            'mail',
            'inbox',
            'message',
            'urgent',
            'process',
            'check',
            'read'
        ]
    
    def _initialize_capabilities(self) -> Dict[str, Any]:
        """Initialize chain capabilities"""
        return {
            "name": "EmailProcessingChain",
            "description": "Processes emails including reading, classification, response generation, and sending",
            "functions": [
                "read_emails",
                "classify_emails",
                "generate_responses",
                "send_responses"
            ],
            "examples": [
                "check my emails",
                "process new messages",
                "handle inbox",
                "read urgent emails"
            ],
            "keywords": self._initialize_keywords()
        }
    
    async def process(self, request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a request through the chain (new interface)"""
        try:
            # Convert request and context to chain variables
            chain_vars = {
                'text': request,  # The natural language request
                **(context.get('variables', {}) if context else {}),  # Any extracted variables
            }
            
            # Execute the chain with the prepared variables
            return await self.execute(chain_vars)
            
        except Exception as e:
            logger.error(f"Error in email processing chain process(): {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'data': None
            }
    
    async def execute(self, chain_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the email processing chain"""
        try:
            # Validate variables
            validation = self.validate_variables(chain_vars)
            if validation['missing']:
                return {
                    'status': 'error',
                    'message': f"Missing required variables: {', '.join(validation['missing'])}",
                    'data': None
                }
            
            # Log start of execution
            self.log_execution("start", {"status": "started", "variables": chain_vars})
            
            # Process the natural language request
            request = chain_vars['text']
            folder = chain_vars.get('folder', 'Inbox')
            label = chain_vars.get('label')
            is_urgent = chain_vars.get('urgent', False)
            should_archive = chain_vars.get('archive', False)
            notify_team = chain_vars.get('notify_team', False)
            
            # Step 1: Fetch emails
            fetch_result = await self._execute_module(
                'email_reader', 
                'fetch_emails',
                folder=folder
            )
            
            if fetch_result['status'] != 'success':
                return fetch_result
            
            emails = fetch_result['result']
            
            # Step 2: Process each email
            processed_emails = []
            for email in emails:
                # Clean email content
                clean_result = await self._execute_module(
                    'data_cleaner',
                    'clean_text',
                    text=email['content']
                )
                
                if clean_result['status'] == 'success':
                    email['cleaned_content'] = clean_result['result']
                    
                    # Extract entities if needed
                    entities_result = await self._execute_module(
                        'data_cleaner',
                        'extract_entities',
                        text=email['cleaned_content']
                    )
                    
                    if entities_result['status'] == 'success':
                        email['entities'] = entities_result['result']
                
                # Apply label if specified
                if label:
                    label_result = await self._execute_module(
                        'email_reader',
                        'apply_label',
                        email_id=email['id'],
                        label=label
                    )
                    
                    if label_result['status'] != 'success':
                        logger.warning(f"Failed to apply label to email {email['id']}")
                
                # Handle urgent emails
                if is_urgent and self._is_urgent(email):
                    notify_result = await self._execute_module(
                        'notification',
                        'send_notification',
                        title="Urgent Email",
                        message=f"Urgent email from {email['sender']}: {email['subject']}"
                    )
                    
                    if notify_result['status'] != 'success':
                        logger.warning(f"Failed to send notification for urgent email {email['id']}")
                
                # Archive if requested
                if should_archive:
                    archive_result = await self._execute_module(
                        'email_reader',
                        'move_to_folder',
                        email_id=email['id'],
                        folder='Archive'
                    )
                    
                    if archive_result['status'] != 'success':
                        logger.warning(f"Failed to archive email {email['id']}")
                
                processed_emails.append(email)
            
            # Step 3: Notify team if requested
            if notify_team and processed_emails:
                summary = self._create_email_summary(processed_emails)
                
                # Send to Slack
                slack_result = await self._execute_module(
                    'slack',
                    'send_message',
                    channel='team-updates',
                    message=summary
                )
                
                if slack_result['status'] != 'success':
                    logger.warning("Failed to send team notification to Slack")
            
            # Step 4: Save processed emails to Google Drive if archiving
            if should_archive and processed_emails:
                # Create folder for archived emails
                folder_result = await self._execute_module(
                    'drive',
                    'create_folder',
                    name=f"Archived_Emails_{datetime.now().strftime('%Y%m%d')}"
                )
                
                if folder_result['status'] == 'success':
                    folder_id = folder_result['result']['id']
                    
                    # Save each email
                    for email in processed_emails:
                        save_result = await self._execute_module(
                            'drive',
                            'save_file',
                            folder_id=folder_id,
                            name=f"{email['id']}.json",
                            content=json.dumps(email, indent=2)
                        )
                        
                        if save_result['status'] != 'success':
                            logger.warning(f"Failed to save email {email['id']} to Drive")
            
            # Return success result
            return {
                'status': 'success',
                'message': f"Processed {len(processed_emails)} emails",
                'data': {
                    'processed_emails': processed_emails,
                    'actions': []  # Add any required actions for the Slack listener
                }
            }
            
        except Exception as e:
            logger.error(f"Error in email processing chain: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'data': None
            }
    
    def _is_urgent(self, email: Dict[str, Any]) -> bool:
        """Check if an email is urgent based on its content and metadata"""
        urgent_keywords = ['urgent', 'important', 'asap', 'emergency', 'critical']
        
        # Check subject
        if any(keyword in email['subject'].lower() for keyword in urgent_keywords):
            return True
        
        # Check content
        if any(keyword in email['content'].lower() for keyword in urgent_keywords):
            return True
        
        # Check priority flag if available
        if email.get('priority') in ['high', 'urgent']:
            return True
        
        return False
    
    def _create_email_summary(self, emails: List[Dict[str, Any]]) -> str:
        """Create a summary of processed emails for team notification"""
        summary = "📧 *Email Processing Summary*\n\n"
        
        # Group emails by sender
        emails_by_sender = {}
        for email in emails:
            sender = email['sender']
            if sender not in emails_by_sender:
                emails_by_sender[sender] = []
            emails_by_sender[sender].append(email)
        
        # Create summary by sender
        for sender, sender_emails in emails_by_sender.items():
            summary += f"*From {sender}:*\n"
            for email in sender_emails:
                summary += f"• {email['subject']}"
                if self._is_urgent(email):
                    summary += " 🚨"
                summary += "\n"
            summary += "\n"
        
        return summary 