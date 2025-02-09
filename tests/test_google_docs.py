#!/usr/bin/env python3

import unittest
import logging
from src.modules.google_docs import GoogleDocsModule

# Disable unnecessary logging during tests
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

class TestGoogleDocsModule(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        self.docs = GoogleDocsModule()
        self.test_title = "Test Document - Aphrodite"
        
    def test_service_initialization(self):
        """Test Google Docs service initialization."""
        try:
            self.docs._initialize_service()
            self.assertIsNotNone(self.docs.service)
            print("✓ Docs service initialized successfully")
        except Exception as e:
            self.fail(f"Failed to initialize Docs service: {str(e)}")
            
    def test_document_creation(self):
        """Test creating a new document."""
        try:
            result = self.docs.execute({
                'operation': 'create_document',
                'title': self.test_title,
                'content': 'This is a test document created by Aphrodite Agent.'
            })
            
            self.assertTrue(result['success'])
            self.assertIn('document_id', result)
            self.assertEqual(result['title'], self.test_title)
            
            # Store document_id for other tests
            self.document_id = result['document_id']
            print(f"✓ Created test document: {result['url']}")
            
            return result['document_id']
            
        except Exception as e:
            self.fail(f"Failed to create document: {str(e)}")
            
    def test_content_operations(self):
        """Test content manipulation operations."""
        try:
            # First create a document
            document_id = self.test_document_creation()
            
            # Get document content
            get_result = self.docs.execute({
                'operation': 'get_document',
                'document_id': document_id
            })
            
            self.assertTrue(get_result['success'])
            print(f"✓ Retrieved document content")
            
            # Insert additional text
            insert_result = self.docs.execute({
                'operation': 'insert_text',
                'document_id': document_id,
                'text': '\n\nAdditional test content.',
                'index': len(get_result['document']['body']['content'])
            })
            
            self.assertTrue(insert_result['success'])
            print(f"✓ Inserted additional text")
            
            # Format text
            format_result = self.docs.execute({
                'operation': 'format_text',
                'document_id': document_id,
                'start_index': 1,
                'end_index': 20,
                'format_options': {
                    'bold': True,
                    'fontSize': {'magnitude': 14, 'unit': 'PT'}
                }
            })
            
            self.assertTrue(format_result['success'])
            print(f"✓ Applied text formatting")
            
            return document_id
            
        except Exception as e:
            self.fail(f"Content operations failed: {str(e)}")
            
    def test_table_operations(self):
        """Test table creation and manipulation."""
        try:
            # Use document from content operations
            document_id = self.test_content_operations()
            
            # Get current document length
            get_result = self.docs.execute({
                'operation': 'get_document',
                'document_id': document_id
            })
            end_index = len(get_result['document']['body']['content'])
            
            # Create table
            table_result = self.docs.execute({
                'operation': 'create_table',
                'document_id': document_id,
                'rows': 3,
                'columns': 3,
                'index': end_index
            })
            
            self.assertTrue(table_result['success'])
            print(f"✓ Created table")
            
            # Insert row
            row_result = self.docs.execute({
                'operation': 'insert_table_row',
                'document_id': document_id,
                'table_index': 0,  # First table in the document
                'row_index': 2
            })
            
            self.assertTrue(row_result['success'])
            print(f"✓ Inserted table row")
            
            return document_id
            
        except Exception as e:
            self.fail(f"Table operations failed: {str(e)}")
            
    def test_header_footer_operations(self):
        """Test header and footer operations."""
        try:
            # Use document from table operations
            document_id = self.test_table_operations()
            
            # Create header
            header_result = self.docs.execute({
                'operation': 'create_header',
                'document_id': document_id,
                'text': 'Test Document Header'
            })
            
            self.assertTrue(header_result['success'])
            print(f"✓ Created header")
            
            # Create footer
            footer_result = self.docs.execute({
                'operation': 'create_footer',
                'document_id': document_id,
                'text': 'Page {{page}} of {{pages}}'
            })
            
            self.assertTrue(footer_result['success'])
            print(f"✓ Created footer")
            
            return document_id
            
        except Exception as e:
            self.fail(f"Header and footer operations failed: {str(e)}")
            
    def test_style_operations(self):
        """Test style application."""
        try:
            # Use document from header/footer operations
            document_id = self.test_header_footer_operations()
            
            # Apply heading style
            style_result = self.docs.execute({
                'operation': 'apply_style',
                'document_id': document_id,
                'style': 'HEADING_1',
                'start_index': 1,
                'end_index': 20
            })
            
            self.assertTrue(style_result['success'])
            print(f"✓ Applied heading style")
            
            # Clean up - delete test document
            from src.modules.google_drive import GoogleDriveModule
            drive = GoogleDriveModule()
            delete_result = drive.execute({
                'operation': 'delete_file',
                'file_id': document_id
            })
            
            self.assertTrue(delete_result['success'])
            print(f"✓ Cleaned up test document")
            
        except Exception as e:
            self.fail(f"Style operations failed: {str(e)}")
            
    def test_parameter_validation(self):
        """Test parameter validation."""
        # Test invalid operation
        with self.assertRaises(ValueError):
            self.docs.execute({
                'operation': 'invalid_operation'
            })
            
        # Test missing required parameters
        with self.assertRaises(ValueError):
            self.docs.execute({
                'operation': 'create_document'
            })
            
        with self.assertRaises(ValueError):
            self.docs.execute({
                'operation': 'insert_text',
                'document_id': 'some_id'
            })
            
        print("✓ Parameter validation working correctly")
        
if __name__ == '__main__':
    unittest.main() 