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
            # Get authentication result from step 1
            auth_result = context.get_result(step_number=1)
            self.logger.debug(f"Auth result: {auth_result}")
            
            if not auth_result or not auth_result.get('success'):
                error_msg = "Authentication failed or no authentication result found"
                self.logger.error(error_msg)
                context.ticket.add_error(error_msg, "auth_failed", None)
                context.ticket.status = TicketStatus.ERROR
                return None

            # Get credentials from auth result
            credentials = auth_result.get('credentials')
            self.logger.debug(f"Credentials: {credentials}")
            
            if not credentials:
                error_msg = "No credentials found in authentication result"
                self.logger.error(error_msg)
                context.ticket.add_error(error_msg, "missing_credentials", None)
                context.ticket.status = TicketStatus.ERROR
                return None

            # Build service
            try:
                # If credentials is already a Credentials object, use it directly
                if isinstance(credentials, Credentials):
                    self.logger.debug("Using existing Credentials object")
                else:
                    self.logger.error("Invalid credentials format")
                    context.ticket.add_error("Invalid credentials format", "invalid_credentials", None)
                    context.ticket.status = TicketStatus.ERROR
                    return None
                
                # Build service
                service = build('calendar', 'v3', credentials=credentials)
                self.logger.debug("Successfully built calendar service")
                return service
                
            except Exception as e:
                error_msg = f"Failed to build calendar service: {str(e)}"
                self.logger.error(error_msg)
                context.ticket.add_error(error_msg, "service_build_failed", None)
                context.ticket.status = TicketStatus.ERROR
                return None

        except Exception as e:
            error_msg = f"Error initializing calendar service: {str(e)}"
            self.logger.error(error_msg)
            context.ticket.add_error(error_msg, "service_init_error", None)
            context.ticket.status = TicketStatus.ERROR
            return None
            
    async def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """Execute calendar operations based on ticket entities"""
        ticket = context.ticket
        self.logger.debug(f"Executing calendar operation with entities: {ticket.entities}")

        # Initialize service first
        service = await self._initialize_service(context)
        if not service:
            error_msg = "Failed to initialize Google Calendar service"
            ticket.add_error(error_msg, "service_initialization_error", None)
            ticket.status = TicketStatus.ERROR
            return {
                'success': False,
                'error': error_msg
            }

        # Get operation type (default to create_event if not specified)
        operation = ticket.entities.get('operation', 'create_event')

        try:
            if operation == 'create_event':
                # Extract event parameters from ticket entities
                event_params = {
                    'time': ticket.entities.get('time'),
                    'date': ticket.entities.get('date'),
                    'description': ticket.entities.get('description'),
                    'participants': ticket.entities.get('participants', []),
                    'duration': ticket.entities.get('duration', 60)
                }
                
                result = await self._create_event(service, event_params)
                if not result.get('success', False):
                    ticket.status = TicketStatus.ERROR
                    ticket.add_error(result.get('error', 'Unknown error'), "calendar_operation_failed", None)
                    return result
                    
                ticket.status = TicketStatus.COMPLETED
                return result
                
            elif operation == 'list_events':
                return await self._list_events(service, context)
            elif operation == 'check_availability':
                return await self._check_availability(service, context)
            else:
                error_msg = f"Unsupported operation: {operation}"
                ticket.add_error(error_msg, "unsupported_operation", None)
                ticket.status = TicketStatus.ERROR
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f"Error executing calendar operation: {str(e)}"
            ticket.add_error(error_msg, "execution_error", None)
            ticket.status = TicketStatus.ERROR
            return {
                'success': False,
                'error': error_msg
            }
            
    async def _create_event(self, service, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Create a calendar event."""
        try:
            # Validate required parameters
            required_params = ['time', 'date', 'description', 'participants']
            missing_params = [param for param in required_params if param not in entities]
            
            if missing_params:
                error_msg = f"Missing required parameters: {', '.join(missing_params)}"
                self.logger.error(f"❌ {error_msg}")
                return {'success': False, 'error': error_msg}

            # Extract parameters
            time = entities['time']
            date = entities['date']
            description = entities['description']
            participants = entities['participants']
            duration = entities.get('duration', 60)  # Default to 60 minutes

            # Calculate start and end times
            start_time = await self._calculate_start_time(date, time)
            end_time = await self._calculate_end_time(start_time, duration)

            # Create event details
            event = {
                'summary': description,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'attendees': [{'email': email} for email in participants],
                'reminders': {
                    'useDefault': True
                }
            }

            # Create the event
            try:
                created_event = await self._execute_api_call(
                    service.events().insert(calendarId='primary', body=event, sendUpdates='all')
                )
                
                return {
                    'success': True,
                    'event_id': created_event.get('id'),
                    'html_link': created_event.get('htmlLink')
                }

            except Exception as e:
                error_msg = f"Failed to create event: {str(e)}"
                self.logger.error(f"❌ {error_msg}")
                return {'success': False, 'error': error_msg}

        except Exception as e:
            error_msg = f"Failed to create event: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}

    async def _calculate_start_time(self, date: str, time: str) -> datetime:
        """Calculate the start time from date and time strings."""
        try:
            # Parse date and time
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            time_obj = datetime.strptime(time, '%H:%M').time()
            
            # Combine date and time
            return datetime.combine(date_obj.date(), time_obj)
            
        except ValueError as e:
            raise ValueError(f"Invalid date or time format: {str(e)}")

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
            
    async def _list_events(self, service, context: ExecutionContext) -> Dict[str, Any]:
        """List calendar events"""
        calendar_id = context.entities.get('calendar_id', 'primary')
        time_min = context.entities.get('time_min')
        time_max = context.entities.get('time_max')
        max_results = context.entities.get('max_results', 10)
        
        try:
            events_result = await self._execute_api_call(
                service.events().list(
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