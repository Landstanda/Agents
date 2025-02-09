#!/usr/bin/env python3

from typing import Dict, Any, List
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger

logger = get_logger(__name__)

class EmailSenderModule(BaseModule):
    """Module for sending emails and managing follow-ups"""
    
    def __init__(self, smtp_config: Dict[str, Any] = None):
        self.smtp_config = smtp_config or {}
        self._validate_smtp_config()
        
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email sending operations"""
        try:
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
        """Send an email using SMTP"""
        to_address = params.get('to_address')
        response_data = params.get('response_data')
        
        if not to_address or not response_data:
            raise ValueError("To address and response data required")
            
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config.get('from_address')
            msg['To'] = to_address
            msg['Subject'] = response_data.get('subject')
            
            # Add body
            body = response_data.get('body')
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_config.get('smtp_server'), 
                            self.smtp_config.get('smtp_port')) as server:
                if self.smtp_config.get('use_tls'):
                    server.starttls()
                
                server.login(self.smtp_config.get('username'),
                           self.smtp_config.get('password'))
                
                # Send email
                server.send_message(msg)
                
            logger.info(f"Email sent successfully to {to_address}")
            
            # Prepare result
            result = {
                'success': True,
                'message_id': msg.get('Message-ID'),
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
            
            # Store follow-up in database or task system
            # This is a placeholder - implement according to your system
            follow_up_data = {
                'email_id': email_id,
                'follow_up_date': follow_up_datetime.isoformat(),
                'next_steps': next_steps,
                'status': 'scheduled'
            }
            
            logger.info(f"Follow-up scheduled for {follow_up_date}")
            return follow_up_data
            
        except Exception as e:
            logger.error(f"Failed to schedule follow-up: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'email_id': email_id
            }
            
    def _validate_smtp_config(self):
        """Validate SMTP configuration"""
        required_fields = [
            'smtp_server',
            'smtp_port',
            'username',
            'password',
            'from_address'
        ]
        
        for field in required_fields:
            if field not in self.smtp_config:
                raise ValueError(f"Missing required SMTP config field: {field}")
                
        # Validate port number
        try:
            port = int(self.smtp_config['smtp_port'])
            if port < 1 or port > 65535:
                raise ValueError("Invalid SMTP port number")
        except ValueError as e:
            raise ValueError(f"Invalid SMTP port: {str(e)}")

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
        return ['email_sending', 'followup_scheduling'] 