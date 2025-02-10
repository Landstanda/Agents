#!/usr/bin/env python3

from src.modules.slack import SlackModule
from src.modules.google_drive import GoogleDriveModule
from src.utils.logging import get_logger
import os
import tempfile

logger = get_logger(__name__)

class SlackToDriveChain:
    """Chain for handling file transfers from Slack to Google Drive."""
    
    def __init__(self):
        self.slack = SlackModule()
        self.drive = GoogleDriveModule()
        
    def process_message(self, message_data):
        """Process a Slack message containing a file and upload to Drive."""
        try:
            # 1. Extract file from Slack message
            file_result = self.slack.execute({
                'operation': 'download_file',
                'file_id': message_data['file']['id'],
                'channel_id': message_data['channel']
            })
            
            if not file_result['success']:
                raise Exception("Failed to download file from Slack")
                
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file_result['content'])
                temp_path = temp_file.name
                
            # 2. Parse destination folder from message
            folder_name = self._parse_folder_name(message_data['text'])
            
            # 3. Find or create folder in Drive
            folder_result = self.drive.execute({
                'operation': 'search_files',
                'query': folder_name,
                'file_type': 'application/vnd.google-apps.folder'
            })
            
            if folder_result['success'] and folder_result['files']:
                folder_id = folder_result['files'][0]['id']
            else:
                # Create folder if it doesn't exist
                create_result = self.drive.execute({
                    'operation': 'create_folder',
                    'folder_name': folder_name
                })
                if not create_result['success']:
                    raise Exception(f"Failed to create folder: {folder_name}")
                folder_id = create_result['folder_id']
                
            # 4. Upload file to Drive
            upload_result = self.drive.execute({
                'operation': 'upload_file',
                'file_path': temp_path,
                'parent_folder': folder_id
            })
            
            # Clean up temporary file
            os.unlink(temp_path)
            
            if not upload_result['success']:
                raise Exception("Failed to upload file to Drive")
                
            # 5. Update sharing settings if needed
            share_result = self.drive.execute({
                'operation': 'update_sharing',
                'file_id': upload_result['file_id'],
                'role': 'reader'
            })
            
            # 6. Send confirmation message back to Slack
            self.slack.execute({
                'operation': 'post_message',
                'channel': message_data['channel'],
                'text': f"File uploaded successfully to Google Drive folder '{folder_name}'\n"
                       f"View it here: {upload_result['web_link']}"
            })
            
            return {
                'success': True,
                'file_id': upload_result['file_id'],
                'folder_id': folder_id,
                'web_link': upload_result['web_link']
            }
            
        except Exception as e:
            logger.error(f"Chain execution failed: {str(e)}")
            # Notify failure in Slack
            self.slack.execute({
                'operation': 'post_message',
                'channel': message_data['channel'],
                'text': f"Failed to process file: {str(e)}"
            })
            return {'success': False, 'error': str(e)}
            
    def _parse_folder_name(self, message_text):
        """Extract folder name from message text.
        Expected format: "upload to folder: <folder_name>"
        """
        try:
            if "upload to folder:" in message_text.lower():
                return message_text.lower().split("upload to folder:")[1].strip()
            return "Uploads"  # Default folder
        except Exception:
            return "Uploads"  # Default folder

if __name__ == '__main__':
    # Example usage
    chain = SlackToDriveChain()
    
    # Sample message data (in practice, this would come from Slack events)
    message_data = {
        'channel': 'C1234567890',
        'text': 'upload to folder: Project Documents',
        'file': {
            'id': 'F1234567890',
            'name': 'document.pdf'
        }
    }
    
    result = chain.process_message(message_data)
    print(f"Chain execution result: {result}") 