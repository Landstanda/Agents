#!/usr/bin/env python3

from typing import Dict, Any, List
from ...modules.base_chain import Chain
from ...utils.logging import get_logger
import json
from datetime import datetime

logger = get_logger(__name__)

class BusinessCommunicationChain(Chain):
    """Chain for handling various forms of business communication"""
    
    def __init__(self):
        super().__init__("business_communication_chain", "1.0")
        
        # Required modules
        from ...modules.business_context import BusinessContextModule
        from ...modules.data_cleaner import DataCleanerModule
        from ...modules.email_sender import EmailSenderModule
        from ...modules.slack import SlackModule
        from ...modules.trello import TrelloModule
        from ...modules.notification import NotificationModule
        
        # Initialize modules
        self.modules = {
            'context': BusinessContextModule(),
            'cleaner': DataCleanerModule(),
            'email': EmailSenderModule(),
            'slack': SlackModule(),
            'trello': TrelloModule(),
            'notification': NotificationModule()
        }
        
        # Define required and optional variables
        self.required_variables = ['text']  # Natural language request
        self.optional_variables = [
            'communication_type',  # Type of communication (email, slack, trello)
            'subject',            # Subject/title of the communication
            'content',            # Main content
            'tone',              # Desired tone (formal, casual, etc.)
            'send_email',        # Whether to send email
            'email_recipients',  # List of email recipients
            'send_slack',        # Whether to send Slack message
            'slack_channel',     # Target Slack channel
            'create_trello',     # Whether to create Trello card
            'trello_list_id',    # Target Trello list
            'trello_comment',    # Comment for Trello card
            'notify_additional', # Whether to send additional notifications
            'attachments'        # List of attachments
        ]
        
        # Define success criteria
        self.success_criteria = [
            "Communication context is properly retrieved",
            "Content is properly formatted and validated",
            "Messages are delivered through specified channels",
            "Attachments are properly handled",
            "Trello cards are created if specified",
            "Additional notifications are sent if requested"
        ]
    
    async def execute(self, chain_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the business communication chain"""
        try:
            # Validate variables
            validation = self.validate_variables(chain_vars)
            if validation['missing']:
                return {
                    'status': 'error',
                    'error': f"Missing required variables: {', '.join(validation['missing'])}"
                }
            
            # Log start of execution
            self.log_execution("start", {"status": "started", "variables": chain_vars})
            
            # Process the natural language request
            request = chain_vars['text']
            comm_type = chain_vars.get('communication_type', 'all')
            subject = chain_vars.get('subject', '')
            content = chain_vars.get('content', request)
            tone = chain_vars.get('tone', 'professional')
            
            # Step 1: Get business context
            context_result = await self._execute_module(
                'context',
                'get_context'
            )
            
            if context_result['status'] != 'success':
                logger.warning("Failed to get business context")
                context = {}
            else:
                context = context_result['result']
            
            # Step 2: Format message based on context and tone
            formatted_content = await self._format_message(content, tone, context)
            
            # Step 3: Validate content
            validation_result = await self._execute_module(
                'cleaner',
                'validate_content',
                text=formatted_content,
                content_type=comm_type
            )
            
            if validation_result['status'] != 'success':
                return validation_result
            
            # Step 4: Send communications
            results = []
            
            # Send email if requested
            if chain_vars.get('send_email'):
                email_result = await self._send_email(
                    chain_vars.get('email_recipients', []),
                    subject,
                    formatted_content,
                    chain_vars.get('attachments', [])
                )
                results.append(('email', email_result))
            
            # Send Slack message if requested
            if chain_vars.get('send_slack'):
                slack_result = await self._send_slack_message(
                    chain_vars.get('slack_channel', 'general'),
                    formatted_content,
                    chain_vars.get('attachments', [])
                )
                results.append(('slack', slack_result))
            
            # Create Trello card if requested
            if chain_vars.get('create_trello'):
                trello_result = await self._create_trello_card(
                    chain_vars.get('trello_list_id'),
                    subject or "New Communication",
                    formatted_content,
                    chain_vars.get('trello_comment'),
                    chain_vars.get('attachments', [])
                )
                results.append(('trello', trello_result))
            
            # Send additional notifications if requested
            if chain_vars.get('notify_additional'):
                notify_result = await self._execute_module(
                    'notification',
                    'send_notification',
                    title=subject or "New Communication",
                    message=formatted_content
                )
                results.append(('notification', notify_result))
            
            # Check results and prepare response
            success = all(result[1]['status'] == 'success' for result in results)
            
            if success:
                return {
                    'status': 'success',
                    'message': "Communication sent successfully",
                    'results': {k: v for k, v in results},
                    'actions': self._create_action_list(results)
                }
            else:
                failed = [r[0] for r in results if r[1]['status'] != 'success']
                return {
                    'status': 'partial_success',
                    'message': f"Some communications failed: {', '.join(failed)}",
                    'results': {k: v for k, v in results},
                    'actions': self._create_action_list(results)
                }
            
        except Exception as e:
            logger.error(f"Error in business communication chain: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def _format_message(self, content: str, tone: str, context: Dict) -> str:
        """Format message based on tone and context"""
        format_result = await self._execute_module(
            'cleaner',
            'format_message',
            text=content,
            tone=tone,
            context=context
        )
        
        if format_result['status'] == 'success':
            return format_result['result']
        return content
    
    async def _send_email(self, recipients: List[str], subject: str, 
                         content: str, attachments: List[str]) -> Dict[str, Any]:
        """Send email to recipients"""
        return await self._execute_module(
            'email',
            'send_email',
            recipients=recipients,
            subject=subject,
            content=content,
            attachments=attachments
        )
    
    async def _send_slack_message(self, channel: str, content: str, 
                                attachments: List[str]) -> Dict[str, Any]:
        """Send message to Slack channel"""
        # First upload any attachments
        file_urls = []
        for attachment in attachments:
            upload_result = await self._execute_module(
                'slack',
                'upload_file',
                channel=channel,
                file_path=attachment
            )
            if upload_result['status'] == 'success':
                file_urls.append(upload_result['result']['url'])
        
        # Send message with attachment URLs
        if file_urls:
            content += "\n\nAttachments:\n" + "\n".join(file_urls)
        
        return await self._execute_module(
            'slack',
            'send_message',
            channel=channel,
            message=content
        )
    
    async def _create_trello_card(self, list_id: str, title: str, 
                                description: str, comment: str = None,
                                attachments: List[str] = None) -> Dict[str, Any]:
        """Create Trello card and add attachments"""
        # Create card
        card_result = await self._execute_module(
            'trello',
            'create_card',
            list_id=list_id,
            title=title,
            description=description
        )
        
        if card_result['status'] != 'success':
            return card_result
        
        card_id = card_result['result']['id']
        
        # Add comment if provided
        if comment:
            await self._execute_module(
                'trello',
                'add_comment',
                card_id=card_id,
                comment=comment
            )
        
        # Add attachments if provided
        if attachments:
            for attachment in attachments:
                await self._execute_module(
                    'trello',
                    'add_attachment',
                    card_id=card_id,
                    file_path=attachment
                )
        
        return card_result
    
    def _create_action_list(self, results: List[tuple]) -> List[Dict[str, Any]]:
        """Create list of actions for the Slack listener"""
        actions = []
        
        # Create a summary message
        summary = "📨 Communication Summary:\n"
        for channel, result in results:
            status = "✅" if result['status'] == 'success' else "❌"
            summary += f"• {channel}: {status}\n"
        
        actions.append({
            'type': 'send_message',
            'text': summary
        })
        
        return actions 