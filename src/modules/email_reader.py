#!/usr/bin/env python3

from typing import Dict, Any, List, Optional
import os
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
import email
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import asyncio
from src.utils.credential_manager import CredentialManager

logger = get_logger(__name__)

class EmailReader(BaseModule):
    """Module for searching and reading emails using Gmail API"""
    
    def __init__(self):
        super().__init__()
        self.service = None
        self.cred_manager = CredentialManager()
        
    async def _initialize_service(self):
        """Initialize Gmail API service"""
        if not self.service:
            credentials = await self.cred_manager.get_credentials('gmail')
            self.service = build('gmail', 'v1', credentials=credentials)
            
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email reading operations"""
        try:
            await self._initialize_service()
            
            action = params.get('action')
            if not action:
                raise ValueError("No action specified")
                
            actions = {
                'search': self._search_emails,
                'process_emails': self._process_emails,
                'validate_email': self._validate_email
            }
            
            if action not in actions:
                raise ValueError(f"Unknown action: {action}")
                
            return await actions[action](params)
                
        except Exception as e:
            logger.error(f"Email reader error: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _search_emails(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search emails based on filters"""
        try:
            filter_type = params.get('filter_type', 'all')
            query = params.get('query', '')
            date_range = params.get('date_range', 'today')
            folder = params.get('folder', 'INBOX')
            max_results = params.get('max_results', 10)
            
            # Build search query
            search_query = []
            
            # Add folder/label
            if folder.upper() != 'INBOX':
                search_query.append(f'label:{folder}')
            
            # Add date range
            date_map = {
                'today': 'newer_than:1d',
                'week': 'newer_than:7d',
                'month': 'newer_than:30d',
                'year': 'newer_than:365d'
            }
            if date_range in date_map:
                search_query.append(date_map[date_range])
                
            # Add filter type
            filter_map = {
                'unread': 'is:unread',
                'important': 'is:important',
                'starred': 'is:starred',
                'sent': 'in:sent',
                'draft': 'is:draft'
            }
            if filter_type in filter_map:
                search_query.append(filter_map[filter_type])
                
            # Add search query
            if query:
                search_query.append(query)
                
            # Execute search
            results = self.service.users().messages().list(
                userId='me',
                q=' '.join(search_query),
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            return {
                'status': 'success',
                'results': True if messages else False,
                'email_ids': [msg['id'] for msg in messages],
                'total_results': len(messages)
            }
            
        except Exception as e:
            logger.error(f"Failed to search emails: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _process_emails(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process a list of email IDs and return their contents"""
        try:
            email_ids = params.get('email_ids', [])
            include_attachments = params.get('include_attachments', False)
            
            if not email_ids:
                return {
                    'status': 'error',
                    'error': 'No email IDs provided'
                }
                
            processed_emails = []
            
            for email_id in email_ids:
                message = self.service.users().messages().get(
                    userId='me',
                    id=email_id,
                    format='full'
                ).execute()
                
                # Extract headers
                headers = {}
                for header in message['payload']['headers']:
                    headers[header['name'].lower()] = header['value']
                    
                # Get body
                body = self._get_email_body(message['payload'])
                
                # Get attachments if requested
                attachments = []
                if include_attachments:
                    attachments = self._get_attachments(message['payload'])
                    
                processed_emails.append({
                    'id': email_id,
                    'thread_id': message['threadId'],
                    'subject': headers.get('subject', ''),
                    'from': headers.get('from', ''),
                    'to': headers.get('to', ''),
                    'date': headers.get('date', ''),
                    'body': body,
                    'attachments': attachments,
                    'labels': message.get('labelIds', [])
                })
                
            return {
                'status': 'success',
                'processed': True,
                'emails': processed_emails,
                'count': len(processed_emails)
            }
            
        except Exception as e:
            logger.error(f"Failed to process emails: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _validate_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that an email ID exists and is accessible"""
        try:
            email_id = params.get('email_id')
            
            if not email_id:
                return {
                    'status': 'error',
                    'error': 'No email ID provided'
                }
                
            # Try to get the email
            message = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='minimal'
            ).execute()
            
            return {
                'status': 'success',
                'valid': True,
                'email_id': email_id,
                'thread_id': message.get('threadId')
            }
            
        except Exception as e:
            logger.error(f"Failed to validate email: {str(e)}")
            return {
                'status': 'error',
                'valid': False,
                'error': str(e)
            }
            
    def _get_email_body(self, payload: Dict[str, Any]) -> str:
        """Extract email body from payload"""
        if payload.get('body', {}).get('data'):
            return base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode('utf-8')
            
        if payload.get('parts'):
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    return base64.urlsafe_b64decode(
                        part['body']['data']
                    ).decode('utf-8')
                    
        return ''
        
    def _get_attachments(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract attachment information from payload"""
        attachments = []
        
        if payload.get('parts'):
            for part in payload['parts']:
                if part.get('filename'):
                    attachments.append({
                        'id': part['body'].get('attachmentId'),
                        'filename': part['filename'],
                        'mime_type': part['mimeType'],
                        'size': part['body'].get('size', 0)
                    })
                    
        return attachments

    @property
    def capabilities(self) -> List[str]:
        return [
            'email_search',
            'email_reading',
            'attachment_listing',
            'email_validation'
        ] 