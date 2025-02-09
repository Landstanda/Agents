import unittest
from src.modules.browser_headers import BrowserHeadersModule
from src.utils.logging import get_logger

class TestBrowserHeadersModule(unittest.TestCase):
    def setUp(self):
        """Set up test cases"""
        self.module = BrowserHeadersModule()
        self.logger = get_logger(__name__)

    def test_default_headers(self):
        """Test that default headers are properly initialized"""
        self.assertIn('User-Agent', self.module.default_headers)
        self.assertIn('Accept', self.module.default_headers)
        self.assertIn('Accept-Language', self.module.default_headers)
        self.assertIn('Connection', self.module.default_headers)

    def test_execute_empty_params(self):
        """Test execution with empty parameters"""
        result = self.module.execute({})
        self.assertIn('headers', result)
        self.assertEqual(result['headers'], self.module.default_headers)

    def test_execute_with_custom_headers(self):
        """Test execution with custom headers"""
        custom_headers = {'Custom-Header': 'Test-Value'}
        params = {'headers': custom_headers}
        result = self.module.execute(params)
        
        # Check that custom headers are preserved
        self.assertIn('Custom-Header', result['headers'])
        self.assertEqual(result['headers']['Custom-Header'], 'Test-Value')
        
        # Check that default headers are still present
        for key in self.module.default_headers:
            self.assertIn(key, result['headers'])

    def test_validate_params(self):
        """Test parameter validation"""
        # Valid parameters
        self.assertTrue(self.module.validate_params({}))
        self.assertTrue(self.module.validate_params({'headers': {}}))
        
        # Invalid parameters
        self.assertFalse(self.module.validate_params(None))
        self.assertFalse(self.module.validate_params([]))
        self.assertFalse(self.module.validate_params("invalid"))

    def test_capabilities(self):
        """Test that capabilities are properly defined"""
        capabilities = self.module.capabilities
        self.assertIsInstance(capabilities, list)
        self.assertIn('browser_headers', capabilities)
        self.assertIn('web_request_headers', capabilities)

if __name__ == '__main__':
    unittest.main() 