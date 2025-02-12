import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
from src.modules.google_auth import GoogleAuthModule
from src.utils.logging import get_logger

class TestGoogleAuthModule(unittest.TestCase):
    def setUp(self):
        """Set up test cases"""
        self.module = GoogleAuthModule()
        self.logger = get_logger(__name__)

    def test_init(self):
        """Test module initialization"""
        self.assertIsNotNone(self.module.SCOPES)
        self.assertIsNone(self.module.creds)
        self.assertEqual(self.module.token_path, 'token.pickle')
        self.assertEqual(self.module.credentials_path, 'credentials.json')

    def test_validate_params(self):
        """Test parameter validation"""
        self.assertTrue(self.module.validate_params({}))
        self.assertTrue(self.module.validate_params({'test': 'value'}))
        self.assertFalse(self.module.validate_params(None))
        self.assertFalse(self.module.validate_params([]))

    def test_capabilities(self):
        """Test that capabilities are properly defined"""
        capabilities = self.module.capabilities
        self.assertIsInstance(capabilities, list)
        self.assertIn('google_auth', capabilities)
        self.assertIn('oauth2', capabilities)
        self.assertIn('credentials', capabilities)

    @patch('builtins.open', new_callable=mock_open, read_data=b'mock_data')
    @patch('pickle.load')
    @patch('os.path.exists')
    def test_execute_existing_valid_token(self, mock_exists, mock_pickle_load, mock_file):
        """Test execution with existing valid token"""
        # Mock valid credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_pickle_load.return_value = mock_creds
        mock_exists.return_value = True

        result = self.module.execute({})
        
        self.assertEqual(result['credentials'], mock_creds)
        self.assertEqual(result['token_path'], self.module.token_path)
        self.assertEqual(result['scopes'], self.module.SCOPES)
        mock_exists.assert_called_with(self.module.token_path)
        mock_pickle_load.assert_called_once()
        mock_file.assert_called_with(self.module.token_path, 'rb')

    @patch('os.path.exists')
    def test_execute_missing_credentials(self, mock_exists):
        """Test execution with missing credentials file"""
        mock_exists.return_value = False
        
        with self.assertRaises(FileNotFoundError):
            self.module.execute({})

if __name__ == '__main__':
    unittest.main() 