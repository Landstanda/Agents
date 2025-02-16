from typing import Dict, Any, List, Optional
import base64
import os
import json
from src.core.module_interface import BaseModule
import logging
from googleapiclient.discovery import build
from src.utils.credential_manager import CredentialManager
from .gpt_handler import GPTHandler

logger = logging.getLogger(__name__)

class EmailManager(BaseModule):
    """Module for managing emails and attachments using Gmail API"""
    
    def __init__(self):
        super().__init__()
        self.service = None
        self.cred_manager = CredentialManager()
        self.gpt_handler = GPTHandler()
        
        # Load classification schema
        schema_path = os.path.join('src', 'services', 'email_classifications.json')
        with open(schema_path, 'r') as f:
            self.classification_schema = json.load(f)
            
    async def _initialize_service(self):
        """Initialize Gmail API service"""
        if not self.service:
            credentials = await self.cred_manager.get_credentials('gmail')
            self.service = build('gmail', 'v1', credentials=credentials)
            
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email management operations"""
        try:
            await self._initialize_service()
            
            action = params.get('action')
            if not action:
                raise ValueError("No action specified")
                
            actions = {
                'modify_labels': self._modify_labels,
                'mark_as_read': self._mark_as_read,
                'mark_as_unread': self._mark_as_unread,
                'flag_email': self._flag_email,
                'download_attachment': self._download_attachment,
                'create_folder': self._create_folder,
                'classify_email': self._classify_email,
                'process_classification': self._process_classification
            }
            
            if action not in actions:
                raise ValueError(f"Unknown action: {action}")
                
            if action == 'classify_email':
                return await actions[action](params.get('email_id'))
            else:
                return await actions[action](params)
                
        except Exception as e:
            logger.error(f"Email manager error: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _modify_labels(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add or remove labels from an email"""
        try:
            email_id = params.get('email_id')
            add_labels = params.get('add_labels', [])
            remove_labels = params.get('remove_labels', [])
            
            if not email_id:
                raise ValueError("Email ID required")
                
            # Get or create label IDs for labels to add
            add_label_ids = []
            for label in add_labels:
                label_id = await self._get_or_create_label(label)
                add_label_ids.append(label_id)
                
            # Get label IDs for labels to remove
            remove_label_ids = []
            for label in remove_labels:
                try:
                    label_id = await self._get_or_create_label(label)
                    remove_label_ids.append(label_id)
                except Exception:
                    # Skip if label doesn't exist
                    continue
                    
            # Modify the email's labels
            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={
                    'addLabelIds': add_label_ids,
                    'removeLabelIds': remove_label_ids
                }
            ).execute()
            
            return {
                'status': 'success',
                'action_completed': True,
                'email_id': email_id,
                'added_labels': add_labels,
                'removed_labels': remove_labels
            }
            
        except Exception as e:
            logger.error(f"Failed to modify labels: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _mark_as_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mark email as read"""
        try:
            email_id = params.get('email_id')
            
            if not email_id:
                raise ValueError("Email ID required")
                
            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            
            return {
                'status': 'success',
                'action_completed': True,
                'email_id': email_id,
                'new_status': 'read'
            }
            
        except Exception as e:
            logger.error(f"Failed to mark email as read: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _mark_as_unread(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mark email as unread"""
        try:
            email_id = params.get('email_id')
            
            if not email_id:
                raise ValueError("Email ID required")
                
            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'addLabelIds': ['UNREAD']}
            ).execute()
            
            return {
                'status': 'success',
                'action_completed': True,
                'email_id': email_id,
                'new_status': 'unread'
            }
            
        except Exception as e:
            logger.error(f"Failed to mark email as unread: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _flag_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Flag/star an email"""
        try:
            email_id = params.get('email_id')
            flag_type = params.get('flag_type', 'star')  # star, important, etc.
            
            if not email_id:
                raise ValueError("Email ID required")
                
            flag_labels = {
                'star': 'STARRED',
                'important': 'IMPORTANT'
            }
            
            label = flag_labels.get(flag_type)
            if not label:
                raise ValueError(f"Unknown flag type: {flag_type}")
                
            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'addLabelIds': [label]}
            ).execute()
            
            return {
                'status': 'success',
                'action_completed': True,
                'email_id': email_id,
                'flag_type': flag_type
            }
            
        except Exception as e:
            logger.error(f"Failed to flag email: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _download_attachment(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Download an email attachment"""
        try:
            email_id = params.get('email_id')
            attachment_id = params.get('attachment_id')
            save_path = params.get('save_path', 'downloads')
            
            if not all([email_id, attachment_id]):
                raise ValueError("Email ID and attachment ID required")
                
            # Create save directory if it doesn't exist
            os.makedirs(save_path, exist_ok=True)
            
            # Get the attachment
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=email_id,
                id=attachment_id
            ).execute()
            
            file_data = base64.urlsafe_b64decode(attachment['data'])
            
            # Save the file
            file_path = os.path.join(save_path, params.get('filename', 'attachment'))
            with open(file_path, 'wb') as f:
                f.write(file_data)
                
            return {
                'status': 'success',
                'action_completed': True,
                'email_id': email_id,
                'attachment_id': attachment_id,
                'save_location': file_path
            }
            
        except Exception as e:
            logger.error(f"Failed to download attachment: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _create_folder(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new email folder/label"""
        try:
            folder_name = params.get('folder_name')
            
            if not folder_name:
                raise ValueError("Folder name required")
                
            label = self.service.users().labels().create(
                userId='me',
                body={'name': folder_name}
            ).execute()
            
            return {
                'status': 'success',
                'action_completed': True,
                'folder_name': folder_name,
                'label_id': label['id']
            }
            
        except Exception as e:
            logger.error(f"Failed to create folder: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _get_or_create_label(self, label_name: str) -> str:
        """Get a label ID or create it if it doesn't exist"""
        try:
            # List all labels
            labels = self.service.users().labels().list(userId='me').execute()
            
            # Look for existing label
            for label in labels.get('labels', []):
                if label['name'].lower() == label_name.lower():
                    return label['id']
                    
            # Create new label if not found
            new_label = self.service.users().labels().create(
                userId='me',
                body={'name': label_name}
            ).execute()
            
            return new_label['id']
            
        except Exception as e:
            logger.error(f"Failed to get/create label: {str(e)}")
            raise

    async def _classify_email(self, email_id: str) -> Dict[str, Any]:
        """Classify an email using GPT"""
        try:
            # Get email content
            email_data = await self._get_email_content(email_id)
            if not email_data:
                raise ValueError("Failed to retrieve email content")
            
            headers = email_data['payload']['headers']
            body = self._extract_email_body(email_data)
            
            # Prepare email data for classification
            email_content = {
                "from": next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown'),
                "subject": next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject'),
                "date": next((h['value'] for h in headers if h['name'].lower() == 'date'), 'Unknown'),
                "content": body
            }
            
            # Log raw email content for debugging
            logger.info("=== Raw Email Content ===")
            logger.info(json.dumps(email_content, indent=2))
            logger.info("========================")
            
            # Prepare classification prompt
            system_message = """You are an email classification assistant. Your task is to analyze emails and categorize them based on their content and urgency. You must provide accurate classifications that follow the specified format exactly."""
            
            prompt = f"""Analyze and classify the following email:

From: {email_content['from']}
Subject: {email_content['subject']}
Date: {email_content['date']}
Content:
{email_content['content']}

Available Categories:
{json.dumps(self.classification_schema['categories'], indent=2)}

Classify this email by providing a JSON object with these fields:
- category: One of [{', '.join(self.classification_schema['categories'].keys())}]
- confidence: Number between 0.0 and 1.0 indicating classification confidence
- summary: Brief description of the email content

Base your classification on:
1. Email content and subject
2. Sender information
3. Urgency indicators
4. Business impact
5. Required actions"""

            # Define validation schema
            validation_schema = {
                'required_fields': ['category', 'confidence', 'summary'],
                'field_types': {
                    'category': 'str',
                    'confidence': 'number',
                    'summary': 'str'
                },
                'value_ranges': {
                    'confidence': (0.0, 1.0)
                }
            }
            
            # Get classification from GPT
            classification_result = await self.gpt_handler.execute({
                'prompt': prompt,
                'system_message': system_message,
                'response_format': 'json',
                'validation_schema': validation_schema,
                'temperature': 0.1  # Low temperature for consistent results
            })
            
            if classification_result['status'] != 'success':
                raise ValueError(f"Failed to classify email: {classification_result.get('error')}")
            
            # Parse the classification
            classification = json.loads(classification_result['content'])
            
            # Validate category
            if classification['category'] not in self.classification_schema['categories']:
                raise ValueError(f"Invalid category: {classification['category']}")
            
            return {
                'status': 'success',
                'classification': classification
            }
            
        except Exception as e:
            logger.error(f"Failed to classify email: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    async def _process_classification(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process the classification results and take appropriate actions"""
        try:
            classification = params.get('classification')
            if not classification:
                raise ValueError("Classification required")
                
            category = self.classification_schema['categories'].get(classification['category'])
            
            if not category:
                raise ValueError(f"Unknown category: {classification['category']}")
                
            # Add the main category label
            result = await self._modify_labels({
                'email_id': classification['email_id'],
                'add_labels': [category['folder']],
                'remove_labels': []
            })
            
            # Process other actions
            action_results = []
            for action in category['actions']:
                if action == 'flag_as_important':
                    # Use Gmail's built-in IMPORTANT label
                    await self._flag_email({
                        'email_id': classification['email_id'],
                        'flag_type': 'important'
                    })
                    action_results.append({
                        'action': 'flag_as_important',
                        'status': 'completed'
                    })
                elif action.startswith('auto_respond'):
                    if classification['auto_response_possible']:
                        action_results.append({
                            'action': 'auto_respond',
                            'status': 'pending'
                        })
                else:
                    action_results.append({
                        'action': action,
                        'status': 'processed'
                    })
            
            return {
                'status': 'success',
                'label_added': category['folder'],
                'category': category['name'],
                'actions_performed': action_results
            }
            
        except Exception as e:
            logger.error(f"Failed to process classification: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def _get_email_body(self, payload: Dict[str, Any]) -> str:
        """Extract email body from payload"""
        if payload.get('body', {}).get('data'):
            return base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode('utf-8')
            
        if payload.get('parts'):
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    return base64.urlsafe_b64decode(
                        part['body']['data']
                    ).decode('utf-8')
                    
        return ''

    async def _get_email_content(self, email_id: str) -> Dict[str, Any]:
        """Get email content from Gmail API"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to get email content: {str(e)}")
            return None
            
    def _extract_email_body(self, message: Dict[str, Any]) -> str:
        """Extract email body from message payload"""
        if message.get('payload', {}).get('body', {}).get('data'):
            return base64.urlsafe_b64decode(
                message['payload']['body']['data']
            ).decode('utf-8')
            
        if message.get('payload', {}).get('parts'):
            for part in message['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    return base64.urlsafe_b64decode(
                        part['body']['data']
                    ).decode('utf-8')
                    
        return ''

    @property
    def capabilities(self) -> List[str]:
        return [
            'email_organization',
            'attachment_handling',
            'folder_management',
            'email_status_management'
        ] 