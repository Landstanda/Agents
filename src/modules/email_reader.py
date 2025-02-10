#!/usr/bin/env python3

from typing import Dict, Any, List
import os
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
import email
from email.mime.text import MIMEText
from datetime import datetime, timedelta

logger = get_logger(__name__)

class EmailReaderModule(BaseModule):
    """Module for reading and processing emails from Gmail"""
    
    def __init__(self):
        super().__init__()
        self.service = None
        
    async def _initialize_service(self):
        """Initialize Gmail API service"""
        if not self.service:
            from .google_auth import GoogleAuthModule
            auth_module = GoogleAuthModule()
            auth_result = await auth_module.execute({})
            credentials = auth_result['credentials']
            self.service = build('gmail', 'v1', credentials=credentials)
            
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email reading operations"""
        try:
            await self._initialize_service()
            
            operation = params.get('operation', 'get_recent_emails')  # Default operation
            
            if operation == 'get_recent_emails':
                return await self._get_recent_emails(params)
            elif operation == 'get_email_content':
                return await self._get_email_content(params)
            elif operation == 'mark_as_read':
                return await self._mark_as_read(params)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except Exception as e:
            logger.error(f"Email reader error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _get_recent_emails(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get recent emails from Gmail"""
        try:
            max_results = params.get('max_emails', 10)
            query = 'is:unread' if params.get('unread_only', True) else ''
            
            # Get messages
            messages = []
            request = self.service.users().messages().list(
                userId='me',
                maxResults=max_results,
                q=query
            )
            response = request.execute()
            
            if 'messages' in response:
                for msg in response['messages']:
                    email_data = await self._get_email_content({'message_id': msg['id']})
                    if email_data.get('success'):
                        messages.append(email_data['email'])
            
            return {
                'success': True,
                'emails': messages,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get recent emails: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _get_email_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get content of a specific email"""
        try:
            message_id = params.get('message_id')
            if not message_id:
                raise ValueError("Message ID required")
                
            # Get the email data
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Parse headers
            headers = {}
            for header in message['payload']['headers']:
                headers[header['name'].lower()] = header['value']
                
            # Get body content
            parts = message['payload'].get('parts', [])
            body = ''
            
            if parts:
                for part in parts:
                    if part['mimeType'] == 'text/plain':
                        body = base64.urlsafe_b64decode(
                            part['body']['data']
                        ).decode('utf-8')
                        break
            else:
                # Handle messages with no parts
                data = message['payload']['body'].get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    
            # Prepare email data
            email_data = {
                'id': message_id,
                'thread_id': message['threadId'],
                'subject': headers.get('subject', ''),
                'from': headers.get('from', ''),
                'to': headers.get('to', ''),
                'date': headers.get('date', ''),
                'body': body,
                'labels': message['labelIds']
            }
            
            return {
                'success': True,
                'email': email_data
            }
            
        except Exception as e:
            logger.error(f"Failed to get email content: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _mark_as_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mark an email as read"""
        try:
            message_id = params.get('message_id')
            if not message_id:
                raise ValueError("Message ID required")
                
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            
            return {
                'success': True,
                'message_id': message_id
            }
            
        except Exception as e:
            logger.error(f"Failed to mark email as read: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation', 'get_recent_emails')
        
        if operation == 'get_recent_emails':
            return True  # No required params
        elif operation == 'get_email_content':
            return bool(params.get('message_id'))
        elif operation == 'mark_as_read':
            return bool(params.get('message_id'))
            
        return False
        
    @property
    def capabilities(self) -> List[str]:
        """Return module capabilities"""
        return [
            'read_emails',
            'get_email_content',
            'mark_as_read',
            'gmail_integration'
        ] 