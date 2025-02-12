#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from src.modules.file_transfer import FileTransferModule
from src.utils.logging import get_logger
import json

logger = get_logger(__name__)

def create_test_file(filename: str, content: str) -> str:
    """Create a test file with given content"""
    filepath = os.path.join('test_files', filename)
    os.makedirs('test_files', exist_ok=True)
    
    with open(filepath, 'w') as f:
        f.write(content)
    return filepath

def test_file_transfer():
    """Test file transfer functionality"""
    try:
        logger.info("=== Testing File Transfer Module ===")
        
        # Initialize module
        transfer_module = FileTransferModule()
        
        # Load environment variables
        load_dotenv()
        
        # Setup Google Drive
        logger.info("\nSetting up Google Drive...")
        google_creds = {
            'token': os.getenv('GOOGLE_TOKEN'),
            'refresh_token': os.getenv('GOOGLE_REFRESH_TOKEN'),
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'client_secret': os.getenv('GOOGLE_CLIENT_SECRET')
        }
        transfer_module.setup_google_drive(google_creds)
        logger.info("✓ Google Drive setup complete")
        
        # Setup Slack
        logger.info("\nSetting up Slack...")
        slack_token = os.getenv('SLACK_BOT_TOKEN')
        transfer_module.setup_slack(slack_token)
        logger.info("✓ Slack setup complete")
        
        # Setup Email
        logger.info("\nSetting up Email...")
        email_config = {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'username': os.getenv('EMAIL_USERNAME'),
            'password': os.getenv('EMAIL_PASSWORD'),
            'from_email': os.getenv('EMAIL_FROM')
        }
        transfer_module.setup_email(email_config)
        logger.info("✓ Email setup complete")
        
        # Create test files
        logger.info("\nCreating test files...")
        test_files = {
            'document.txt': 'This is a test document.',
            'data.json': json.dumps({'test': 'data'}),
            'image.jpg': 'Dummy image content'  # In real test, use actual image file
        }
        
        test_file_paths = {}
        for filename, content in test_files.items():
            test_file_paths[filename] = create_test_file(filename, content)
            logger.info(f"✓ Created {filename}")
        
        # Test Google Drive upload
        logger.info("\nTesting Google Drive upload...")
        drive_result = transfer_module.execute({
            'operation': 'upload_to_drive',
            'file_path': test_file_paths['document.txt']
        })
        
        if drive_result['success']:
            logger.info("✓ Successfully uploaded to Google Drive")
            file_id = drive_result['file_id']
            
            # Test Google Drive download
            logger.info("\nTesting Google Drive download...")
            download_result = transfer_module.execute({
                'operation': 'download_from_drive',
                'file_id': file_id
            })
            
            if download_result['success']:
                logger.info("✓ Successfully downloaded from Google Drive")
        
        # Test Slack upload
        logger.info("\nTesting Slack upload...")
        slack_result = transfer_module.execute({
            'operation': 'send_to_slack',
            'file_path': test_file_paths['data.json'],
            'channel': '#test-channel'  # Make sure this channel exists
        })
        
        if slack_result['success']:
            logger.info("✓ Successfully uploaded to Slack")
            slack_file_id = slack_result['file_id']
            
            # Test Slack download
            logger.info("\nTesting Slack download...")
            slack_download = transfer_module.execute({
                'operation': 'download_from_slack',
                'file_id': slack_file_id
            })
            
            if slack_download['success']:
                logger.info("✓ Successfully downloaded from Slack")
        
        # Test email sending
        logger.info("\nTesting email sending...")
        email_result = transfer_module.execute({
            'operation': 'send_email',
            'file_path': test_file_paths['document.txt'],
            'to_email': os.getenv('TEST_EMAIL_TO'),
            'subject': 'Test File Transfer',
            'body': 'This is a test email with attachment.'
        })
        
        if email_result['success']:
            logger.info("✓ Successfully sent email with attachment")
        
        # Test file organization
        logger.info("\nTesting file organization...")
        organize_result = transfer_module.execute({
            'operation': 'organize_files',
            'directory': 'test_files',
            'organize_by': 'type'
        })
        
        if organize_result['success']:
            logger.info("✓ Successfully organized files")
            for file_info in organize_result['organized_files']:
                logger.info(f"  • {file_info['file']} → {file_info['category']}")
        
        logger.info("\n✨ File transfer tests completed!")
        
    except Exception as e:
        logger.error(f"Test error: {str(e)}")
    finally:
        # Cleanup test files
        if os.path.exists('test_files'):
            import shutil
            shutil.rmtree('test_files')

if __name__ == "__main__":
    test_file_transfer() 