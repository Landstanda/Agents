#!/usr/bin/env python3

import unittest
import logging
from src.modules.google_calendar import GoogleCalendarModule
from datetime import datetime, timedelta

# Disable unnecessary logging during tests
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

class TestGoogleCalendarModule(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        self.calendar = GoogleCalendarModule()
        self.test_calendar_name = "Test Calendar - Aphrodite"
        
    def test_service_initialization(self):
        """Test Google Calendar service initialization."""
        try:
            self.calendar._initialize_service()
            self.assertIsNotNone(self.calendar.service)
            print("✓ Calendar service initialized successfully")
        except Exception as e:
            self.fail(f"Failed to initialize Calendar service: {str(e)}")
            
    def test_calendar_creation(self):
        """Test creating a new calendar."""
        try:
            result = self.calendar.execute({
                'operation': 'create_calendar',
                'summary': self.test_calendar_name,
                'description': 'Test calendar for Aphrodite Agent',
                'timezone': 'UTC'
            })
            
            self.assertTrue(result['success'])
            self.assertIn('calendar_id', result)
            self.assertEqual(result['summary'], self.test_calendar_name)
            
            # Store calendar_id for other tests
            self.calendar_id = result['calendar_id']
            print(f"✓ Created test calendar: {result['summary']}")
            
            return result['calendar_id']
            
        except Exception as e:
            self.fail(f"Failed to create calendar: {str(e)}")
            
    def test_event_operations(self):
        """Test event creation, update, and deletion."""
        try:
            # First create a calendar
            calendar_id = self.test_calendar_creation()
            
            # Create an event
            start_time = (datetime.utcnow() + timedelta(hours=1)).isoformat() + 'Z'
            end_time = (datetime.utcnow() + timedelta(hours=2)).isoformat() + 'Z'
            
            create_result = self.calendar.execute({
                'operation': 'create_event',
                'calendar_id': calendar_id,
                'summary': 'Test Event',
                'description': 'This is a test event',
                'start_time': start_time,
                'end_time': end_time,
                'location': 'Virtual',
                'attendees': ['mirror.aphrodite.ca@gmail.com']
            })
            
            self.assertTrue(create_result['success'])
            event_id = create_result['event_id']
            print(f"✓ Created test event: {create_result['html_link']}")
            
            # Update the event
            update_result = self.calendar.execute({
                'operation': 'update_event',
                'calendar_id': calendar_id,
                'event_id': event_id,
                'summary': 'Updated Test Event',
                'description': 'This event has been updated'
            })
            
            self.assertTrue(update_result['success'])
            print(f"✓ Updated test event")
            
            # Get event details
            get_result = self.calendar.execute({
                'operation': 'get_event',
                'calendar_id': calendar_id,
                'event_id': event_id
            })
            
            self.assertTrue(get_result['success'])
            self.assertEqual(get_result['event']['summary'], 'Updated Test Event')
            print(f"✓ Retrieved event details")
            
            # Delete the event
            delete_result = self.calendar.execute({
                'operation': 'delete_event',
                'calendar_id': calendar_id,
                'event_id': event_id
            })
            
            self.assertTrue(delete_result['success'])
            print(f"✓ Deleted test event")
            
            return calendar_id
            
        except Exception as e:
            self.fail(f"Event operations failed: {str(e)}")
            
    def test_list_operations(self):
        """Test listing calendars and events."""
        try:
            # List calendars
            calendars_result = self.calendar.execute({
                'operation': 'list_calendars'
            })
            
            self.assertTrue(calendars_result['success'])
            self.assertIsInstance(calendars_result['calendars'], list)
            print(f"✓ Listed {calendars_result['count']} calendars")
            
            # Create a calendar and event for listing
            calendar_id = self.test_event_operations()
            
            # List events
            events_result = self.calendar.execute({
                'operation': 'list_events',
                'calendar_id': calendar_id,
                'max_results': 10
            })
            
            self.assertTrue(events_result['success'])
            print(f"✓ Listed {events_result['count']} events")
            
            return calendar_id
            
        except Exception as e:
            self.fail(f"List operations failed: {str(e)}")
            
    def test_availability_and_attendees(self):
        """Test availability checking and attendee management."""
        try:
            # Create calendar and event
            calendar_id = self.test_list_operations()
            
            # Create an event for testing
            start_time = (datetime.utcnow() + timedelta(hours=3)).isoformat() + 'Z'
            end_time = (datetime.utcnow() + timedelta(hours=4)).isoformat() + 'Z'
            
            event_result = self.calendar.execute({
                'operation': 'create_event',
                'calendar_id': calendar_id,
                'summary': 'Availability Test Event',
                'start_time': start_time,
                'end_time': end_time
            })
            
            self.assertTrue(event_result['success'])
            event_id = event_result['event_id']
            
            # Check availability
            check_result = self.calendar.execute({
                'operation': 'check_availability',
                'calendar_id': calendar_id,
                'start_time': start_time,
                'end_time': end_time,
                'attendees': ['mirror.aphrodite.ca@gmail.com']
            })
            
            self.assertTrue(check_result['success'])
            print(f"✓ Checked availability")
            
            # Update attendees
            attendees_result = self.calendar.execute({
                'operation': 'update_event_attendees',
                'calendar_id': calendar_id,
                'event_id': event_id,
                'add_attendees': ['mirror.aphrodite.ca@gmail.com']
            })
            
            self.assertTrue(attendees_result['success'])
            print(f"✓ Updated event attendees")
            
            # Set reminders
            reminders_result = self.calendar.execute({
                'operation': 'set_event_reminders',
                'calendar_id': calendar_id,
                'event_id': event_id,
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 30},
                        {'method': 'popup', 'minutes': 15}
                    ]
                }
            })
            
            self.assertTrue(reminders_result['success'])
            print(f"✓ Set event reminders")
            
            # Clean up - delete calendar
            delete_result = self.calendar.execute({
                'operation': 'delete_calendar',
                'calendar_id': calendar_id
            })
            
            self.assertTrue(delete_result['success'])
            print(f"✓ Cleaned up test calendar")
            
        except Exception as e:
            self.fail(f"Availability and attendee operations failed: {str(e)}")
            
    def test_parameter_validation(self):
        """Test parameter validation."""
        # Test invalid operation
        with self.assertRaises(ValueError):
            self.calendar.execute({
                'operation': 'invalid_operation'
            })
            
        # Test missing required parameters
        with self.assertRaises(ValueError):
            self.calendar.execute({
                'operation': 'create_event'
            })
            
        with self.assertRaises(ValueError):
            self.calendar.execute({
                'operation': 'update_event'
            })
            
        print("✓ Parameter validation working correctly")
        
if __name__ == '__main__':
    unittest.main() 