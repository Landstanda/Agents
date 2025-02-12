#!/usr/bin/env python3

import unittest
import os
import shutil
import json
from datetime import datetime, timedelta
from src.modules.basic_auth import BasicAuthModule

class TestBasicAuthModule(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        # Use a test directory for credentials
        self.test_cred_dir = '.test_credentials'
        os.environ['CREDENTIALS_DIR'] = self.test_cred_dir
        self.auth = BasicAuthModule()
        
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_cred_dir):
            shutil.rmtree(self.test_cred_dir)
            
    def test_store_credentials(self):
        """Test storing credentials."""
        # Test storing new credentials
        success = self.auth.store_credentials('test_service', 'testuser', 'testpass')
        self.assertTrue(success)
        
        # Verify credentials file exists
        self.assertTrue(os.path.exists(os.path.join(self.test_cred_dir, 'basic_auth.json')))
        
        # Test storing credentials for same service, different user
        success = self.auth.store_credentials('test_service', 'testuser2', 'testpass2')
        self.assertTrue(success)
        
    def test_verify_credentials(self):
        """Test credential verification."""
        # Store test credentials
        self.auth.store_credentials('test_service', 'testuser', 'testpass')
        
        # Test valid credentials
        self.assertTrue(
            self.auth.verify_credentials('test_service', 'testuser', 'testpass')
        )
        
        # Test invalid password
        self.assertFalse(
            self.auth.verify_credentials('test_service', 'testuser', 'wrongpass')
        )
        
        # Test non-existent service
        self.assertFalse(
            self.auth.verify_credentials('fake_service', 'testuser', 'testpass')
        )
        
        # Test non-existent user
        self.assertFalse(
            self.auth.verify_credentials('test_service', 'fakeuser', 'testpass')
        )
        
    def test_session_management(self):
        """Test session creation and verification."""
        # Store test credentials
        self.auth.store_credentials('test_service', 'testuser', 'testpass')
        
        # Create session
        token = self.auth.create_session('test_service', 'testuser', 'testpass')
        self.assertIsNotNone(token)
        
        # Verify valid session
        is_valid, session_info = self.auth.verify_session(token)
        self.assertTrue(is_valid)
        self.assertEqual(session_info['service'], 'test_service')
        self.assertEqual(session_info['username'], 'testuser')
        
        # Test invalid token
        is_valid, session_info = self.auth.verify_session('invalid_token')
        self.assertFalse(is_valid)
        self.assertIsNone(session_info)
        
        # Test session expiration
        self.auth.sessions[token]['expires_at'] = datetime.now() - timedelta(hours=1)
        is_valid, session_info = self.auth.verify_session(token)
        self.assertFalse(is_valid)
        self.assertIsNone(session_info)
        
    def test_end_session(self):
        """Test ending sessions."""
        # Store test credentials and create session
        self.auth.store_credentials('test_service', 'testuser', 'testpass')
        token = self.auth.create_session('test_service', 'testuser', 'testpass')
        
        # End session
        self.assertTrue(self.auth.end_session(token))
        
        # Verify session is ended
        is_valid, _ = self.auth.verify_session(token)
        self.assertFalse(is_valid)
        
        # Test ending non-existent session
        self.assertFalse(self.auth.end_session('fake_token'))
        
    def test_remove_credentials(self):
        """Test removing credentials."""
        # Store test credentials
        self.auth.store_credentials('test_service', 'testuser', 'testpass')
        self.auth.store_credentials('test_service', 'testuser2', 'testpass2')
        
        # Remove credentials
        self.assertTrue(self.auth.remove_credentials('test_service', 'testuser'))
        
        # Verify credentials are removed
        self.assertFalse(
            self.auth.verify_credentials('test_service', 'testuser', 'testpass')
        )
        
        # Verify other credentials still exist
        self.assertTrue(
            self.auth.verify_credentials('test_service', 'testuser2', 'testpass2')
        )
        
        # Test removing non-existent credentials
        self.assertFalse(self.auth.remove_credentials('fake_service', 'fakeuser'))
        
    def test_encryption(self):
        """Test credential encryption."""
        # Store test credentials
        self.auth.store_credentials('test_service', 'testuser', 'testpass')
        
        # Read raw file content
        with open(os.path.join(self.test_cred_dir, 'basic_auth.json'), 'r') as f:
            raw_content = f.read()
            
        # Verify content is encrypted (not plain text)
        self.assertNotIn('test_service', raw_content)
        self.assertNotIn('testuser', raw_content)
        self.assertNotIn('testpass', raw_content)
        
        # Create new instance and verify credentials are still accessible
        new_auth = BasicAuthModule()
        self.assertTrue(
            new_auth.verify_credentials('test_service', 'testuser', 'testpass')
        )
        
if __name__ == '__main__':
    unittest.main() 