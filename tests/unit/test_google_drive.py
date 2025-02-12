#!/usr/bin/env python3

import unittest
import os
import logging
from src.modules.google_drive import GoogleDriveModule

# Disable unnecessary logging during tests
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

class TestGoogleDriveModule(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        self.drive = GoogleDriveModule()
        self.test_folder_name = "test_folder_aphrodite"
        self.test_file_name = "test_file.txt"
        self.test_file_content = "This is a test file created by Aphrodite Agent."
        
        # Create a test file
        with open(self.test_file_name, 'w') as f:
            f.write(self.test_file_content)
            
    def tearDown(self):
        """Clean up test environment."""
        # Remove test file
        if os.path.exists(self.test_file_name):
            os.remove(self.test_file_name)
            
    def test_service_initialization(self):
        """Test Google Drive service initialization."""
        try:
            self.drive._initialize_service()
            self.assertIsNotNone(self.drive.service)
            print("✓ Drive service initialized successfully")
        except Exception as e:
            self.fail(f"Failed to initialize Drive service: {str(e)}")
            
    def test_folder_operations(self):
        """Test folder creation and management."""
        try:
            # Create test folder
            result = self.drive.execute({
                'operation': 'create_folder',
                'folder_name': self.test_folder_name
            })
            
            self.assertTrue(result['success'])
            self.assertIn('folder_id', result)
            folder_id = result['folder_id']
            print(f"✓ Created test folder: {result['name']}")
            
            # Store folder_id for cleanup
            self.folder_id = folder_id
            
            # List files in the folder
            list_result = self.drive.execute({
                'operation': 'list_files',
                'folder_id': folder_id
            })
            
            self.assertTrue(list_result['success'])
            print(f"✓ Listed folder contents")
            
            return folder_id
            
        except Exception as e:
            self.fail(f"Folder operations failed: {str(e)}")
            
    def test_file_operations(self):
        """Test file upload, download, and management."""
        try:
            # First create a folder
            folder_id = self.test_folder_operations()
            
            # Upload test file
            upload_result = self.drive.execute({
                'operation': 'upload_file',
                'file_path': self.test_file_name,
                'parent_folder': folder_id
            })
            
            self.assertTrue(upload_result['success'])
            self.assertIn('file_id', upload_result)
            file_id = upload_result['file_id']
            print(f"✓ Uploaded test file: {upload_result['name']}")
            
            # Get file metadata
            metadata_result = self.drive.execute({
                'operation': 'get_file_metadata',
                'file_id': file_id
            })
            
            self.assertTrue(metadata_result['success'])
            print(f"✓ Retrieved file metadata")
            
            # Download the file
            download_result = self.drive.execute({
                'operation': 'download_file',
                'file_id': file_id,
                'output_path': 'downloaded_test.txt'
            })
            
            self.assertTrue(download_result['success'])
            print(f"✓ Downloaded file")
            
            # Verify content
            with open('downloaded_test.txt', 'r') as f:
                content = f.read()
                self.assertEqual(content, self.test_file_content)
            
            # Clean up downloaded file
            os.remove('downloaded_test.txt')
            
            # Update sharing settings
            share_result = self.drive.execute({
                'operation': 'update_sharing',
                'file_id': file_id,
                'role': 'reader'
            })
            
            self.assertTrue(share_result['success'])
            print(f"✓ Updated sharing settings")
            
            # Delete test file
            delete_result = self.drive.execute({
                'operation': 'delete_file',
                'file_id': file_id
            })
            
            self.assertTrue(delete_result['success'])
            print(f"✓ Deleted test file")
            
            # Delete test folder
            delete_folder_result = self.drive.execute({
                'operation': 'delete_file',
                'file_id': folder_id
            })
            
            self.assertTrue(delete_folder_result['success'])
            print(f"✓ Deleted test folder")
            
        except Exception as e:
            self.fail(f"File operations failed: {str(e)}")
            
    def test_search_operations(self):
        """Test file search functionality."""
        try:
            # Create a unique file to search for
            unique_name = f"unique_test_file_{os.urandom(4).hex()}.txt"
            with open(unique_name, 'w') as f:
                f.write("Unique test content")
                
            # Upload the unique file
            upload_result = self.drive.execute({
                'operation': 'upload_file',
                'file_path': unique_name
            })
            
            self.assertTrue(upload_result['success'])
            file_id = upload_result['file_id']
            
            # Search for the file
            search_result = self.drive.execute({
                'operation': 'search_files',
                'query': unique_name
            })
            
            self.assertTrue(search_result['success'])
            self.assertTrue(any(f['id'] == file_id for f in search_result['files']))
            print(f"✓ Successfully searched for file")
            
            # Clean up
            self.drive.execute({
                'operation': 'delete_file',
                'file_id': file_id
            })
            os.remove(unique_name)
            
        except Exception as e:
            self.fail(f"Search operations failed: {str(e)}")
            
    def test_parameter_validation(self):
        """Test parameter validation."""
        # Test invalid operation
        with self.assertRaises(ValueError):
            self.drive.execute({
                'operation': 'invalid_operation'
            })
            
        # Test missing required parameters
        with self.assertRaises(ValueError):
            self.drive.execute({
                'operation': 'upload_file'
            })
            
        with self.assertRaises(ValueError):
            self.drive.execute({
                'operation': 'download_file'
            })
            
        print("✓ Parameter validation working correctly")
        
if __name__ == '__main__':
    unittest.main() 