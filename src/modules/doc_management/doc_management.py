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
        self.documents: Dict[str, Dict[str, Any]] = {}
        
    def _ensure_directory_exists(self):
        """Create documents directory if it doesn't exist"""
        if not os.path.exists(self.docs_directory):
            os.makedirs(self.docs_directory)
            os.makedirs(os.path.join(self.docs_directory, 'versions'))
            
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute document management operations"""
        try:
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            if operation == 'save_document':
                return self._save_document(params)
            elif operation == 'load_document':
                return self._load_document(params)
            elif operation == 'list_documents':
                return self._list_documents(params)
            elif operation == 'convert_format':
                return self._convert_format(params)
            elif operation == 'create_version':
                return self._create_version(params)
            elif operation == 'get_versions':
                return self._get_versions(params)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except Exception as e:
            logger.error(f"Document management error: {str(e)}")
            raise
            
    def _save_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Save a document in specified format"""
        name = params.get('name')
        content = params.get('content')
        format = params.get('format', 'txt').lower()
        
        if not name or not content:
            raise ValueError("Document name and content required")
            
        if not self.supported_formats.get(format):
            raise ValueError(f"Unsupported format: {format}")
            
        filename = f"{name}.{format}"
        filepath = os.path.join(self.docs_directory, filename)
        
        try:
            with open(filepath, 'w') as f:
                if format == 'json':
                    if isinstance(content, str):
                        content = json.loads(content)
                    json.dump(content, f, indent=2)
                elif format == 'yaml':
                    if isinstance(content, str):
                        content = yaml.safe_load(content)
                    yaml.dump(content, f)
                else:  # txt or md
                    f.write(content)
                    
            return {
                'success': True,
                'filepath': filepath,
                'format': format
            }
            
        except Exception as e:
            logger.error(f"Error saving document: {str(e)}")
            raise
            
    def _load_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Load a document"""
        name = params.get('name')
        format = params.get('format', 'txt').lower()
        version = params.get('version')
        
        if not name:
            raise ValueError("Document name required")
            
        filename = f"{name}.{format}"
        if version:
            filepath = os.path.join(self.docs_directory, 'versions', f"{name}_v{version}.{format}")
        else:
            filepath = os.path.join(self.docs_directory, filename)
            
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Document not found: {filepath}")
            
        try:
            with open(filepath, 'r') as f:
                if format == 'json':
                    content = json.load(f)
                elif format == 'yaml':
                    content = yaml.safe_load(f)
                else:  # txt or md
                    content = f.read()
                    
            return {
                'content': content,
                'format': format,
                'filepath': filepath
            }
            
        except Exception as e:
            logger.error(f"Error loading document: {str(e)}")
            raise
            
    def _list_documents(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List all documents"""
        format_filter = params.get('format')
        
        documents = []
        for filename in os.listdir(self.docs_directory):
            if filename.endswith(tuple(f".{fmt}" for fmt in self.supported_formats)):
                if not format_filter or filename.endswith(f".{format_filter}"):
                    filepath = os.path.join(self.docs_directory, filename)
                    stat = os.stat(filepath)
                    documents.append({
                        'name': os.path.splitext(filename)[0],
                        'format': filename.split('.')[-1],
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                    
        return {'documents': documents}
        
    def _convert_format(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert document to different format"""
        name = params.get('name')
        from_format = params.get('from_format', 'txt').lower()
        to_format = params.get('to_format', 'yaml').lower()
        
        if not name:
            raise ValueError("Document name required")
            
        # Load original document
        content = self._load_document({
            'name': name,
            'format': from_format
        })['content']
        
        # Save in new format
        result = self._save_document({
            'name': name,
            'content': content,
            'format': to_format
        })
        
        return {
            'success': True,
            'original_format': from_format,
            'new_format': to_format,
            'filepath': result['filepath']
        }
        
    def _create_version(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new version of a document"""
        name = params.get('name')
        format = params.get('format', 'txt').lower()
        
        if not name:
            raise ValueError("Document name required")
            
        # Load current document
        current = self._load_document({
            'name': name,
            'format': format
        })
        
        # Get next version number
        versions_dir = os.path.join(self.docs_directory, 'versions')
        existing_versions = [f for f in os.listdir(versions_dir) 
                           if f.startswith(f"{name}_v") and f.endswith(f".{format}")]
        next_version = len(existing_versions) + 1
        
        # Save new version
        version_name = f"{name}_v{next_version}"
        result = self._save_document({
            'name': os.path.join('versions', version_name),
            'content': current['content'],
            'format': format
        })
        
        return {
            'success': True,
            'version': next_version,
            'filepath': result['filepath']
        }
        
    def _get_versions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get all versions of a document"""
        name = params.get('name')
        format = params.get('format', 'txt').lower()
        
        if not name:
            raise ValueError("Document name required")
            
        versions_dir = os.path.join(self.docs_directory, 'versions')
        versions = []
        
        for filename in os.listdir(versions_dir):
            if filename.startswith(f"{name}_v") and filename.endswith(f".{format}"):
                filepath = os.path.join(versions_dir, filename)
                stat = os.stat(filepath)
                version_num = int(filename.split('_v')[-1].split('.')[0])
                versions.append({
                    'version': version_num,
                    'filepath': filepath,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
                
        return {
            'document': name,
            'format': format,
            'versions': sorted(versions, key=lambda x: x['version'])
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

    async def create_document(self, doc_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new document with the given content and metadata.
        
        Args:
            doc_id: Unique identifier for the document
            content: Initial content of the document
            metadata: Optional metadata for the document
            
        Returns:
            Dict containing the operation status and document info
        """
        if doc_id in self.documents:
            self.logger.error(f"Document {doc_id} already exists")
            return {"status": "error", "message": f"Document {doc_id} already exists"}
            
        self.documents[doc_id] = {
            "content": content,
            "metadata": metadata or {},
            "version": 1
        }
        
        self.logger.info(f"Created document {doc_id}")
        return {
            "status": "success",
            "message": f"Document {doc_id} created successfully",
            "document": self.documents[doc_id]
        }

    async def get_document(self, doc_id: str) -> Dict[str, Any]:
        """Retrieve a document by its ID.
        
        Args:
            doc_id: ID of the document to retrieve
            
        Returns:
            Dict containing the operation status and document if found
        """
        if doc_id not in self.documents:
            self.logger.error(f"Document {doc_id} not found")
            return {"status": "error", "message": f"Document {doc_id} not found"}
            
        return {
            "status": "success",
            "document": self.documents[doc_id]
        }

    async def update_document(self, doc_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update an existing document's content and/or metadata.
        
        Args:
            doc_id: ID of the document to update
            content: New content for the document
            metadata: Optional new metadata for the document
            
        Returns:
            Dict containing the operation status and updated document
        """
        if doc_id not in self.documents:
            self.logger.error(f"Document {doc_id} not found")
            return {"status": "error", "message": f"Document {doc_id} not found"}
            
        doc = self.documents[doc_id]
        doc["content"] = content
        if metadata:
            doc["metadata"].update(metadata)
        doc["version"] += 1
        
        self.logger.info(f"Updated document {doc_id}")
        return {
            "status": "success",
            "message": f"Document {doc_id} updated successfully",
            "document": doc
        }

    async def delete_document(self, doc_id: str) -> Dict[str, str]:
        """Delete a document by its ID.
        
        Args:
            doc_id: ID of the document to delete
            
        Returns:
            Dict containing the operation status and result message
        """
        if doc_id not in self.documents:
            self.logger.error(f"Document {doc_id} not found")
            return {"status": "error", "message": f"Document {doc_id} not found"}
            
        del self.documents[doc_id]
        self.logger.info(f"Deleted document {doc_id}")
        return {
            "status": "success",
            "message": f"Document {doc_id} deleted successfully"
        }

    def get_supported_formats(self) -> List[str]:
        """Get list of supported document formats"""
        return [fmt for fmt, supported in self.supported_formats.items() 
                if supported]

    async def add_content(self, doc_id: str, content: str) -> Dict[str, Any]:
        """Add content to an existing document."""
        try:
            if doc_id not in self.documents:
                raise ValueError(f"Document not found: {doc_id}")
            
            current_content = self.documents[doc_id]["content"]
            self.documents[doc_id]["content"] = current_content + content
            self.documents[doc_id]["version"] += 1
            
            return {
                "status": "success",
                "message": "Content added to document"
            }
        except Exception as e:
            self.logger.error(f"Error adding content: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
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