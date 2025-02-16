from typing import Dict, Any, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
import base64
import os
from src.core.module_interface import BaseModule
import logging
from googleapiclient.discovery import build
from src.utils.credential_manager import CredentialManager
from .gpt_handler import GPTHandler

logger = logging.getLogger(__name__)

class EmailComposer(BaseModule):
    """Module for composing and sending emails using Gmail API"""
    
    def __init__(self):
        super().__init__()
        self.service = None
        self.cred_manager = CredentialManager()
        self.gpt_handler = GPTHandler()
        
    async def _initialize_service(self):
        """Initialize Gmail API service"""
        if not self.service:
            credentials = await self.cred_manager.get_credentials('gmail')
            self.service = build('gmail', 'v1', credentials=credentials)
            
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email composition and sending operations"""
        try:
            await self._initialize_service()
            
            action = params.get('action')
            if not action:
                raise ValueError("No action specified")
                
            actions = {
                'validate_addresses': self._validate_addresses,
                'generate_content': self._generate_content,
                'prepare': self._prepare_email,
                'prepare_attachments': self._prepare_attachments,
                'send': self._send_email
            }
            
            if action not in actions:
                raise ValueError(f"Unknown action: {action}")
                
            return await actions[action](params)
                
        except Exception as e:
            logger.error(f"Email composer error: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _validate_addresses(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate email addresses"""
        addresses = params.get('addresses', [])
        cc = params.get('cc', [])
        bcc = params.get('bcc', [])
        
        all_addresses = addresses + cc + bcc
        invalid_addresses = []
        
        for address in all_addresses:
            if not self._is_valid_email(address):
                invalid_addresses.append(address)
                
        return {
            'status': 'success' if not invalid_addresses else 'error',
            'all_valid': not invalid_addresses,
            'invalid_addresses': invalid_addresses
        }
        
    async def _generate_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate email content using GPT"""
        try:
            if params.get('original_email'):
                # This is a reply
                return await self.gpt_handler.execute({
                    'action': 'compose_reply',
                    'original_email': params['original_email'],
                    'response_type': params.get('response_type', 'standard'),
                    'key_points': params.get('key_points', []),
                    'context': params.get('context', ''),
                    'tone': params.get('tone', 'professional')
                })
            else:
                # This is a new email
                return await self.gpt_handler.execute({
                    'action': 'compose_email',
                    'subject': params['subject'],
                    'purpose': params['purpose'],
                    'recipients': params['to'],
                    'context': params.get('context', ''),
                    'tone': params.get('tone', 'professional')
                })
                
        except Exception as e:
            logger.error(f"Failed to generate content: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _prepare_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare email draft"""
        required_params = ['to', 'subject']
        if not all(params.get(p) for p in required_params):
            raise ValueError(f"Missing required parameters: {required_params}")
            
        try:
            # Generate content if not provided
            if not params.get('content'):
                content_result = await self._generate_content(params)
                if content_result['status'] != 'success':
                    return content_result
                params['content'] = content_result['content']
            
            message = MIMEMultipart()
            message['to'] = self._format_addresses(params['to'])
            message['subject'] = params['subject']
            
            if params.get('cc'):
                message['cc'] = self._format_addresses(params['cc'])
            if params.get('bcc'):
                message['bcc'] = self._format_addresses(params['bcc'])
                
            # Handle content
            message.attach(MIMEText(params['content'], 'plain'))
            
            # Create draft
            draft = self.service.users().drafts().create(
                userId='me',
                body={
                    'message': {
                        'raw': base64.urlsafe_b64encode(
                            message.as_bytes()
                        ).decode('utf-8')
                    }
                }
            ).execute()
            
            return {
                'status': 'success',
                'draft_id': draft['id'],
                'message_id': draft['message']['id'],
                'content': params['content']
            }
            
        except Exception as e:
            logger.error(f"Failed to prepare email: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _prepare_attachments(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare email attachments"""
        attachments = params.get('attachments', [])
        draft_id = params.get('draft_id')
        
        if not draft_id:
            raise ValueError("draft_id is required")
            
        try:
            # Get the draft
            draft = self.service.users().drafts().get(
                userId='me',
                id=draft_id
            ).execute()
            
            message = draft['message']
            raw_message = base64.urlsafe_b64decode(message['raw'])
            email_message = MIMEMultipart()
            email_message.parse(raw_message)
            
            # Add attachments
            for attachment in attachments:
                if os.path.exists(attachment):
                    with open(attachment, 'rb') as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(attachment))
                        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment)}"'
                        email_message.attach(part)
                        
            # Update draft
            updated_draft = self.service.users().drafts().update(
                userId='me',
                id=draft_id,
                body={
                    'message': {
                        'raw': base64.urlsafe_b64encode(
                            email_message.as_bytes()
                        ).decode('utf-8')
                    }
                }
            ).execute()
            
            return {
                'status': 'success',
                'draft_id': updated_draft['id'],
                'attachments_added': len(attachments)
            }
            
        except Exception as e:
            logger.error(f"Failed to prepare attachments: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _send_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send prepared email draft"""
        draft_id = params.get('draft_id')
        if not draft_id:
            raise ValueError("draft_id is required")
            
        try:
            # Send the draft
            sent_message = self.service.users().drafts().send(
                userId='me',
                body={'id': draft_id}
            ).execute()
            
            return {
                'status': 'success',
                'sent': True,
                'message_id': sent_message['id'],
                'thread_id': sent_message.get('threadId'),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    def _is_valid_email(self, email: str) -> bool:
        """Basic email validation"""
        return '@' in email and '.' in email.split('@')[1]
        
    def _format_addresses(self, addresses: List[str]) -> str:
        """Format list of addresses into comma-separated string"""
        return ', '.join(addresses)

    @property
    def capabilities(self) -> List[str]:
        return [
            'email_composition',
            'email_sending',
            'attachment_handling',
            'address_validation'
        ] 