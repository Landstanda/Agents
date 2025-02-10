#!/usr/bin/env python3

from typing import Dict, Any, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import base64
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from googleapiclient.discovery import build

logger = get_logger(__name__)

class EmailSenderModule(BaseModule):
    """Module for sending emails and managing follow-ups using Gmail API"""
    
    def __init__(self, brain=None):
        super().__init__()
        self.brain = brain
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
        """Execute email sending operations"""
        try:
            self._initialize_service()
            
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            if operation == 'send_email':
                return self._send_email(params)
            elif operation == 'schedule_followup':
                return self._schedule_followup(params)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except Exception as e:
            logger.error(f"Email sending error: {str(e)}")
            raise
            
    def _send_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send an email using Gmail API"""
        to_address = params.get('to_address')
        response_data = params.get('response_data')
        
        if not to_address or not response_data:
            raise ValueError("To address and response data required")
            
        try:
            # Create message
            message = MIMEMultipart()
            message['to'] = to_address
            message['subject'] = response_data.get('subject')
            
            # Add body
            body = response_data.get('body')
            message.attach(MIMEText(body, 'plain'))
            
            # Encode the message
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode('utf-8')
            
            # Send via Gmail API
            sent_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"Email sent successfully to {to_address}")
            
            # Prepare result
            result = {
                'success': True,
                'message_id': sent_message['id'],
                'thread_id': sent_message['threadId'],
                'timestamp': datetime.now().isoformat(),
                'to_address': to_address,
                'subject': response_data.get('subject')
            }
            
            # Schedule follow-up if needed
            if response_data.get('follow_up_needed'):
                follow_up = self._schedule_followup({
                    'email_id': result['message_id'],
                    'follow_up_date': response_data.get('follow_up_date'),
                    'next_steps': response_data.get('next_steps', [])
                })
                result['follow_up'] = follow_up
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'to_address': to_address,
                'subject': response_data.get('subject')
            }
            
    def _schedule_followup(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a follow-up for an email"""
        email_id = params.get('email_id')
        follow_up_date = params.get('follow_up_date')
        next_steps = params.get('next_steps', [])
        
        if not email_id or not follow_up_date:
            raise ValueError("Email ID and follow-up date required")
            
        try:
            # Convert string date to datetime
            follow_up_datetime = datetime.fromisoformat(follow_up_date)
            
            # Add a label for follow-up
            label_name = 'Follow-up'
            
            # Create label if it doesn't exist
            try:
                labels = self.service.users().labels().list(userId='me').execute()
                label_id = next(
                    (label['id'] for label in labels['labels'] 
                     if label['name'] == label_name),
                    None
                )
                
                if not label_id:
                    label = self.service.users().labels().create(
                        userId='me',
                        body={'name': label_name}
                    ).execute()
                    label_id = label['id']
                    
            except Exception as e:
                logger.error(f"Failed to create/find label: {str(e)}")
                label_id = None
                
            # Store follow-up data
            follow_up_data = {
                'email_id': email_id,
                'follow_up_date': follow_up_datetime.isoformat(),
                'next_steps': next_steps,
                'status': 'scheduled'
            }
            
            # Add label to the email if we got one
            if label_id:
                self.service.users().messages().modify(
                    userId='me',
                    id=email_id,
                    body={'addLabelIds': [label_id]}
                ).execute()
                follow_up_data['label_id'] = label_id
                
            logger.info(f"Follow-up scheduled for {follow_up_date}")
            return follow_up_data
            
        except Exception as e:
            logger.error(f"Failed to schedule follow-up: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'email_id': email_id
            }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        if operation == 'send_email':
            return bool(params.get('to_address')) and bool(params.get('response_data'))
        elif operation == 'schedule_followup':
            return bool(params.get('email_id')) and bool(params.get('follow_up_date'))
            
        return False

    @property
    def capabilities(self) -> List[str]:
        return ['email_sending', 'followup_scheduling', 'gmail_integration'] 