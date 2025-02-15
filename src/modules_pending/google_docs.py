#!/usr/bin/env python3

from typing import Dict, Any, List, Optional
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from googleapiclient.discovery import build
import logging

logger = get_logger(__name__)

class GoogleDocsModule(BaseModule):
    """Module for handling Google Docs operations"""
    
    def __init__(self):
        self.service = None
        
    def _initialize_service(self):
        """Initialize Google Docs API service"""
        if not self.service:
            from .google_auth import GoogleAuthModule
            auth_module = GoogleAuthModule()
            auth_result = auth_module.execute({})
            credentials = auth_result['credentials']
            self.service = build('docs', 'v1', credentials=credentials)
            
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Google Docs operations"""
        try:
            self._initialize_service()
            
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            operations = {
                'create_document': self._create_document,
                'get_document': self._get_document,
                'update_document': self._update_document,
                'insert_text': self._insert_text,
                'delete_content': self._delete_content,
                'format_text': self._format_text,
                'create_table': self._create_table,
                'insert_table_row': self._insert_table_row,
                'insert_image': self._insert_image,
                'create_header': self._create_header,
                'create_footer': self._create_footer,
                'apply_style': self._apply_style
            }
            
            if operation not in operations:
                raise ValueError(f"Unknown operation: {operation}")
                
            return operations[operation](params)
            
        except Exception as e:
            logger.error(f"Docs operation error: {str(e)}")
            raise
            
    def _create_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Google Doc"""
        title = params.get('title')
        
        if not title:
            raise ValueError("Document title required")
            
        try:
            document = {
                'title': title
            }
            
            doc = self.service.documents().create(body=document).execute()
            
            # If initial content is provided, insert it
            if params.get('content'):
                self._insert_text({
                    'document_id': doc['documentId'],
                    'text': params['content'],
                    'index': 1  # Start at beginning of document
                })
                
            return {
                'success': True,
                'document_id': doc['documentId'],
                'title': doc['title'],
                'url': f"https://docs.google.com/document/d/{doc['documentId']}/edit"
            }
            
        except Exception as e:
            logger.error(f"Failed to create document: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _get_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get a document's content and metadata"""
        document_id = params.get('document_id')
        
        if not document_id:
            raise ValueError("Document ID required")
            
        try:
            document = self.service.documents().get(
                documentId=document_id
            ).execute()
            
            return {
                'success': True,
                'document': document
            }
            
        except Exception as e:
            logger.error(f"Failed to get document: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _update_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update document content with batch requests"""
        document_id = params.get('document_id')
        requests = params.get('requests', [])
        
        if not document_id or not requests:
            raise ValueError("Document ID and requests required")
            
        try:
            result = self.service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': requests}
            ).execute()
            
            return {
                'success': True,
                'replies': result.get('replies', [])
            }
            
        except Exception as e:
            logger.error(f"Failed to update document: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _insert_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Insert text at a specific location"""
        document_id = params.get('document_id')
        text = params.get('text')
        index = params.get('index', 1)
        
        if not all([document_id, text]):
            raise ValueError("Document ID and text required")
            
        try:
            requests = [{
                'insertText': {
                    'location': {
                        'index': index
                    },
                    'text': text
                }
            }]
            
            return self._update_document({
                'document_id': document_id,
                'requests': requests
            })
            
        except Exception as e:
            logger.error(f"Failed to insert text: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _delete_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete content from the document"""
        document_id = params.get('document_id')
        start_index = params.get('start_index')
        end_index = params.get('end_index')
        
        if not all([document_id, start_index, end_index]):
            raise ValueError("Document ID, start index, and end index required")
            
        try:
            requests = [{
                'deleteContentRange': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    }
                }
            }]
            
            return self._update_document({
                'document_id': document_id,
                'requests': requests
            })
            
        except Exception as e:
            logger.error(f"Failed to delete content: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _format_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply text formatting"""
        document_id = params.get('document_id')
        start_index = params.get('start_index')
        end_index = params.get('end_index')
        format_options = params.get('format_options', {})
        
        if not all([document_id, start_index, end_index]):
            raise ValueError("Document ID, start index, and end index required")
            
        try:
            requests = [{
                'updateTextStyle': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    },
                    'textStyle': format_options,
                    'fields': ','.join(format_options.keys())
                }
            }]
            
            return self._update_document({
                'document_id': document_id,
                'requests': requests
            })
            
        except Exception as e:
            logger.error(f"Failed to format text: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _create_table(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a table in the document"""
        document_id = params.get('document_id')
        rows = params.get('rows', 1)
        columns = params.get('columns', 1)
        index = params.get('index')
        
        if not all([document_id, index]):
            raise ValueError("Document ID and index required")
            
        try:
            requests = [{
                'insertTable': {
                    'location': {
                        'index': index
                    },
                    'rows': rows,
                    'columns': columns
                }
            }]
            
            return self._update_document({
                'document_id': document_id,
                'requests': requests
            })
            
        except Exception as e:
            logger.error(f"Failed to create table: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _insert_table_row(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a row into an existing table"""
        document_id = params.get('document_id')
        table_index = params.get('table_index')
        row_index = params.get('row_index', 0)
        
        if not document_id or table_index is None:
            raise ValueError("Document ID and table index required")
            
        try:
            # First get the document to find the table
            doc = self.service.documents().get(documentId=document_id).execute()
            
            # Find the table in the document
            table_found = False
            current_index = 0
            table_start = 0
            
            for element in doc.get('body', {}).get('content', []):
                if element.get('table'):
                    if current_index == table_index:
                        table_found = True
                        table_start = element.get('startIndex', 0)
                        break
                    current_index += 1
            
            if not table_found:
                raise ValueError(f"Table at index {table_index} not found")
            
            requests = [{
                'insertTableRow': {
                    'tableCellLocation': {
                        'tableStartLocation': {
                            'index': table_start
                        },
                        'rowIndex': row_index
                    },
                    'insertBelow': True
                }
            }]
            
            return self._update_document({
                'document_id': document_id,
                'requests': requests
            })
            
        except Exception as e:
            logger.error(f"Failed to insert table row: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _insert_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Insert an image into the document"""
        document_id = params.get('document_id')
        image_uri = params.get('image_uri')
        index = params.get('index')
        width = params.get('width', {'magnitude': 100, 'unit': 'PT'})
        height = params.get('height', {'magnitude': 100, 'unit': 'PT'})
        
        if not all([document_id, image_uri, index]):
            raise ValueError("Document ID, image URI, and index required")
            
        try:
            requests = [{
                'insertInlineImage': {
                    'location': {
                        'index': index
                    },
                    'uri': image_uri,
                    'objectSize': {
                        'height': height,
                        'width': width
                    }
                }
            }]
            
            return self._update_document({
                'document_id': document_id,
                'requests': requests
            })
            
        except Exception as e:
            logger.error(f"Failed to insert image: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _create_header(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update document header"""
        document_id = params.get('document_id')
        text = params.get('text', '')
        
        if not document_id:
            raise ValueError("Document ID required")
            
        try:
            requests = [{
                'createHeader': {
                    'type': 'DEFAULT'
                }
            }]
            
            # First create the header
            result = self._update_document({
                'document_id': document_id,
                'requests': requests
            })
            
            if result['success'] and text:
                # Then insert text into the header
                header_id = result['replies'][0]['createHeader']['headerId']
                requests = [{
                    'insertText': {
                        'location': {
                            'segmentId': header_id,
                            'index': 0
                        },
                        'text': text
                    }
                }]
                
                return self._update_document({
                    'document_id': document_id,
                    'requests': requests
                })
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to create header: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _create_footer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update document footer"""
        document_id = params.get('document_id')
        text = params.get('text', '')
        
        if not document_id:
            raise ValueError("Document ID required")
            
        try:
            requests = [{
                'createFooter': {
                    'type': 'DEFAULT'
                }
            }]
            
            # First create the footer
            result = self._update_document({
                'document_id': document_id,
                'requests': requests
            })
            
            if result['success'] and text:
                # Then insert text into the footer
                footer_id = result['replies'][0]['createFooter']['footerId']
                requests = [{
                    'insertText': {
                        'location': {
                            'segmentId': footer_id,
                            'index': 0
                        },
                        'text': text
                    }
                }]
                
                return self._update_document({
                    'document_id': document_id,
                    'requests': requests
                })
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to create footer: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _apply_style(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply named style to content"""
        document_id = params.get('document_id')
        style = params.get('style')
        start_index = params.get('start_index')
        end_index = params.get('end_index')
        
        if not all([document_id, style, start_index, end_index]):
            raise ValueError("Document ID, style, start index, and end index required")
            
        try:
            requests = [{
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    },
                    'paragraphStyle': {
                        'namedStyleType': style
                    },
                    'fields': 'namedStyleType'
                }
            }]
            
            return self._update_document({
                'document_id': document_id,
                'requests': requests
            })
            
        except Exception as e:
            logger.error(f"Failed to apply style: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        required_params = {
            'create_document': ['title'],
            'get_document': ['document_id'],
            'update_document': ['document_id', 'requests'],
            'insert_text': ['document_id', 'text'],
            'delete_content': ['document_id', 'start_index', 'end_index'],
            'format_text': ['document_id', 'start_index', 'end_index'],
            'create_table': ['document_id', 'index'],
            'insert_table_row': ['document_id', 'table_index'],
            'insert_image': ['document_id', 'image_uri', 'index'],
            'create_header': ['document_id'],
            'create_footer': ['document_id'],
            'apply_style': ['document_id', 'style', 'start_index', 'end_index']
        }
        
        if operation in required_params:
            return all(params.get(param) for param in required_params[operation])
            
        return True
        
    @property
    def capabilities(self) -> List[str]:
        return [
            'document_creation',
            'document_editing',
            'text_formatting',
            'table_management',
            'image_insertion',
            'header_footer_management',
            'style_application',
            'google_docs_integration'
        ] 