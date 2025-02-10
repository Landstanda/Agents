#!/usr/bin/env python3

import unittest
from src.modules.html_parser import HTMLParserModule

class TestHTMLParserModule(unittest.TestCase):
    def setUp(self):
        self.parser = HTMLParserModule()
        self.sample_html = """
        <html>
            <head>
                <title>Test Page</title>
                <script>console.log('test');</script>
                <style>.test { color: red; }</style>
            </head>
            <body>
                <h1>Welcome to Test Page</h1>
                <p class="content">This is a test paragraph.</p>
                <a href="/test" title="Test Link">Click here</a>
                <a href="https://example.com">External Link</a>
                
                <table>
                    <tr>
                        <th>Header 1</th>
                        <th>Header 2</th>
                    </tr>
                    <tr>
                        <td>Data 1</td>
                        <td>Data 2</td>
                    </tr>
                </table>
                
                <form action="/submit" method="POST">
                    <input type="text" name="username" required>
                    <input type="password" name="password" required>
                    <textarea name="message"></textarea>
                    <input type="submit" value="Submit">
                </form>
            </body>
        </html>
        """
        
    def test_load_html(self):
        """Test loading HTML content"""
        self.assertTrue(self.parser.load_html(self.sample_html))
        self.assertFalse(self.parser.load_html(None))
        
    def test_extract_text(self):
        """Test extracting text content"""
        self.parser.load_html(self.sample_html)
        
        # Test full text extraction
        full_text = self.parser.extract_text()
        self.assertIn("Welcome to Test Page", full_text)
        self.assertIn("This is a test paragraph", full_text)
        
        # Test selective text extraction
        h1_text = self.parser.extract_text("h1")
        self.assertEqual(h1_text, "Welcome to Test Page")
        
        # Test with invalid selector
        invalid_text = self.parser.extract_text("#nonexistent")
        self.assertEqual(invalid_text, "")
        
    def test_extract_links(self):
        """Test extracting links"""
        self.parser.load_html(self.sample_html)
        links = self.parser.extract_links(base_url="https://test.com")
        
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]['text'], "Click here")
        self.assertEqual(links[0]['title'], "Test Link")
        self.assertEqual(links[0]['url'], "https://test.com/test")
        self.assertEqual(links[1]['url'], "https://example.com")
        
    def test_extract_tables(self):
        """Test extracting tables"""
        self.parser.load_html(self.sample_html)
        tables = self.parser.extract_tables()
        
        self.assertEqual(len(tables), 1)
        self.assertEqual(len(tables[0]), 2)  # Two rows
        self.assertEqual(tables[0][0], ["Header 1", "Header 2"])  # Header row
        self.assertEqual(tables[0][1], ["Data 1", "Data 2"])  # Data row
        
    def test_extract_forms(self):
        """Test extracting forms"""
        self.parser.load_html(self.sample_html)
        forms = self.parser.extract_forms()
        
        self.assertEqual(len(forms), 1)
        form = forms[0]
        self.assertEqual(form['action'], "/submit")
        self.assertEqual(form['method'], "POST")
        
        fields = form['fields']
        self.assertEqual(len(fields), 4)  # text, password, textarea, submit
        
        # Check username field
        username_field = next(f for f in fields if f['name'] == 'username')
        self.assertEqual(username_field['type'], 'text')
        self.assertTrue(username_field['required'])
        
    def test_find_elements(self):
        """Test finding elements by selector"""
        self.parser.load_html(self.sample_html)
        
        # Find paragraph
        paragraphs = self.parser.find_elements("p.content")
        self.assertEqual(len(paragraphs), 1)
        self.assertEqual(paragraphs[0]['text'].rstrip('.'), "This is a test paragraph")
        self.assertEqual(paragraphs[0]['class'], ['content'])
        
        # Find non-existent element
        nothing = self.parser.find_elements("#nonexistent")
        self.assertEqual(len(nothing), 0)
        
    def test_clean_html(self):
        """Test cleaning HTML content"""
        cleaned = self.parser.clean_html(self.sample_html)
        
        # Scripts and styles should be removed
        self.assertNotIn("<script>", cleaned)
        self.assertNotIn("<style>", cleaned)
        self.assertIn("<h1>", cleaned)  # Regular content should remain
        
if __name__ == '__main__':
    unittest.main() 