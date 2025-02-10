#!/usr/bin/env python3

import unittest
import pandas as pd
from src.modules.data_cleaner import DataCleanerModule

class TestDataCleanerModule(unittest.TestCase):
    def setUp(self):
        self.cleaner = DataCleanerModule()
        
    def test_normalize_text(self):
        """Test text normalization"""
        # Test basic normalization
        self.assertEqual(self.cleaner.normalize_text("  Hello   World  "), "hello world")
        
        # Test unicode normalization
        self.assertEqual(self.cleaner.normalize_text("café"), "cafe")
        
        # Test with non-string input
        self.assertEqual(self.cleaner.normalize_text(123), "123")
        
        # Test with case preservation
        self.assertEqual(
            self.cleaner.normalize_text("Hello World", lowercase=False),
            "Hello World"
        )
        
    def test_standardize_date(self):
        """Test date standardization"""
        # Test various date formats
        self.assertEqual(self.cleaner.standardize_date("2024-02-09"), "2024-02-09")  # ISO format
        self.assertEqual(self.cleaner.standardize_date("09/02/2024"), "2024-02-09")  # DD/MM/YYYY
        self.assertEqual(self.cleaner.standardize_date("09-02-2024"), "2024-02-09")  # DD-MM-YYYY
        self.assertEqual(self.cleaner.standardize_date("09.02.2024"), "2024-02-09")  # DD.MM.YYYY
        
        # Test invalid dates
        self.assertIsNone(self.cleaner.standardize_date("invalid"))
        self.assertIsNone(self.cleaner.standardize_date("2024-13-45"))  # Invalid month/day
        self.assertIsNone(self.cleaner.standardize_date("35/12/2024"))  # Invalid day
        
    def test_remove_duplicates(self):
        """Test duplicate removal"""
        # Test with simple list
        data = [1, 2, 2, 3, 3, 4]
        self.assertEqual(self.cleaner.remove_duplicates(data), [1, 2, 3, 4])
        
        # Test with mixed types
        data = [1, "2", 2, "2", 3]
        self.assertEqual(self.cleaner.remove_duplicates(data), [1, "2", 2, 3])
        
        # Test order preservation
        data = ["b", "a", "b", "c"]
        self.assertEqual(self.cleaner.remove_duplicates(data), ["b", "a", "c"])
        
    def test_clean_dict(self):
        """Test dictionary cleaning"""
        data = {
            "name": "  John   Doe  ",
            "date": "2024-02-09",
            "items": ["a", "a", "b"],
            "nested": {"key": "  Value  "}
        }
        
        cleaned = self.cleaner.clean_dict(data)
        self.assertEqual(cleaned["name"], "john doe")
        self.assertEqual(cleaned["date"], "2024-02-09")
        self.assertEqual(cleaned["items"], ["a", "b"])
        self.assertEqual(cleaned["nested"]["key"], "value")
        
    def test_standardize_phone(self):
        """Test phone number standardization"""
        # Test US numbers
        self.assertEqual(self.cleaner.standardize_phone("123-456-7890"), "+11234567890")
        self.assertEqual(self.cleaner.standardize_phone("(123) 456-7890"), "+11234567890")
        
        # Test with country code
        self.assertEqual(self.cleaner.standardize_phone("+1-123-456-7890"), "+11234567890")
        
        # Test invalid numbers
        self.assertIsNone(self.cleaner.standardize_phone("123"))
        self.assertIsNone(self.cleaner.standardize_phone("invalid"))
        
    def test_clean_email(self):
        """Test email cleaning"""
        # Test valid emails
        self.assertEqual(self.cleaner.clean_email("Test@Example.com"), "test@example.com")
        self.assertEqual(
            self.cleaner.clean_email("user.name+tag@example.com"),
            "user.name+tag@example.com"
        )
        
        # Test invalid emails
        self.assertIsNone(self.cleaner.clean_email("invalid"))
        self.assertIsNone(self.cleaner.clean_email("test@"))
        self.assertIsNone(self.cleaner.clean_email("@example.com"))
        
    def test_clean_dataframe(self):
        """Test DataFrame cleaning"""
        # Create test DataFrame
        df = pd.DataFrame({
            'name': ['  John  ', ' Jane '],
            'date': ['2024-02-09', '09/02/2024'],
            'email': ['TEST@example.com', 'invalid']
        })
        
        cleaned_df = self.cleaner.clean_dataframe(df, date_columns=['date'])
        
        # Check cleaning results
        self.assertEqual(cleaned_df['name'][0], "john")
        self.assertEqual(cleaned_df['date'][0], "2024-02-09")
        self.assertEqual(cleaned_df['email'][0], "test@example.com")
        
    def test_clean_json(self):
        """Test JSON cleaning"""
        # Test valid JSON
        json_str = '''
        {
            "name": "  John   Doe  ",
            "date": "2024-02-09",
            "items": ["a", "a", "b"],
            "contact": {
                "email": "TEST@example.com",
                "phone": "123-456-7890"
            }
        }
        '''
        
        cleaned = self.cleaner.clean_json(json_str)
        self.assertIsNotNone(cleaned)
        
        # Verify cleaned data
        import json
        data = json.loads(cleaned)
        self.assertEqual(data["name"], "john doe")
        self.assertEqual(data["date"], "2024-02-09")
        self.assertEqual(data["items"], ["a", "b"])
        self.assertEqual(data["contact"]["email"], "test@example.com")
        
        # Test invalid JSON
        self.assertIsNone(self.cleaner.clean_json("invalid"))
        
if __name__ == '__main__':
    unittest.main() 