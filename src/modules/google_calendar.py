#!/usr/bin/env python3

from typing import Dict, Any, List, Optional
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pytz
import logging

logger = get_logger(__name__)

class GoogleCalendarModule(BaseModule):
    """Module for handling Google Calendar operations"""
    
    def __init__(self):
        self.service = None
        
    def _initialize_service(self):
        """Initialize Google Calendar API service"""
        if not self.service:
            from .google_auth import GoogleAuthModule
            auth_module = GoogleAuthModule()
            auth_result = auth_module.execute({})
            credentials = auth_result['credentials']
            self.service = build('calendar', 'v3', credentials=credentials)
            
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Google Calendar operations"""
        try:
            self._initialize_service()
            
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            operations = {
                'create_event': self._create_event,
                'update_event': self._update_event,
                'delete_event': self._delete_event,
                'get_event': self._get_event,
                'list_events': self._list_events,
                'create_calendar': self._create_calendar,
                'list_calendars': self._list_calendars,
                'check_availability': self._check_availability,
                'update_event_attendees': self._update_event_attendees,
                'set_event_reminders': self._set_event_reminders,
                'delete_calendar': self._delete_calendar
            }
            
            if operation not in operations:
                raise ValueError(f"Unknown operation: {operation}")
                
            return operations[operation](params)
            
        except Exception as e:
            logger.error(f"Calendar operation error: {str(e)}")
            raise
            
    def _create_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a calendar event"""
        calendar_id = params.get('calendar_id', 'primary')
        summary = params.get('summary')
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        timezone = params.get('timezone', 'UTC')
        description = params.get('description', '')
        location = params.get('location', '')
        attendees = params.get('attendees', [])
        recurrence = params.get('recurrence', None)
        reminders = params.get('reminders', {'useDefault': True})
        
        if not all([summary, start_time, end_time]):
            raise ValueError("Summary, start time, and end time are required")
            
        try:
            event = {
                'summary': summary,
                'location': location,
                'description': description,
                'start': {
                    'dateTime': start_time,
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': timezone,
                }
            }
            
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
                
            if recurrence:
                event['recurrence'] = [recurrence]
                
            if reminders:
                event['reminders'] = reminders
                
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event,
                sendUpdates='all' if attendees else 'none'
            ).execute()
            
            return {
                'success': True,
                'event_id': created_event['id'],
                'html_link': created_event['htmlLink']
            }
            
        except Exception as e:
            logger.error(f"Failed to create event: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _update_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing calendar event"""
        calendar_id = params.get('calendar_id', 'primary')
        event_id = params.get('event_id')
        
        if not event_id:
            raise ValueError("Event ID required")
            
        try:
            # Get existing event
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update fields
            update_fields = ['summary', 'location', 'description', 'start', 'end']
            for field in update_fields:
                if field in params:
                    if field in ['start', 'end']:
                        event[field]['dateTime'] = params[field]
                    else:
                        event[field] = params[field]
                        
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates='all' if event.get('attendees') else 'none'
            ).execute()
            
            return {
                'success': True,
                'event_id': updated_event['id'],
                'html_link': updated_event['htmlLink']
            }
            
        except Exception as e:
            logger.error(f"Failed to update event: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _delete_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a calendar event"""
        calendar_id = params.get('calendar_id', 'primary')
        event_id = params.get('event_id')
        
        if not event_id:
            raise ValueError("Event ID required")
            
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendUpdates='all'
            ).execute()
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Failed to delete event: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _get_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get details of a specific event"""
        calendar_id = params.get('calendar_id', 'primary')
        event_id = params.get('event_id')
        
        if not event_id:
            raise ValueError("Event ID required")
            
        try:
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            return {
                'success': True,
                'event': event
            }
            
        except Exception as e:
            logger.error(f"Failed to get event: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _list_events(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List calendar events"""
        calendar_id = params.get('calendar_id', 'primary')
        max_results = params.get('max_results', 10)
        time_min = params.get('time_min', datetime.utcnow().isoformat() + 'Z')
        time_max = params.get('time_max')
        query = params.get('query')
        
        try:
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime',
                q=query
            ).execute()
            
            events = events_result.get('items', [])
            
            return {
                'success': True,
                'events': events,
                'count': len(events)
            }
            
        except Exception as e:
            logger.error(f"Failed to list events: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _create_calendar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new calendar"""
        summary = params.get('summary')
        description = params.get('description', '')
        timezone = params.get('timezone', 'UTC')
        
        if not summary:
            raise ValueError("Calendar summary required")
            
        try:
            calendar = {
                'summary': summary,
                'description': description,
                'timeZone': timezone
            }
            
            created_calendar = self.service.calendars().insert(body=calendar).execute()
            
            return {
                'success': True,
                'calendar_id': created_calendar['id'],
                'summary': created_calendar['summary']
            }
            
        except Exception as e:
            logger.error(f"Failed to create calendar: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _list_calendars(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available calendars"""
        try:
            calendars_result = self.service.calendarList().list().execute()
            calendars = calendars_result.get('items', [])
            
            return {
                'success': True,
                'calendars': calendars,
                'count': len(calendars)
            }
            
        except Exception as e:
            logger.error(f"Failed to list calendars: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _check_availability(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check availability for a time slot"""
        calendar_id = params.get('calendar_id', 'primary')
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        attendees = params.get('attendees', [])
        
        if not all([start_time, end_time]):
            raise ValueError("Start time and end time required")
            
        try:
            # Create free/busy request
            body = {
                'timeMin': start_time,
                'timeMax': end_time,
                'timeZone': 'UTC',
                'items': [{'id': calendar_id}]
            }
            
            if attendees:
                body['items'].extend([{'id': email} for email in attendees])
                
            freebusy = self.service.freebusy().query(body=body).execute()
            calendars = freebusy.get('calendars', {})
            
            # Process results
            conflicts = {}
            for cal_id, busy in calendars.items():
                if busy.get('errors'):
                    conflicts[cal_id] = {'error': busy['errors']}
                elif busy.get('busy'):
                    conflicts[cal_id] = {'busy': busy['busy']}
                    
            return {
                'success': True,
                'is_available': len(conflicts) == 0,
                'conflicts': conflicts
            }
            
        except Exception as e:
            logger.error(f"Failed to check availability: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _update_event_attendees(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update event attendees"""
        calendar_id = params.get('calendar_id', 'primary')
        event_id = params.get('event_id')
        add_attendees = params.get('add_attendees', [])
        remove_attendees = params.get('remove_attendees', [])
        
        if not event_id:
            raise ValueError("Event ID required")
            
        try:
            # Get existing event
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update attendees
            current_attendees = event.get('attendees', [])
            current_emails = {a['email'] for a in current_attendees}
            
            # Remove specified attendees
            if remove_attendees:
                current_attendees = [
                    a for a in current_attendees 
                    if a['email'] not in remove_attendees
                ]
                
            # Add new attendees
            for email in add_attendees:
                if email not in current_emails:
                    current_attendees.append({'email': email})
                    
            event['attendees'] = current_attendees
            
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates='all'
            ).execute()
            
            return {
                'success': True,
                'event_id': updated_event['id'],
                'attendees': updated_event.get('attendees', [])
            }
            
        except Exception as e:
            logger.error(f"Failed to update attendees: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _set_event_reminders(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set event reminders"""
        calendar_id = params.get('calendar_id', 'primary')
        event_id = params.get('event_id')
        reminders = params.get('reminders')
        
        if not event_id or not reminders:
            raise ValueError("Event ID and reminders required")
            
        try:
            # Get existing event
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update reminders
            event['reminders'] = reminders
            
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates='none'
            ).execute()
            
            return {
                'success': True,
                'event_id': updated_event['id'],
                'reminders': updated_event['reminders']
            }
            
        except Exception as e:
            logger.error(f"Failed to set reminders: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def _delete_calendar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a calendar"""
        calendar_id = params.get('calendar_id')
        
        if not calendar_id:
            raise ValueError("Calendar ID required")
            
        try:
            self.service.calendars().delete(calendarId=calendar_id).execute()
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Failed to delete calendar: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        required_params = {
            'create_event': ['summary', 'start_time', 'end_time'],
            'update_event': ['event_id'],
            'delete_event': ['event_id'],
            'get_event': ['event_id'],
            'create_calendar': ['summary'],
            'check_availability': ['start_time', 'end_time'],
            'update_event_attendees': ['event_id'],
            'set_event_reminders': ['event_id', 'reminders']
        }
        
        if operation in required_params:
            return all(params.get(param) for param in required_params[operation])
            
        return True
        
    @property
    def capabilities(self) -> List[str]:
        return [
            'event_creation',
            'event_management',
            'calendar_management',
            'availability_checking',
            'attendee_management',
            'reminder_management',
            'google_calendar_integration'
        ] 