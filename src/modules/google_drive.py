#!/usr/bin/env python3

from typing import Dict, Any, List, Optional
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io
import os
import mimetypes
import logging

logger = get_logger(__name__)

class GoogleDriveModule(BaseModule):
    """Module for handling Google Drive operations"""
    
    def __init__(self):
        self.service = None
        self.folder_mime = 'application/vnd.google-apps.folder'
        
    def _initialize_service(self):
        """Initialize Google Drive API service"""
        if not self.service:
            from .google_auth import GoogleAuthModule
            auth_module = GoogleAuthModule()
            auth_result = auth_module.execute({})
            credentials = auth_result['credentials']
            self.service = build('drive', 'v3', credentials=credentials)
            
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Google Drive operations"""
        try:
            self._initialize_service()
            
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            operations = {
                'upload_file': self._upload_file,
                'download_file': self._download_file,
                'create_folder': self._create_folder,
                'list_files': self._list_files,
                'search_files': self._search_files,
                'update_sharing': self._update_sharing,
                'get_file_metadata': self._get_file_metadata,
                'delete_file': self._delete_file
            }
            
            if operation not in operations:
                raise ValueError(f"Unknown operation: {operation}")
                
            return operations[operation](params)
            
        except Exception as e:
            logger.error(f"Drive operation error: {str(e)}")
            raise
            
    def _upload_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a file to Google Drive"""
        file_path = params.get('file_path')
        parent_folder = params.get('parent_folder', 'root')
        
        if not file_path or not os.path.exists(file_path):
            raise ValueError("Valid file path required")
            
        try:
            file_metadata = {
                'name': os.path.basename(file_path),
                'parents': [parent_folder]
            }
            
            mime_type = mimetypes.guess_type(file_path)[0]
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, mimeType, webViewLink'
            ).execute()
            
            return {
                'success': True,
                'file_id': file['id'],
                'name': file['name'],
                'mime_type': file['mimeType'],
                'web_link': file.get('webViewLink')
            }
            
        except Exception as e:
            logger.error(f"Failed to upload file: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _download_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Download a file from Google Drive"""
        file_id = params.get('file_id')
        output_path = params.get('output_path')
        
        if not file_id:
            raise ValueError("File ID required")
            
        try:
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
            fh.seek(0)
            
            if output_path:
                with open(output_path, 'wb') as f:
                    f.write(fh.read())
                    return {'success': True, 'path': output_path}
            else:
                return {'success': True, 'content': fh.read()}
                
        except Exception as e:
            logger.error(f"Failed to download file: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _create_folder(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a folder in Google Drive"""
        folder_name = params.get('folder_name')
        parent_folder = params.get('parent_folder', 'root')
        
        if not folder_name:
            raise ValueError("Folder name required")
            
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': self.folder_mime,
                'parents': [parent_folder]
            }
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id, name, webViewLink'
            ).execute()
            
            return {
                'success': True,
                'folder_id': folder['id'],
                'name': folder['name'],
                'web_link': folder.get('webViewLink')
            }
            
        except Exception as e:
            logger.error(f"Failed to create folder: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _list_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List files in a folder"""
        folder_id = params.get('folder_id', 'root')
        page_size = params.get('page_size', 100)
        
        try:
            query = f"'{folder_id}' in parents"
            response = self.service.files().list(
                q=query,
                pageSize=page_size,
                fields="files(id, name, mimeType, webViewLink)"
            ).execute()
            
            return {
                'success': True,
                'files': response.get('files', [])
            }
            
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _search_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search for files in Google Drive"""
        query = params.get('query')
        file_type = params.get('file_type')
        
        if not query:
            raise ValueError("Search query required")
            
        try:
            search_query = f"name contains '{query}'"
            if file_type:
                search_query += f" and mimeType='{file_type}'"
                
            response = self.service.files().list(
                q=search_query,
                pageSize=50,
                fields="files(id, name, mimeType, webViewLink)"
            ).execute()
            
            return {
                'success': True,
                'files': response.get('files', [])
            }
            
        except Exception as e:
            logger.error(f"Failed to search files: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _update_sharing(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update sharing settings for a file"""
        file_id = params.get('file_id')
        role = params.get('role', 'reader')  # 'reader', 'writer', 'commenter'
        email = params.get('email')
        
        if not file_id:
            raise ValueError("File ID required")
            
        try:
            if email:
                # Share with specific user
                permission = {
                    'type': 'user',
                    'role': role,
                    'emailAddress': email
                }
            else:
                # Make file accessible via link
                permission = {
                    'type': 'anyone',
                    'role': role
                }
                
            result = self.service.permissions().create(
                fileId=file_id,
                body=permission,
                fields='id'
            ).execute()
            
            # Get updated sharing link
            file = self.service.files().get(
                fileId=file_id,
                fields='webViewLink'
            ).execute()
            
            return {
                'success': True,
                'permission_id': result['id'],
                'web_link': file.get('webViewLink')
            }
            
        except Exception as e:
            logger.error(f"Failed to update sharing: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _get_file_metadata(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get metadata for a file"""
        file_id = params.get('file_id')
        
        if not file_id:
            raise ValueError("File ID required")
            
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, webViewLink, createdTime, modifiedTime, size, parents'
            ).execute()
            
            return {
                'success': True,
                'metadata': file
            }
            
        except Exception as e:
            logger.error(f"Failed to get file metadata: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _delete_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a file from Google Drive"""
        file_id = params.get('file_id')
        
        if not file_id:
            raise ValueError("File ID required")
            
        try:
            self.service.files().delete(fileId=file_id).execute()
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        required_params = {
            'upload_file': ['file_path'],
            'download_file': ['file_id'],
            'create_folder': ['folder_name'],
            'search_files': ['query'],
            'update_sharing': ['file_id'],
            'get_file_metadata': ['file_id'],
            'delete_file': ['file_id']
        }
        
        if operation in required_params:
            return all(params.get(param) for param in required_params[operation])
            
        return True
        
    @property
    def capabilities(self) -> List[str]:
        return [
            'file_upload',
            'file_download',
            'folder_management',
            'file_sharing',
            'file_search',
            'metadata_management',
            'google_drive_integration'
        ] 