#!/usr/bin/env python3

import unittest
from src.modules.email_reader import EmailReaderModule
import logging

# Disable unnecessary logging during tests
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

class TestEmailReaderModule(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        self.reader = EmailReaderModule()
        
    def test_service_initialization(self):
        """Test Gmail service initialization."""
        try:
            self.reader._initialize_service()
            self.assertIsNotNone(self.reader.service)
            print("✓ Gmail service initialized successfully")
        except Exception as e:
            self.fail(f"Failed to initialize Gmail service: {str(e)}")
            
    def test_get_recent_emails(self):
        """Test retrieving recent emails."""
        try:
            # Test with default parameters
            result = self.reader.execute({
                'operation': 'get_recent_emails',
                'max_results': 5,
                'hours_ago': 24
            })
            
            self.assertIn('emails', result)
            self.assertIn('count', result)
            self.assertIsInstance(result['emails'], list)
            print(f"✓ Retrieved {result['count']} recent emails")
            
            # Test with important emails only
            result = self.reader.execute({
                'operation': 'get_recent_emails',
                'max_results': 5,
                'hours_ago': 24,
                'only_important': True
            })
            
            self.assertIn('emails', result)
            print(f"✓ Retrieved {result['count']} important emails")
            
        except Exception as e:
            self.fail(f"Failed to get recent emails: {str(e)}")
            
    def test_get_email_content(self):
        """Test retrieving specific email content."""
        try:
            # First get a message ID from recent emails
            result = self.reader.execute({
                'operation': 'get_recent_emails',
                'max_results': 1
            })
            
            if result['count'] > 0:
                message_id = result['emails'][0]['message_id']
                
                # Test getting content of that email
                email_content = self.reader.execute({
                    'operation': 'get_email_content',
                    'message_id': message_id
                })
                
                # Verify email content structure
                self.assertIn('subject', email_content)
                self.assertIn('from', email_content)
                self.assertIn('to', email_content)
                self.assertIn('date', email_content)
                self.assertIn('body', email_content)
                self.assertIn('labels', email_content)
                
                print(f"✓ Successfully retrieved email content")
                print(f"  Subject: {email_content['subject']}")
                
        except Exception as e:
            self.fail(f"Failed to get email content: {str(e)}")
            
    def test_mark_as_read(self):
        """Test marking an email as read."""
        try:
            # Get an unread email first
            result = self.reader.execute({
                'operation': 'get_recent_emails',
                'max_results': 1
            })
            
            if result['count'] > 0:
                message_id = result['emails'][0]['message_id']
                
                # Mark it as read
                mark_result = self.reader.execute({
                    'operation': 'mark_as_read',
                    'message_id': message_id
                })
                
                self.assertEqual(mark_result['status'], 'read')
                print(f"✓ Successfully marked email as read")
                
        except Exception as e:
            self.fail(f"Failed to mark email as read: {str(e)}")
            
    def test_parameter_validation(self):
        """Test parameter validation."""
        # Test invalid operation
        with self.assertRaises(ValueError):
            self.reader.execute({
                'operation': 'invalid_operation'
            })
            
        # Test missing message_id
        with self.assertRaises(ValueError):
            self.reader.execute({
                'operation': 'get_email_content'
            })
            
        # Test missing operation
        with self.assertRaises(ValueError):
            self.reader.execute({})
            
        print("✓ Parameter validation working correctly")
        
if __name__ == '__main__':
    unittest.main() 