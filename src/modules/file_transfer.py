#!/usr/bin/env python3

from typing import Dict, Any, List, Optional
import os
import shutil
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from slack_sdk import WebClient
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from .doc_management import DocumentManagementModule

logger = get_logger(__name__)

class FileTransferModule(BaseModule):
    """Module for transferring files between local storage and cloud services"""
    
    def __init__(self):
        self.doc_manager = DocumentManagementModule()
        self.transfer_directory = "file_transfers"
        self._ensure_directory_exists()
        
        # Initialize cloud service clients
        self.google_drive_service = None
        self.slack_client = None
        self.email_config = None
        
    def _ensure_directory_exists(self):
        """Create transfer directory if it doesn't exist"""
        if not os.path.exists(self.transfer_directory):
            os.makedirs(self.transfer_directory)
            
    def setup_google_drive(self, credentials_dict: Dict[str, Any]):
        """Setup Google Drive client"""
        credentials = Credentials.from_authorized_user_info(credentials_dict)
        self.google_drive_service = build('drive', 'v3', credentials=credentials)
        
    def setup_slack(self, token: str):
        """Setup Slack client"""
        self.slack_client = WebClient(token=token)
        
    def setup_email(self, config: Dict[str, Any]):
        """Setup email configuration"""
        self.email_config = config
        
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file transfer operations"""
        try:
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            operations = {
                'upload_to_drive': self._upload_to_drive,
                'download_from_drive': self._download_from_drive,
                'send_to_slack': self._send_to_slack,
                'download_from_slack': self._download_from_slack,
                'send_email': self._send_email,
                'organize_files': self._organize_files
            }
            
            if operation not in operations:
                raise ValueError(f"Unknown operation: {operation}")
                
            return operations[operation](params)
            
        except Exception as e:
            logger.error(f"File transfer error: {str(e)}")
            raise
            
    def _upload_to_drive(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Upload file to Google Drive"""
        if not self.google_drive_service:
            raise ValueError("Google Drive not configured")
            
        file_path = params.get('file_path')
        folder_id = params.get('folder_id')
        
        if not file_path or not os.path.exists(file_path):
            raise ValueError("Invalid file path")
            
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id] if folder_id else None
        }
        
        media = MediaFileUpload(file_path, resumable=True)
        file = self.google_drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        return {
            'success': True,
            'file_id': file.get('id'),
            'service': 'google_drive'
        }
        
    def _download_from_drive(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Download file from Google Drive"""
        if not self.google_drive_service:
            raise ValueError("Google Drive not configured")
            
        file_id = params.get('file_id')
        if not file_id:
            raise ValueError("File ID required")
            
        file = self.google_drive_service.files().get(fileId=file_id).execute()
        request = self.google_drive_service.files().get_media(fileId=file_id)
        
        local_path = os.path.join(self.transfer_directory, file['name'])
        with open(local_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
                
        return {
            'success': True,
            'local_path': local_path,
            'filename': file['name']
        }
        
    def _send_to_slack(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send file to Slack channel"""
        if not self.slack_client:
            raise ValueError("Slack not configured")
            
        file_path = params.get('file_path')
        channel = params.get('channel')
        
        if not file_path or not channel:
            raise ValueError("File path and channel required")
            
        with open(file_path, 'rb') as f:
            response = self.slack_client.files_upload(
                channels=channel,
                file=f,
                filename=os.path.basename(file_path)
            )
            
        return {
            'success': True,
            'file_id': response['file']['id'],
            'service': 'slack'
        }
        
    def _download_from_slack(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Download file from Slack"""
        if not self.slack_client:
            raise ValueError("Slack not configured")
            
        file_id = params.get('file_id')
        if not file_id:
            raise ValueError("File ID required")
            
        response = self.slack_client.files_info(file=file_id)
        download_url = response['file']['url_private_download']
        
        local_path = os.path.join(self.transfer_directory, response['file']['name'])
        self.slack_client.files_download(url=download_url, filename=local_path)
        
        return {
            'success': True,
            'local_path': local_path,
            'filename': response['file']['name']
        }
        
    def _send_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send file via email"""
        if not self.email_config:
            raise ValueError("Email not configured")
            
        file_path = params.get('file_path')
        to_email = params.get('to_email')
        subject = params.get('subject', 'File Transfer')
        body = params.get('body', 'Please find the attached file.')
        
        if not file_path or not to_email:
            raise ValueError("File path and recipient email required")
            
        msg = MIMEMultipart()
        msg['From'] = self.email_config['from_email']
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        with open(file_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename={os.path.basename(file_path)}'
        )
        msg.attach(part)
        
        with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
            server.starttls()
            server.login(self.email_config['username'], self.email_config['password'])
            server.send_message(msg)
            
        return {
            'success': True,
            'to_email': to_email,
            'service': 'email'
        }
        
    def _organize_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Organize files by type, date, or custom categories"""
        directory = params.get('directory', self.transfer_directory)
        organize_by = params.get('organize_by', 'type')  # type, date, or category
        
        if not os.path.exists(directory):
            raise ValueError(f"Directory not found: {directory}")
            
        organized = []
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                if organize_by == 'type':
                    ext = os.path.splitext(filename)[1][1:] or 'no_extension'
                    target_dir = os.path.join(directory, ext)
                elif organize_by == 'date':
                    timestamp = os.path.getmtime(file_path)
                    date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                    target_dir = os.path.join(directory, date_str)
                else:  # category (based on file patterns or metadata)
                    category = self._determine_category(filename)
                    target_dir = os.path.join(directory, category)
                    
                os.makedirs(target_dir, exist_ok=True)
                shutil.move(file_path, os.path.join(target_dir, filename))
                organized.append({
                    'file': filename,
                    'category': os.path.basename(target_dir)
                })
                
        return {
            'success': True,
            'organized_files': organized,
            'organize_by': organize_by
        }
        
    def _determine_category(self, filename: str) -> str:
        """Determine category based on filename patterns"""
        filename = filename.lower()
        if any(ext in filename for ext in ['.doc', '.docx', '.pdf', '.txt']):
            return 'documents'
        elif any(ext in filename for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            return 'images'
        elif any(ext in filename for ext in ['.mp3', '.wav', '.ogg']):
            return 'audio'
        elif any(ext in filename for ext in ['.mp4', '.avi', '.mov']):
            return 'video'
        else:
            return 'misc'
            
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        required_params = {
            'upload_to_drive': ['file_path'],
            'download_from_drive': ['file_id'],
            'send_to_slack': ['file_path', 'channel'],
            'download_from_slack': ['file_id'],
            'send_email': ['file_path', 'to_email'],
            'organize_files': ['directory']
        }
        
        if operation not in required_params:
            return False
            
        return all(params.get(param) for param in required_params[operation]) 