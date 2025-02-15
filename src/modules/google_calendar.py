#!/usr/bin/env python3

from typing import Dict, Any, List, Optional
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pytz
import logging
import asyncio

logger = get_logger(__name__)

class GoogleCalendarModule(BaseModule):
    """Module for handling Google Calendar operations"""
    
    def __init__(self):
        self.service = None
        logger.debug("🗓️ Initializing Google Calendar Module")
        
    async def _execute_api_call(self, api_call):
        """Execute a Google Calendar API call asynchronously"""
        return await asyncio.to_thread(api_call.execute)
        
    async def _initialize_service(self):
        """Initialize Google Calendar API service"""
        logger.debug("\n=== Google Calendar Service Initialization ===")
        if not self.service:
            try:
                logger.debug("🔄 Importing GoogleAuthModule...")
                from .google_auth import GoogleAuthModule
                logger.debug("✓ GoogleAuthModule imported")
                
                logger.debug("🔐 Creating auth module instance...")
                auth_module = GoogleAuthModule()
                logger.debug("✓ Auth module instance created")
                
                logger.debug("🔑 Executing auth module...")
                auth_result = await auth_module.execute({})
                logger.debug(f"Auth result: {auth_result}")
                
                if not auth_result.get('success'):
                    logger.error(f"❌ Authentication failed: {auth_result.get('error')}")
                    raise ValueError(f"Authentication failed: {auth_result.get('error')}")
                
                logger.debug("✓ Authentication successful")
                credentials = auth_result['credentials']
                
                logger.debug("🔄 Building calendar service...")
                self.service = build('calendar', 'v3', credentials=credentials)
                logger.debug("✓ Calendar service initialized successfully")
            except ImportError as e:
                logger.error(f"❌ Failed to import GoogleAuthModule: {str(e)}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"❌ Failed to initialize calendar service: {str(e)}", exc_info=True)
                raise
            
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Google Calendar operations"""
        try:
            logger.debug(f"\n=== Executing Calendar Operation ===")
            logger.debug(f"Parameters: {params}")
            
            logger.debug("🔄 Initializing service...")
            await self._initialize_service()
            logger.debug("✓ Service initialized")
            
            operation = params.get('operation')
            if not operation:
                error_msg = "No operation specified"
                logger.error(f"❌ {error_msg}")
                return {'success': False, 'error': error_msg}
                
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
                error_msg = f"Unknown operation: {operation}"
                logger.error(f"❌ {error_msg}")
                return {'success': False, 'error': error_msg}
                
            logger.debug(f"🔄 Executing operation: {operation}")
            result = await operations[operation](params)
            logger.debug(f"Operation result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Calendar operation error: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}
            
    async def _create_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a calendar event"""
        logger.debug(f"Creating calendar event with params: {params}")
        calendar_id = params.get('calendar_id', 'primary')
        summary = params.get('summary')
        start_time = params.get('start_time')
        duration = params.get('duration', 3600)  # Default 1 hour in seconds
        timezone = params.get('timezone', 'UTC')
        description = params.get('description', '')
        location = params.get('location', '')
        attendees = params.get('attendees') or []  # Default to empty list if None
        recurrence = params.get('recurrence', None)
        reminders = params.get('reminders', {'useDefault': True})
        
        if not all([summary, start_time]):
            error_msg = "Missing required parameters"
            logger.error(f"{error_msg}. Required: summary={bool(summary)}, start_time={bool(start_time)}")
            raise ValueError(error_msg)
            
        try:
            # Parse start time
            if isinstance(start_time, str):
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            else:
                start_dt = start_time
                
            # Calculate end time
            end_dt = start_dt + timedelta(seconds=duration)
            
            logger.debug("Building event object")
            event = {
                'summary': summary,
                'location': location,
                'description': description,
                'start': {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': timezone,
                },
                'visibility': 'default',
                'transparency': 'opaque'
            }
            
            # Only add attendees if the list is not empty
            if attendees and isinstance(attendees, list) and all(isinstance(email, str) for email in attendees):
                logger.debug(f"Adding attendees: {attendees}")
                event['attendees'] = [{'email': email} for email in attendees]
                
            if recurrence:
                logger.debug(f"Adding recurrence: {recurrence}")
                event['recurrence'] = [recurrence]
                
            if reminders:
                logger.debug(f"Adding reminders: {reminders}")
                event['reminders'] = reminders
                
            logger.debug(f"Inserting event into calendar {calendar_id}")
            created_event = await self._execute_api_call(
                self.service.events().insert(
                    calendarId=calendar_id,
                    body=event,
                    sendUpdates='all' if attendees else 'none'  # Only send updates if there are attendees
                )
            )
            
            logger.debug(f"Event created successfully: {created_event['id']}")
            return {
                'success': True,
                'event_id': created_event['id'],
                'html_link': created_event['htmlLink']
            }
            
        except Exception as e:
            logger.error(f"Failed to create event: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}
            
    async def _update_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing calendar event"""
        calendar_id = params.get('calendar_id', 'primary')
        event_id = params.get('event_id')
        
        if not event_id:
            raise ValueError("Event ID required")
            
        try:
            # Get existing event
            event = await self._execute_api_call(
                self.service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                )
            )
            
            # Update fields
            update_fields = ['summary', 'location', 'description', 'start', 'end']
            for field in update_fields:
                if field in params:
                    if field in ['start', 'end']:
                        event[field]['dateTime'] = params[field]
                    else:
                        event[field] = params[field]
                        
            updated_event = await self._execute_api_call(
                self.service.events().update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event,
                    sendUpdates='all' if event.get('attendees') else 'none'
                )
            )
            
            return {
                'success': True,
                'event_id': updated_event['id'],
                'html_link': updated_event['htmlLink']
            }
            
        except Exception as e:
            logger.error(f"Failed to update event: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def _delete_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a calendar event"""
        calendar_id = params.get('calendar_id', 'primary')
        event_id = params.get('event_id')
        
        if not event_id:
            raise ValueError("Event ID required")
            
        try:
            await self._execute_api_call(
                self.service.events().delete(
                    calendarId=calendar_id,
                    eventId=event_id,
                    sendUpdates='all'
                )
            )
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Failed to delete event: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def _get_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get details of a specific event"""
        calendar_id = params.get('calendar_id', 'primary')
        event_id = params.get('event_id')
        
        if not event_id:
            raise ValueError("Event ID required")
            
        try:
            event = await self._execute_api_call(
                self.service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                )
            )
            
            return {
                'success': True,
                'event': event
            }
            
        except Exception as e:
            logger.error(f"Failed to get event: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def _list_events(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List calendar events"""
        calendar_id = params.get('calendar_id', 'primary')
        time_min = params.get('time_min')
        time_max = params.get('time_max')
        max_results = params.get('max_results', 10)
        
        try:
            events_result = await self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return {'success': True, 'events': events}
            
        except Exception as e:
            logger.error(f"Failed to list events: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def _create_calendar(self, params: Dict[str, Any]) -> Dict[str, Any]:
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
            
            created_calendar = await self.service.calendars().insert(body=calendar).execute()
            return {
                'success': True,
                'calendar_id': created_calendar['id']
            }
            
        except Exception as e:
            logger.error(f"Failed to create calendar: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def _list_calendars(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available calendars"""
        try:
            calendars_result = await self.service.calendarList().list().execute()
            calendars = calendars_result.get('items', [])
            return {'success': True, 'calendars': calendars}
            
        except Exception as e:
            logger.error(f"Failed to list calendars: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def _check_availability(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check availability for a time slot"""
        calendar_id = params.get('calendar_id', 'primary')
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        timezone = params.get('timezone', 'UTC')
        
        if not all([start_time, end_time]):
            raise ValueError("Start time and end time required")
            
        try:
            # Convert times to RFC3339 format if they're datetime objects
            if isinstance(start_time, datetime):
                start_time = start_time.isoformat()
            if isinstance(end_time, datetime):
                end_time = end_time.isoformat()
                
            # Query for events in the time range
            events_result = await self.service.events().list(
                calendarId=calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True
            ).execute()
            
            events = events_result.get('items', [])
            is_available = len(events) == 0
            
            return {
                'success': True,
                'is_available': is_available,
                'conflicting_events': events if not is_available else []
            }
            
        except Exception as e:
            logger.error(f"Failed to check availability: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def _update_event_attendees(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update event attendees"""
        calendar_id = params.get('calendar_id', 'primary')
        event_id = params.get('event_id')
        attendees = params.get('attendees', [])
        
        if not event_id:
            raise ValueError("Event ID required")
            
        try:
            # Get existing event
            event = await self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update attendees
            event['attendees'] = [{'email': email} for email in attendees]
            
            updated_event = await self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates='all'
            ).execute()
            
            return {
                'success': True,
                'event_id': updated_event['id']
            }
            
        except Exception as e:
            logger.error(f"Failed to update event attendees: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def _set_event_reminders(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set event reminders"""
        calendar_id = params.get('calendar_id', 'primary')
        event_id = params.get('event_id')
        reminders = params.get('reminders', {'useDefault': True})
        
        if not event_id:
            raise ValueError("Event ID required")
            
        try:
            # Get existing event
            event = await self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update reminders
            event['reminders'] = reminders
            
            updated_event = await self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            return {
                'success': True,
                'event_id': updated_event['id']
            }
            
        except Exception as e:
            logger.error(f"Failed to set event reminders: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def _delete_calendar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a calendar"""
        calendar_id = params.get('calendar_id')
        
        if not calendar_id:
            raise ValueError("Calendar ID required")
            
        try:
            await self.service.calendars().delete(calendarId=calendar_id).execute()
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
            'create_event': ['summary', 'start_time'],
            'update_event': ['event_id'],
            'delete_event': ['event_id'],
            'get_event': ['event_id'],
            'create_calendar': ['summary'],
            'check_availability': ['start_time'],
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