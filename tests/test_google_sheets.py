#!/usr/bin/env python3

import unittest
import logging
from src.modules.google_sheets import GoogleSheetsModule

# Disable unnecessary logging during tests
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

class TestGoogleSheetsModule(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        self.sheets = GoogleSheetsModule()
        self.test_title = "Test Spreadsheet - Aphrodite"
        
    def test_service_initialization(self):
        """Test Google Sheets service initialization."""
        try:
            self.sheets._initialize_service()
            self.assertIsNotNone(self.sheets.service)
            print("✓ Sheets service initialized successfully")
        except Exception as e:
            self.fail(f"Failed to initialize Sheets service: {str(e)}")
            
    def test_spreadsheet_creation(self):
        """Test creating a new spreadsheet."""
        try:
            result = self.sheets.execute({
                'operation': 'create_spreadsheet',
                'title': self.test_title,
                'sheets': [
                    {'title': 'Data'},
                    {'title': 'Summary'}
                ]
            })
            
            self.assertTrue(result['success'])
            self.assertIn('spreadsheet_id', result)
            self.assertIn('url', result)
            
            # Store spreadsheet_id for other tests
            self.spreadsheet_id = result['spreadsheet_id']
            print(f"✓ Created test spreadsheet: {result['url']}")
            
            return result['spreadsheet_id']
            
        except Exception as e:
            self.fail(f"Failed to create spreadsheet: {str(e)}")
            
    def test_data_operations(self):
        """Test data operations (get, update, append, clear)."""
        try:
            # First create a spreadsheet
            spreadsheet_id = self.test_spreadsheet_creation()
            
            # Update values
            update_result = self.sheets.execute({
                'operation': 'update_values',
                'spreadsheet_id': spreadsheet_id,
                'range': 'Data!A1:C3',
                'values': [
                    ['Name', 'Age', 'City'],
                    ['John Doe', 30, 'New York'],
                    ['Jane Smith', 25, 'Los Angeles']
                ]
            })
            
            self.assertTrue(update_result['success'])
            print(f"✓ Updated values in range")
            
            # Get values
            get_result = self.sheets.execute({
                'operation': 'get_values',
                'spreadsheet_id': spreadsheet_id,
                'range': 'Data!A1:C3'
            })
            
            self.assertTrue(get_result['success'])
            self.assertEqual(len(get_result['values']), 3)  # Header + 2 rows
            print(f"✓ Retrieved values from range")
            
            # Append values
            append_result = self.sheets.execute({
                'operation': 'append_values',
                'spreadsheet_id': spreadsheet_id,
                'range': 'Data!A1:C1',
                'values': [
                    ['Bob Wilson', 35, 'Chicago']
                ]
            })
            
            self.assertTrue(append_result['success'])
            print(f"✓ Appended values to range")
            
            # Clear values
            clear_result = self.sheets.execute({
                'operation': 'clear_values',
                'spreadsheet_id': spreadsheet_id,
                'range': 'Data!A4:C4'  # Clear just the appended row
            })
            
            self.assertTrue(clear_result['success'])
            print(f"✓ Cleared values from range")
            
            return spreadsheet_id
            
        except Exception as e:
            self.fail(f"Data operations failed: {str(e)}")
            
    def test_sheet_management(self):
        """Test sheet creation and formatting."""
        try:
            # Use spreadsheet from data operations
            spreadsheet_id = self.test_data_operations()
            
            # Create new sheet
            sheet_result = self.sheets.execute({
                'operation': 'create_sheet',
                'spreadsheet_id': spreadsheet_id,
                'title': 'Charts',
                'row_count': 50,
                'column_count': 10
            })
            
            self.assertTrue(sheet_result['success'])
            sheet_id = sheet_result['sheet_id']
            print(f"✓ Created new sheet")
            
            # Format range
            format_result = self.sheets.execute({
                'operation': 'format_range',
                'spreadsheet_id': spreadsheet_id,
                'range': 'Data!A1:C1',
                'format': {
                    'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8},
                    'textFormat': {'bold': True}
                }
            })
            
            self.assertTrue(format_result['success'])
            print(f"✓ Applied formatting to range")
            
            # Create chart
            chart_result = self.sheets.execute({
                'operation': 'create_chart',
                'spreadsheet_id': spreadsheet_id,
                'sheet_id': sheet_id,
                'chart_spec': {
                    'title': 'Age Distribution',
                    'basicChart': {
                        'chartType': 'COLUMN',
                        'domains': [{
                            'domain': {
                                'sourceRange': {
                                    'sources': [{
                                        'sheetId': sheet_id,
                                        'startRowIndex': 0,
                                        'endRowIndex': 3,
                                        'startColumnIndex': 0,
                                        'endColumnIndex': 1
                                    }]
                                }
                            }
                        }],
                        'series': [{
                            'series': {
                                'sourceRange': {
                                    'sources': [{
                                        'sheetId': sheet_id,
                                        'startRowIndex': 0,
                                        'endRowIndex': 3,
                                        'startColumnIndex': 1,
                                        'endColumnIndex': 2
                                    }]
                                }
                            }
                        }]
                    }
                }
            })
            
            self.assertTrue(chart_result['success'])
            print(f"✓ Created chart")
            
            # Auto-resize columns
            resize_result = self.sheets.execute({
                'operation': 'auto_resize',
                'spreadsheet_id': spreadsheet_id,
                'sheet_id': sheet_id,
                'dimension': 'COLUMNS'
            })
            
            self.assertTrue(resize_result['success'])
            print(f"✓ Auto-resized columns")
            
            return spreadsheet_id, sheet_id
            
        except Exception as e:
            self.fail(f"Sheet management failed: {str(e)}")
            
    def test_protection_and_formatting(self):
        """Test range protection and conditional formatting."""
        try:
            # Use spreadsheet from sheet management
            spreadsheet_id, sheet_id = self.test_sheet_management()
            
            # Protect header range
            protect_result = self.sheets.execute({
                'operation': 'protect_range',
                'spreadsheet_id': spreadsheet_id,
                'range': 'Data!A1:C1',
                'editors': ['mirror.aphrodite.ca@gmail.com']
            })
            
            self.assertTrue(protect_result['success'])
            print(f"✓ Protected range")
            
            # Add conditional formatting
            condition_result = self.sheets.execute({
                'operation': 'add_conditional_format',
                'spreadsheet_id': spreadsheet_id,
                'range': 'Data!B2:B10',  # Age column
                'condition': {
                    'type': 'NUMBER_GREATER',
                    'values': [{'userEnteredValue': '30'}]
                },
                'format': {
                    'backgroundColor': {'red': 1, 'green': 0.8, 'blue': 0.8}
                }
            })
            
            self.assertTrue(condition_result['success'])
            print(f"✓ Added conditional formatting")
            
            # Clean up - delete test spreadsheet
            from src.modules.google_drive import GoogleDriveModule
            drive = GoogleDriveModule()
            delete_result = drive.execute({
                'operation': 'delete_file',
                'file_id': spreadsheet_id
            })
            
            self.assertTrue(delete_result['success'])
            print(f"✓ Cleaned up test spreadsheet")
            
        except Exception as e:
            self.fail(f"Protection and formatting failed: {str(e)}")
            
    def test_parameter_validation(self):
        """Test parameter validation."""
        # Test invalid operation
        with self.assertRaises(ValueError):
            self.sheets.execute({
                'operation': 'invalid_operation'
            })
            
        # Test missing required parameters
        with self.assertRaises(ValueError):
            self.sheets.execute({
                'operation': 'get_values'
            })
            
        with self.assertRaises(ValueError):
            self.sheets.execute({
                'operation': 'update_values',
                'spreadsheet_id': 'some_id'
            })
            
        print("✓ Parameter validation working correctly")
        
if __name__ == '__main__':
    unittest.main() 