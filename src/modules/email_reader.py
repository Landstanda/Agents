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
        self.service = None
        
    def _initialize_service(self):
        """Initialize Gmail API service"""
        if not self.service:
            from .google_auth import GoogleAuthModule
            auth_module = GoogleAuthModule()
            auth_result = auth_module.execute({})
            credentials = auth_result['credentials']
            self.service = build('gmail', 'v1', credentials=credentials)
            
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email reading operations"""
        try:
            self._initialize_service()
            
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            if operation == 'get_recent_emails':
                return self._get_recent_emails(params)
            elif operation == 'get_email_content':
                return self._get_email_content(params)
            elif operation == 'mark_as_read':
                return self._mark_as_read(params)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except Exception as e:
            logger.error(f"Email reader error: {str(e)}")
            raise
            
    def _get_recent_emails(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get recent unread emails"""
        max_results = params.get('max_results', 10)
        hours_ago = params.get('hours_ago', 24)
        
        # Calculate time range
        after_time = datetime.utcnow() - timedelta(hours=hours_ago)
        after_timestamp = int(after_time.timestamp())
        
        # Create query
        query = f'is:unread after:{after_timestamp}'
        if params.get('only_important'):
            query += ' is:important'
            
        # Get messages
        results = self.service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        emails = []
        
        for msg in messages:
            email_data = self._get_email_content({'message_id': msg['id']})
            if email_data:
                emails.append(email_data)
                
        return {
            'emails': emails,
            'count': len(emails)
        }
        
    def _get_email_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get content of a specific email"""
        message_id = params.get('message_id')
        if not message_id:
            raise ValueError("Message ID required")
            
        # Get the email data
        message = self.service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()
        
        # Extract headers
        headers = message['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
        from_email = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
        to_email = next((h['value'] for h in headers if h['name'].lower() == 'to'), '')
        date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
        
        # Extract body
        body = ''
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    body = base64.urlsafe_b64decode(
                        part['body']['data'].encode('UTF-8')
                    ).decode('utf-8')
                    break
        elif 'body' in message['payload']:
            body = base64.urlsafe_b64decode(
                message['payload']['body']['data'].encode('UTF-8')
            ).decode('utf-8')
            
        return {
            'message_id': message_id,
            'subject': subject,
            'from': from_email,
            'to': to_email,
            'date': date,
            'body': body,
            'labels': message['labelIds']
        }
        
    def _mark_as_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mark an email as read"""
        message_id = params.get('message_id')
        if not message_id:
            raise ValueError("Message ID required")
            
        self.service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        
        return {'message_id': message_id, 'status': 'read'}

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        if operation == 'get_recent_emails':
            return True
        elif operation == 'get_email_content':
            return bool(params.get('message_id'))
        elif operation == 'mark_as_read':
            return bool(params.get('message_id'))
            
        return False

    @property
    def capabilities(self) -> List[str]:
        return ['email_reading', 'gmail_integration', 'message_processing'] 