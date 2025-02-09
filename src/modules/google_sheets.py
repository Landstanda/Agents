#!/usr/bin/env python3

from typing import Dict, Any, List, Optional, Union
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from googleapiclient.discovery import build
import logging
from datetime import datetime

logger = get_logger(__name__)

class GoogleSheetsModule(BaseModule):
    """Module for handling Google Sheets operations"""
    
    def __init__(self):
        self.service = None
        self.spreadsheet_mime = 'application/vnd.google-apps.spreadsheet'
        
    def _initialize_service(self):
        """Initialize Google Sheets API service"""
        if not self.service:
            from .google_auth import GoogleAuthModule
            auth_module = GoogleAuthModule()
            auth_result = auth_module.execute({})
            credentials = auth_result['credentials']
            self.service = build('sheets', 'v4', credentials=credentials)
            
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Google Sheets operations"""
        try:
            self._initialize_service()
            
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            operations = {
                'create_spreadsheet': self._create_spreadsheet,
                'get_values': self._get_values,
                'update_values': self._update_values,
                'append_values': self._append_values,
                'clear_values': self._clear_values,
                'create_sheet': self._create_sheet,
                'format_range': self._format_range,
                'create_chart': self._create_chart,
                'protect_range': self._protect_range,
                'add_conditional_format': self._add_conditional_format,
                'auto_resize': self._auto_resize
            }
            
            if operation not in operations:
                raise ValueError(f"Unknown operation: {operation}")
                
            return operations[operation](params)
            
        except Exception as e:
            logger.error(f"Sheets operation error: {str(e)}")
            raise
            
    def _create_spreadsheet(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Google Spreadsheet"""
        title = params.get('title', f'Spreadsheet_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        sheets = params.get('sheets', [{'title': 'Sheet1'}])
        
        try:
            spreadsheet_body = {
                'properties': {'title': title},
                'sheets': [{'properties': sheet} for sheet in sheets]
            }
            
            spreadsheet = self.service.spreadsheets().create(
                body=spreadsheet_body,
                fields='spreadsheetId,spreadsheetUrl'
            ).execute()
            
            # Update sharing settings if specified
            if params.get('share_with'):
                from .google_drive import GoogleDriveModule
                drive = GoogleDriveModule()
                share_result = drive.execute({
                    'operation': 'update_sharing',
                    'file_id': spreadsheet['spreadsheetId'],
                    'role': params.get('role', 'reader'),
                    'email': params['share_with']
                })
                
            return {
                'success': True,
                'spreadsheet_id': spreadsheet['spreadsheetId'],
                'url': spreadsheet['spreadsheetUrl']
            }
            
        except Exception as e:
            logger.error(f"Failed to create spreadsheet: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _get_values(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get values from a range in the spreadsheet"""
        spreadsheet_id = params.get('spreadsheet_id')
        range_name = params.get('range')
        
        if not spreadsheet_id or not range_name:
            raise ValueError("Spreadsheet ID and range required")
            
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueRenderOption=params.get('render_option', 'FORMATTED_VALUE')
            ).execute()
            
            return {
                'success': True,
                'values': result.get('values', []),
                'range': result['range']
            }
            
        except Exception as e:
            logger.error(f"Failed to get values: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _update_values(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update values in a range"""
        spreadsheet_id = params.get('spreadsheet_id')
        range_name = params.get('range')
        values = params.get('values')
        
        if not all([spreadsheet_id, range_name, values]):
            raise ValueError("Spreadsheet ID, range, and values required")
            
        try:
            body = {
                'values': values,
                'majorDimension': params.get('major_dimension', 'ROWS')
            }
            
            result = self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=params.get('input_option', 'USER_ENTERED'),
                body=body
            ).execute()
            
            return {
                'success': True,
                'updated_cells': result.get('updatedCells'),
                'updated_range': result.get('updatedRange')
            }
            
        except Exception as e:
            logger.error(f"Failed to update values: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _append_values(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Append values to a range"""
        spreadsheet_id = params.get('spreadsheet_id')
        range_name = params.get('range')
        values = params.get('values')
        
        if not all([spreadsheet_id, range_name, values]):
            raise ValueError("Spreadsheet ID, range, and values required")
            
        try:
            body = {
                'values': values,
                'majorDimension': params.get('major_dimension', 'ROWS')
            }
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=params.get('input_option', 'USER_ENTERED'),
                insertDataOption=params.get('insert_option', 'INSERT_ROWS'),
                body=body
            ).execute()
            
            return {
                'success': True,
                'updates': result.get('updates'),
                'updated_range': result.get('tableRange')
            }
            
        except Exception as e:
            logger.error(f"Failed to append values: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _clear_values(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Clear values in a range"""
        spreadsheet_id = params.get('spreadsheet_id')
        range_name = params.get('range')
        
        if not spreadsheet_id or not range_name:
            raise ValueError("Spreadsheet ID and range required")
            
        try:
            result = self.service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            return {
                'success': True,
                'cleared_range': result.get('clearedRange')
            }
            
        except Exception as e:
            logger.error(f"Failed to clear values: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _create_sheet(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new sheet to the spreadsheet"""
        spreadsheet_id = params.get('spreadsheet_id')
        title = params.get('title')
        
        if not spreadsheet_id or not title:
            raise ValueError("Spreadsheet ID and title required")
            
        try:
            request = {
                'addSheet': {
                    'properties': {
                        'title': title,
                        'gridProperties': {
                            'rowCount': params.get('row_count', 1000),
                            'columnCount': params.get('column_count', 26)
                        }
                    }
                }
            }
            
            result = self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': [request]}
            ).execute()
            
            return {
                'success': True,
                'sheet_id': result['replies'][0]['addSheet']['properties']['sheetId']
            }
            
        except Exception as e:
            logger.error(f"Failed to create sheet: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _format_range(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply formatting to a range"""
        spreadsheet_id = params.get('spreadsheet_id')
        range_name = params.get('range')
        format_specs = params.get('format')
        
        if not all([spreadsheet_id, range_name, format_specs]):
            raise ValueError("Spreadsheet ID, range, and format specifications required")
            
        try:
            grid_range = self._range_to_grid_range(spreadsheet_id, range_name)
            
            request = {
                'repeatCell': {
                    'range': grid_range,
                    'cell': {
                        'userEnteredFormat': format_specs
                    },
                    'fields': 'userEnteredFormat'
                }
            }
            
            result = self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': [request]}
            ).execute()
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Failed to format range: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _create_chart(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a chart in the spreadsheet"""
        spreadsheet_id = params.get('spreadsheet_id')
        sheet_id = params.get('sheet_id')
        chart_spec = params.get('chart_spec')
        
        if not all([spreadsheet_id, sheet_id, chart_spec]):
            raise ValueError("Spreadsheet ID, sheet ID, and chart specifications required")
            
        try:
            request = {
                'addChart': {
                    'chart': {
                        'spec': chart_spec,
                        'position': {
                            'overlayPosition': {
                                'anchorCell': {
                                    'sheetId': sheet_id,
                                    'rowIndex': params.get('row_index', 0),
                                    'columnIndex': params.get('column_index', 0)
                                }
                            }
                        }
                    }
                }
            }
            
            result = self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': [request]}
            ).execute()
            
            return {
                'success': True,
                'chart_id': result['replies'][0]['addChart']['chart']['chartId']
            }
            
        except Exception as e:
            logger.error(f"Failed to create chart: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _protect_range(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Protect a range from editing"""
        spreadsheet_id = params.get('spreadsheet_id')
        range_name = params.get('range')
        editors = params.get('editors', [])
        
        if not spreadsheet_id or not range_name:
            raise ValueError("Spreadsheet ID and range required")
            
        try:
            grid_range = self._range_to_grid_range(spreadsheet_id, range_name)
            
            request = {
                'addProtectedRange': {
                    'protectedRange': {
                        'range': grid_range,
                        'editors': {
                            'users': editors
                        }
                    }
                }
            }
            
            result = self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': [request]}
            ).execute()
            
            return {
                'success': True,
                'protected_range_id': result['replies'][0]['addProtectedRange']['protectedRange']['protectedRangeId']
            }
            
        except Exception as e:
            logger.error(f"Failed to protect range: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _add_conditional_format(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add conditional formatting to a range"""
        spreadsheet_id = params.get('spreadsheet_id')
        range_name = params.get('range')
        condition = params.get('condition')
        format_specs = params.get('format')
        
        if not all([spreadsheet_id, range_name, condition, format_specs]):
            raise ValueError("Spreadsheet ID, range, condition, and format required")
            
        try:
            grid_range = self._range_to_grid_range(spreadsheet_id, range_name)
            
            request = {
                'addConditionalFormatRule': {
                    'rule': {
                        'ranges': [grid_range],
                        'booleanRule': {
                            'condition': condition,
                            'format': format_specs
                        }
                    }
                }
            }
            
            result = self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': [request]}
            ).execute()
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Failed to add conditional format: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _auto_resize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-resize columns or rows"""
        spreadsheet_id = params.get('spreadsheet_id')
        sheet_id = params.get('sheet_id')
        dimension = params.get('dimension', 'COLUMNS')  # or 'ROWS'
        
        if not spreadsheet_id or not sheet_id:
            raise ValueError("Spreadsheet ID and sheet ID required")
            
        try:
            request = {
                'autoResizeDimensions': {
                    'dimensions': {
                        'sheetId': sheet_id,
                        'dimension': dimension,
                        'startIndex': params.get('start_index', 0),
                        'endIndex': params.get('end_index')
                    }
                }
            }
            
            result = self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': [request]}
            ).execute()
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Failed to auto-resize: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _range_to_grid_range(self, spreadsheet_id: str, range_name: str) -> Dict[str, Any]:
        """Convert A1 notation range to grid range"""
        try:
            # Get sheet ID first
            metadata = self.service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                ranges=[range_name],
                fields='sheets.properties'
            ).execute()
            
            sheet_id = metadata['sheets'][0]['properties']['sheetId']
            
            # Split range into components (e.g., 'Sheet1!A1:B2' -> 'Sheet1', 'A1:B2')
            if '!' in range_name:
                sheet_name, cell_range = range_name.split('!')
            else:
                cell_range = range_name
                
            # Convert A1 notation to grid coordinates
            from string import ascii_uppercase
            
            def column_to_index(col: str) -> int:
                result = 0
                for c in col.upper():
                    result = result * 26 + (ord(c) - ord('A') + 1)
                return result - 1
                
            # Parse start and end coordinates
            start, end = cell_range.split(':')
            start_col = ''.join(c for c in start if c.isalpha())
            start_row = int(''.join(c for c in start if c.isdigit())) - 1
            end_col = ''.join(c for c in end if c.isalpha())
            end_row = int(''.join(c for c in end if c.isdigit())) - 1
            
            return {
                'sheetId': sheet_id,
                'startRowIndex': start_row,
                'endRowIndex': end_row + 1,
                'startColumnIndex': column_to_index(start_col),
                'endColumnIndex': column_to_index(end_col) + 1
            }
            
        except Exception as e:
            logger.error(f"Failed to convert range: {str(e)}")
            raise
            
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        required_params = {
            'create_spreadsheet': [],  # Optional parameters only
            'get_values': ['spreadsheet_id', 'range'],
            'update_values': ['spreadsheet_id', 'range', 'values'],
            'append_values': ['spreadsheet_id', 'range', 'values'],
            'clear_values': ['spreadsheet_id', 'range'],
            'create_sheet': ['spreadsheet_id', 'title'],
            'format_range': ['spreadsheet_id', 'range', 'format'],
            'create_chart': ['spreadsheet_id', 'sheet_id', 'chart_spec'],
            'protect_range': ['spreadsheet_id', 'range'],
            'add_conditional_format': ['spreadsheet_id', 'range', 'condition', 'format'],
            'auto_resize': ['spreadsheet_id', 'sheet_id']
        }
        
        if operation in required_params:
            return all(params.get(param) for param in required_params[operation])
            
        return True
        
    @property
    def capabilities(self) -> List[str]:
        return [
            'spreadsheet_creation',
            'data_management',
            'sheet_formatting',
            'chart_creation',
            'range_protection',
            'conditional_formatting',
            'auto_sizing',
            'google_sheets_integration'
        ] 