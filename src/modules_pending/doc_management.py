#!/usr/bin/env python3

from typing import Dict, Any, List, Optional
import os
import json
import yaml
import markdown
from datetime import datetime
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger

logger = get_logger(__name__)

class DocManagementModule(BaseModule):
    """Module for handling document management operations"""
    
    def __init__(self):
        self.docs_directory = "business_docs"
        self.supported_formats = {
            'doc': True,
            'docx': True,
            'pdf': True,
            'txt': True,
            'md': True
        }
        self.default_encoding = 'utf-8'
        self._ensure_directory_exists()
        
    def _ensure_directory_exists(self):
        """Create documents directory if it doesn't exist"""
        if not os.path.exists(self.docs_directory):
            os.makedirs(self.docs_directory)
            os.makedirs(os.path.join(self.docs_directory, 'versions'))
            
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute document management operations"""
        try:
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            operations = {
                'save': self._save_document,
                'load': self._load_document,
                'list': self._list_documents,
                'convert': self._convert_format,
                'create_version': self._create_version,
                'get_versions': self._get_versions
            }
            
            if operation not in operations:
                raise ValueError(f"Unknown operation: {operation}")
                
            result = await operations[operation](params)
            return result
            
        except Exception as e:
            logger.error(f"Document management error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _save_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Save a document to the file system"""
        try:
            content = params.get('content')
            filename = params.get('filename')
            format = params.get('format', 'txt')
            encoding = params.get('encoding', self.default_encoding)
            
            if not all([content, filename]):
                raise ValueError("Content and filename required")
                
            if format not in self.supported_formats:
                raise ValueError(f"Unsupported format: {format}")
                
            filepath = os.path.join(self.docs_directory, filename)
            with open(filepath, 'w', encoding=encoding) as f:
                f.write(content)
                
            return {
                'success': True,
                'filepath': filepath
            }
            
        except Exception as e:
            logger.error(f"Error saving document: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _load_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Load a document from the file system"""
        try:
            filename = params.get('filename')
            encoding = params.get('encoding', self.default_encoding)
            
            if not filename:
                raise ValueError("Filename required")
                
            filepath = os.path.join(self.docs_directory, filename)
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Document not found: {filename}")
                
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
                
            return {
                'success': True,
                'content': content,
                'filepath': filepath
            }
            
        except Exception as e:
            logger.error(f"Error loading document: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _list_documents(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available documents"""
        try:
            format_filter = params.get('format')
            
            documents = []
            for filename in os.listdir(self.docs_directory):
                if os.path.isfile(os.path.join(self.docs_directory, filename)):
                    ext = filename.split('.')[-1] if '.' in filename else None
                    if not format_filter or ext == format_filter:
                        documents.append(filename)
                        
            return {
                'success': True,
                'documents': documents
            }
            
        except Exception as e:
            logger.error(f"Error listing documents: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _convert_format(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert document to a different format"""
        try:
            filename = params.get('filename')
            target_format = params.get('target_format')
            
            if not all([filename, target_format]):
                raise ValueError("Filename and target format required")
                
            if target_format not in self.supported_formats:
                raise ValueError(f"Unsupported target format: {target_format}")
                
            # Load original document
            load_result = await self._load_document({'filename': filename})
            if not load_result['success']:
                return load_result
                
            content = load_result['content']
            
            # Convert content based on target format
            if target_format == 'md':
                converted_content = content  # No conversion needed for markdown
            elif target_format == 'txt':
                converted_content = markdown.markdown(content)  # Convert from markdown to text
            else:
                raise ValueError(f"Conversion to {target_format} not implemented")
                
            # Save converted document
            new_filename = f"{os.path.splitext(filename)[0]}.{target_format}"
            save_result = await self._save_document({
                'content': converted_content,
                'filename': new_filename,
                'format': target_format
            })
            
            return save_result
            
        except Exception as e:
            logger.error(f"Error converting document: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _create_version(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new version of a document"""
        try:
            filename = params.get('filename')
            version_note = params.get('version_note', '')
            
            if not filename:
                raise ValueError("Filename required")
                
            # Load current document
            load_result = await self._load_document({'filename': filename})
            if not load_result['success']:
                return load_result
                
            # Create version info
            version_info = {
                'timestamp': datetime.now().isoformat(),
                'note': version_note,
                'content': load_result['content']
            }
            
            # Save version
            version_dir = os.path.join(self.docs_directory, 'versions', filename)
            os.makedirs(version_dir, exist_ok=True)
            
            version_file = os.path.join(version_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(version_file, 'w', encoding=self.default_encoding) as f:
                json.dump(version_info, f, indent=2)
                
            return {
                'success': True,
                'version_file': version_file
            }
            
        except Exception as e:
            logger.error(f"Error creating version: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _get_versions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get version history of a document"""
        try:
            filename = params.get('filename')
            
            if not filename:
                raise ValueError("Filename required")
                
            version_dir = os.path.join(self.docs_directory, 'versions', filename)
            if not os.path.exists(version_dir):
                return {
                    'success': True,
                    'versions': []
                }
                
            versions = []
            for version_file in sorted(os.listdir(version_dir)):
                with open(os.path.join(version_dir, version_file), 'r', encoding=self.default_encoding) as f:
                    version_info = json.load(f)
                    versions.append(version_info)
                    
            return {
                'success': True,
                'versions': versions
            }
            
        except Exception as e:
            logger.error(f"Error getting versions: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        if operation == 'save_document':
            return bool(params.get('name')) and bool(params.get('content'))
        elif operation in ['load_document', 'create_version', 'get_versions']:
            return bool(params.get('name'))
        elif operation == 'convert_format':
            return bool(params.get('name')) and bool(params.get('to_format'))
        elif operation == 'list_documents':
            return True
            
        return False

    @property
    def capabilities(self) -> List[str]:
        return [
            'document_management',
            'format_conversion',
            'version_control',
            'document_storage'
        ]

    async def create_document(self, title: str, content: str, 
                            format: str = 'txt', **kwargs) -> Dict[str, Any]:
        """Create a new document"""
        try:
            logger.info(f"Creating document: {title} in format {format}")
            
            if not self.supported_formats.get(format.lower()):
                raise ValueError(f"Unsupported document format: {format}")
            
            # Implementation would handle actual document creation
            # This is a placeholder for the actual implementation
            doc_info = {
                "title": title,
                "format": format,
                "size": len(content),
                "created": True
            }
            
            return {
                "status": "success",
                "document": doc_info
            }
            
        except Exception as e:
            logger.error(f"Error creating document: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def read_document(self, path: str, 
                          encoding: Optional[str] = None) -> Dict[str, Any]:
        """Read a document's contents"""
        try:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Document not found: {path}")
            
            encoding = encoding or self.default_encoding
            format = path.split('.')[-1].lower()
            
            if not self.supported_formats.get(format):
                raise ValueError(f"Unsupported document format: {format}")
            
            # Implementation would handle actual document reading
            # This is a placeholder for the actual implementation
            return {
                "status": "success",
                "content": "Document content would go here",
                "format": format,
                "encoding": encoding
            }
            
        except Exception as e:
            logger.error(f"Error reading document: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def update_document(self, path: str, content: str, 
                            **kwargs) -> Dict[str, Any]:
        """Update an existing document"""
        try:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Document not found: {path}")
            
            format = path.split('.')[-1].lower()
            
            if not self.supported_formats.get(format):
                raise ValueError(f"Unsupported document format: {format}")
            
            # Implementation would handle actual document updating
            # This is a placeholder for the actual implementation
            return {
                "status": "success",
                "updated": True,
                "size": len(content)
            }
            
        except Exception as e:
            logger.error(f"Error updating document: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def delete_document(self, path: str) -> Dict[str, Any]:
        """Delete a document"""
        try:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Document not found: {path}")
            
            # Implementation would handle actual document deletion
            # This is a placeholder for the actual implementation
            return {
                "status": "success",
                "deleted": True
            }
            
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported document formats"""
        return [fmt for fmt, supported in self.supported_formats.items() 
                if supported] 