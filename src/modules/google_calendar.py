#!/usr/bin/env python3

from typing import Dict, Any, List, Optional
from src.core.module_interface import BaseModule
from src.execution.context import ExecutionContext
from src.utils.logging import get_logger
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pytz
import logging
import asyncio
from google.oauth2.credentials import Credentials
from src.models.ticket import TicketStatus
from src.models import Ticket
import re
from datetime import time

logger = get_logger(__name__)

class GoogleCalendarModule(BaseModule):
    """Module for handling Google Calendar operations"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.logger.debug("🗓️ Initializing Google Calendar Module")
        self.service = None
        self.auth_module = None
        
    async def _execute_api_call(self, api_call):
        """Execute a Google Calendar API call asynchronously"""
        return await asyncio.to_thread(api_call.execute)
        
    async def _initialize_service(self, context: ExecutionContext) -> Optional[Any]:
        """Initialize the Google Calendar service"""
        try:
            # First try to get credentials from context variables
            credentials = context.get_variable('google_credentials')
            
            if not credentials:
                # Try to get authentication result from step 1
                auth_result = context.get_result(step_number=1)
                self.logger.debug(f"Auth result: {auth_result}")
                
                if not auth_result or not auth_result.get('success'):
                    error_msg = "Authentication failed or no authentication result found"
                    self.logger.error(error_msg)
                    context.ticket.add_error(error_msg, "auth_failed", None)
                    context.ticket.update_status(TicketStatus.ERROR)
                    return None

                # Get credentials from auth result
                credentials = auth_result.get('credentials')
                
            self.logger.debug(f"Credentials found: {credentials is not None}")
            
            if not credentials:
                error_msg = "No credentials found in context or authentication result"
                self.logger.error(error_msg)
                context.ticket.add_error(error_msg, "missing_credentials", None)
                context.ticket.update_status(TicketStatus.ERROR)
                return None

            # Build service
            try:
                # If credentials is already a Credentials object, use it directly
                if isinstance(credentials, Credentials):
                    self.logger.debug("Using existing Credentials object")
                else:
                    self.logger.error("Invalid credentials format")
                    context.ticket.add_error("Invalid credentials format", "invalid_credentials", None)
                    context.ticket.update_status(TicketStatus.ERROR)
                    return None
                
                # Build service
                service = build('calendar', 'v3', credentials=credentials)
                self.logger.debug("Successfully built calendar service")
                return service
                
            except Exception as e:
                error_msg = f"Failed to build calendar service: {str(e)}"
                self.logger.error(error_msg)
                context.ticket.add_error(error_msg, "service_build_failed", None)
                context.ticket.update_status(TicketStatus.ERROR)
                return None

        except Exception as e:
            error_msg = f"Error initializing calendar service: {str(e)}"
            self.logger.error(error_msg)
            context.ticket.add_error(error_msg, "service_init_error", None)
            context.ticket.update_status(TicketStatus.ERROR)
            return None
            
    async def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """Execute calendar operations based on ticket entities"""
        ticket = context.ticket
        self.logger.debug(f"Executing calendar operation with entities: {ticket.entities}")

        # Make sure entities are set in the context
        for key, value in ticket.entities.items():
            context.set_variable(key, value)

        # Initialize service first
        service = await self._initialize_service(context)
        if not service:
            error_msg = "Failed to initialize Google Calendar service"
            ticket.add_error(error_msg, "service_initialization_error", None)
            # Don't update status to ERROR here, let the orchestrator handle it
            return {
                "success": False,
                "error": error_msg
            }
            
        self.service = service
        
        # Determine operation based on entities
        operation = ticket.entities.get('operation', 'create_event')
        
        try:
            if operation == 'create_event':
                result = await self._create_event(
                    context,
                    ticket.entities.get('time'),
                    ticket.entities.get('date'),
                    ticket.entities.get('description', 'Meeting'),
                    ticket.entities.get('participants'),
                    ticket.entities.get('location'),
                    ticket.entities.get('duration', 60)
                )
                return result
            elif operation == 'list_events':
                # Implementation for listing events
                return await self._list_events(context)
            elif operation == 'check_availability':
                return await self._check_availability(service, context)
            else:
                error_msg = f"Unsupported calendar operation: {operation}"
                ticket.add_error(error_msg, "unsupported_operation", None)
                # Don't update status to ERROR here
                return {
                    "success": False,
                    "error": error_msg
                }
        except Exception as e:
            error_msg = f"Error executing calendar operation: {str(e)}"
            self.logger.error(error_msg)
            ticket.add_error(error_msg, "calendar_operation_error", None)
            # Don't update status to ERROR here
            return {
                "success": False,
                "error": error_msg
            }
            
    async def _create_event(self, context: ExecutionContext, time: str, date: str, description: str, participants=None, location=None, duration: int = 60) -> Dict[str, Any]:
        """Create a calendar event."""
        try:
            # Validate required parameters
            if not time or not date or not description:
                error_msg = "Missing required parameters: time, date, and description are required"
                self.logger.error(f"❌ {error_msg}")
                return {'success': False, 'error': error_msg}
            
            try:
                # Calculate start and end times
                time_obj = await self._calculate_start_time(date, time)
                end_time = time_obj + timedelta(minutes=duration)
            except ValueError as e:
                error_msg = f"Invalid date or time: {str(e)}"
                self.logger.error(f"❌ {error_msg}")
                return {'success': False, 'error': error_msg}

            # Create event details
            event = {
                'summary': description,
                'description': description,
                'start': {
                    'dateTime': time_obj.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'reminders': {
                    'useDefault': True
                }
            }
            
            # Add location if provided
            if location:
                event['location'] = location
            
            # Handle participants
            attendees = []
            if participants:
                # If participants is a string, convert to list
                if isinstance(participants, str):
                    # Split by comma if multiple emails in one string
                    if ',' in participants:
                        participant_list = [p.strip() for p in participants.split(',')]
                    else:
                        participant_list = [participants]
                elif isinstance(participants, list):
                    participant_list = participants
                else:
                    participant_list = []
                    
                # Process each participant
                for participant in participant_list:
                    # If it's a string that looks like an email
                    if isinstance(participant, str) and '@' in participant:
                        attendees.append({'email': participant})
                    # If it's a dict with an email key
                    elif isinstance(participant, dict) and 'email' in participant:
                        attendees.append(participant)
                    # If it's just a name, log it but don't add (no email)
                    elif isinstance(participant, str):
                        self.logger.warning(f"Participant '{participant}' doesn't have an email address, skipping")
            
            # Add attendees if any
            if attendees:
                event['attendees'] = attendees
                
            # Create the event
            try:
                created_event = await self._execute_api_call(
                    self.service.events().insert(calendarId='primary', body=event, sendUpdates='all')
                )
                
                self.logger.info(f"✅ Event created: {created_event.get('htmlLink')}")
                return {
                    'success': True,
                    'event_id': created_event.get('id'),
                    'event_link': created_event.get('htmlLink'),
                    'summary': created_event.get('summary'),
                    'start_time': created_event.get('start', {}).get('dateTime'),
                    'end_time': created_event.get('end', {}).get('dateTime')
                }
            except Exception as e:
                error_msg = f"Failed to create event: {str(e)}"
                self.logger.error(f"❌ {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            self.logger.error(f"Error creating event: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def _calculate_start_time(self, date_str: str, time_str: str) -> datetime:
        """Calculate start time from date and time strings"""
        try:
            # Handle natural language dates
            now = datetime.now()
            
            # Handle "today", "tomorrow", etc.
            if date_str.lower() == 'today':
                date_obj = now.date()
            elif date_str.lower() == 'tomorrow':
                date_obj = (now + timedelta(days=1)).date()
            else:
                # Try different date formats
                date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']
                date_obj = None
                
                for fmt in date_formats:
                    try:
                        date_obj = datetime.strptime(date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                
                if not date_obj:
                    raise ValueError(f"Unsupported date format: {date_str}")
            
            # Handle time formats
            time_obj = None
            
            # Handle natural language time like "7pm"
            time_match = re.match(r'(\d+)(?::(\d+))?\s*(am|pm)?', time_str.lower())
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                ampm = time_match.group(3)
                
                # Adjust hour for PM
                if ampm == 'pm' and hour < 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
                
                time_obj = time(hour, minute)
            else:
                # Try standard time formats
                time_formats = ['%H:%M', '%I:%M%p', '%I%p']
                
                for fmt in time_formats:
                    try:
                        time_obj = datetime.strptime(time_str, fmt).time()
                        break
                    except ValueError:
                        continue
                
                if not time_obj:
                    raise ValueError(f"Unsupported time format: {time_str}")
            
            # Combine date and time
            return datetime.combine(date_obj, time_obj)
            
        except Exception as e:
            self.logger.error(f"Error calculating start time: {str(e)}")
            raise ValueError(f"Failed to parse date '{date_str}' or time '{time_str}': {str(e)}")

    async def _calculate_end_time(self, start_time: datetime, duration: int) -> datetime:
        """Calculate the end time based on start time and duration in minutes."""
        try:
            return start_time + timedelta(minutes=duration)
        except Exception as e:
            raise ValueError(f"Failed to calculate end time: {str(e)}")
            
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
            
    async def _list_events(self, context: ExecutionContext) -> Dict[str, Any]:
        """List calendar events"""
        calendar_id = context.entities.get('calendar_id', 'primary')
        time_min = context.entities.get('time_min')
        time_max = context.entities.get('time_max')
        max_results = context.entities.get('max_results', 10)
        
        try:
            events_result = await self._execute_api_call(
                self.service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime'
                )
            )
            
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
            
            created_calendar = await self._execute_api_call(
                self.service.calendars().insert(body=calendar)
            )
            
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
            calendars_result = await self._execute_api_call(
                self.service.calendarList().list()
            )
            
            calendars = calendars_result.get('items', [])
            return {'success': True, 'calendars': calendars}
            
        except Exception as e:
            logger.error(f"Failed to list calendars: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    async def _check_availability(self, service, context: ExecutionContext) -> Dict[str, Any]:
        """Check availability for a time slot"""
        calendar_id = context.entities.get('calendar_id', 'primary')
        start_time = context.entities.get('start_time')
        end_time = context.entities.get('end_time')
        timezone = context.entities.get('timezone', 'UTC')
        
        if not all([start_time, end_time]):
            raise ValueError("Start time and end time required")
            
        try:
            # Convert times to RFC3339 format if they're datetime objects
            if isinstance(start_time, datetime):
                start_time = start_time.isoformat()
            if isinstance(end_time, datetime):
                end_time = end_time.isoformat()
                
            # Query for events in the time range
            events_result = await self._execute_api_call(
                service.events().list(
                    calendarId=calendar_id,
                    timeMin=start_time,
                    timeMax=end_time,
                    singleEvents=True
                )
            )
            
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
            event = await self._execute_api_call(
                self.service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                )
            )
            
            # Update attendees
            event['attendees'] = [{'email': email} for email in attendees]
            
            updated_event = await self._execute_api_call(
                self.service.events().update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event,
                    sendUpdates='all'
                )
            )
            
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
            event = await self._execute_api_call(
                self.service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                )
            )
            
            # Update reminders
            event['reminders'] = reminders
            
            updated_event = await self._execute_api_call(
                self.service.events().update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event
                )
            )
            
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
            await self._execute_api_call(
                self.service.calendars().delete(calendarId=calendar_id)
            )
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