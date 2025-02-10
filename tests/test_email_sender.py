#!/usr/bin/env python3

import unittest
from src.modules.email_sender import EmailSenderModule
import logging
from datetime import datetime, timedelta

# Disable unnecessary logging during tests
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

class TestEmailSenderModule(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        self.sender = EmailSenderModule()
        
    def test_service_initialization(self):
        """Test Gmail service initialization."""
        try:
            self.sender._initialize_service()
            self.assertIsNotNone(self.sender.service)
            print("✓ Gmail service initialized successfully")
        except Exception as e:
            self.fail(f"Failed to initialize Gmail service: {str(e)}")
            
    def test_send_email(self):
        """Test sending an email."""
        try:
            # Send a test email
            result = self.sender.execute({
                'operation': 'send_email',
                'to_address': 'mirror.aphrodite.ca@gmail.com',  # Send to self for testing
                'response_data': {
                    'subject': 'Test Email from Aphrodite Agent',
                    'body': 'This is a test email sent by the EmailSenderModule test suite.\n\n'
                           'If you receive this, the Gmail API integration is working correctly.'
                }
            })
            
            # Verify the result
            self.assertTrue(result['success'])
            self.assertIn('message_id', result)
            self.assertIn('thread_id', result)
            print(f"✓ Test email sent successfully")
            print(f"  Message ID: {result['message_id']}")
            print(f"  Thread ID: {result['thread_id']}")
            
            return result  # Return for use in follow-up test
            
        except Exception as e:
            self.fail(f"Failed to send email: {str(e)}")
            
    def test_schedule_followup(self):
        """Test scheduling a follow-up."""
        try:
            # First send a test email
            send_result = self.test_send_email()
            
            # Schedule a follow-up
            follow_up_date = (datetime.now() + timedelta(days=1)).isoformat()
            result = self.sender.execute({
                'operation': 'schedule_followup',
                'email_id': send_result['message_id'],
                'follow_up_date': follow_up_date,
                'next_steps': ['Review response', 'Send follow-up email']
            })
            
            # Verify the result
            self.assertEqual(result['email_id'], send_result['message_id'])
            self.assertEqual(result['status'], 'scheduled')
            self.assertIn('label_id', result)  # Should have created/used Follow-up label
            print(f"✓ Follow-up scheduled successfully")
            print(f"  Follow-up date: {result['follow_up_date']}")
            
        except Exception as e:
            self.fail(f"Failed to schedule follow-up: {str(e)}")
            
    def test_parameter_validation(self):
        """Test parameter validation."""
        # Test invalid operation
        with self.assertRaises(ValueError):
            self.sender.execute({
                'operation': 'invalid_operation'
            })
            
        # Test missing to_address
        with self.assertRaises(ValueError):
            self.sender.execute({
                'operation': 'send_email',
                'response_data': {'subject': 'Test', 'body': 'Test'}
            })
            
        # Test missing response_data
        with self.assertRaises(ValueError):
            self.sender.execute({
                'operation': 'send_email',
                'to_address': 'test@example.com'
            })
            
        # Test missing operation
        with self.assertRaises(ValueError):
            self.sender.execute({})
            
        print("✓ Parameter validation working correctly")
        
if __name__ == '__main__':
    unittest.main() 