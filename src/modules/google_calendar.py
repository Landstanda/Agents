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
            credentials = context.get_variable('google_credentials')
            if not credentials:
                self.logger.error("No credentials found")
                return None

            self.logger.debug("Credentials found: True")
            self.logger.debug("Using existing Credentials object")
            
            # Initialize Calendar service
            calendar_service = build('calendar', 'v3', credentials=credentials)
            
            self.logger.debug("Successfully built calendar service")
            context.set_variable('calendar_service', calendar_service)
            return calendar_service

        except Exception as e:
            self.logger.error(f"Failed to initialize service: {str(e)}")
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
                    ticket.entities.get('duration', '1 hour')
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
            
    async def _parse_duration(self, duration_str: str) -> int:
        """Convert a duration string like '2 hours' or '30 minutes' to minutes"""
        try:
            if not duration_str:
                return 60  # default 1 hour
            
            parts = duration_str.lower().split()
            if len(parts) != 2:
                return 60
            
            amount = float(parts[0])
            unit = parts[1].rstrip('s')  # remove plural 's' if present
            
            if unit in ['hour', 'hr']:
                return int(amount * 60)
            elif unit in ['minute', 'min']:
                return int(amount)
            else:
                return 60
        except (ValueError, TypeError):
            return 60

    async def _create_event(self, context: ExecutionContext, time: str, date: str, description: str, participants=None, location=None, duration: str = '1 hour') -> Dict[str, Any]:
        """Create a calendar event"""
        try:
            self.logger.debug("Creating calendar event...")
            
            # Get the calendar service
            calendar_service = await self._initialize_service(context)
            if not calendar_service:
                return {'success': False, 'error': 'Failed to initialize calendar service'}

            # Calculate start time
            start_time = await self._calculate_start_time(date, time)
            if not start_time:
                return {'success': False, 'error': 'Invalid start time'}

            # Parse duration and calculate end time
            duration_minutes = await self._parse_duration(duration)
            end_time = start_time + timedelta(minutes=duration_minutes)

            # Create event details
            event = {
                'summary': description,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'America/Los_Angeles',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'America/Los_Angeles',
                },
                'reminders': {
                    'useDefault': True
                }
            }
            
            # Add location if provided
            if location:
                event['location'] = location
            
            # Handle participants
            send_invites = context.ticket.entities.get('send_invites', False)
            
            if participants:
                # Convert to list if string
                if isinstance(participants, str):
                    participant_list = [p.strip() for p in participants.split(',')]
                else:
                    participant_list = [participants]

                if send_invites:
                    # Let Google Calendar handle the email lookups and sending invites
                    event['attendees'] = [{'email': p} if '@' in p else {'displayName': p} for p in participant_list]
                    event['sendUpdates'] = 'all'
                else:
                    # Just add to description if not sending invites
                    participants_str = ', '.join(participant_list)
                    event['description'] = f"{event['description']}\n\nAttendees: {participants_str}"

            # Create the event
            created_event = calendar_service.events().insert(
                calendarId='primary',
                body=event
            ).execute()

            self.logger.info(f"✅ Event created: {created_event.get('htmlLink')}")
            
            return {
                'success': True,
                'event_id': created_event['id'],
                'event_link': created_event.get('htmlLink'),
                'attendees_notified': bool(event.get('attendees', []))
            }

        except Exception as e:
            self.logger.error(f"Error creating event: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def _get_next_weekday(self, day_name: str) -> datetime:
        """Calculate the date of the next occurrence of a given weekday"""
        weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6,
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
        }
        
        day_name = day_name.lower()
        if day_name not in weekdays:
            raise ValueError(f"Invalid day name: {day_name}")
        
        target_weekday = weekdays[day_name]
        current_date = datetime.now()
        current_weekday = current_date.weekday()
        
        # Calculate days until next occurrence
        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        next_date = current_date + timedelta(days=days_ahead)
        return next_date.replace(hour=0, minute=0, second=0, microsecond=0)

    async def _calculate_start_time(self, date_str: str, time_str: str) -> datetime:
        """Calculate the start time for an event"""
        try:
            # Get current time for reference
            now = datetime.now()
            
            # Handle time-of-day terms in date_str
            time_of_day_terms = {
                'tonight': {'date': 'today', 'default_hour': 19, 'is_pm': True},  # 7 PM
                'morning': {'date': 'today', 'default_hour': 9, 'is_pm': False},   # 9 AM
                'afternoon': {'date': 'today', 'default_hour': 14, 'is_pm': False}, # 2 PM
                'evening': {'date': 'today', 'default_hour': 18, 'is_pm': True},   # 6 PM
                'midnight': {'date': 'tomorrow', 'default_hour': 0, 'is_pm': False}, # 12 AM tomorrow
                'noon': {'date': 'today', 'default_hour': 12, 'is_pm': False}       # 12 PM
            }
            
            # Check if date_str is a time-of-day term
            date_str_lower = date_str.lower()
            is_pm = False
            if date_str_lower in time_of_day_terms:
                term_info = time_of_day_terms[date_str_lower]
                # If no specific time provided, use the default for this time of day
                if not time_str:
                    time_str = f"{term_info['default_hour']}:00"
                date_str = term_info['date']
                is_pm = term_info['is_pm']  # Set PM based on time of day
            
            # Parse the date
            if date_str.lower() == 'today':
                event_date = now.date()
            elif date_str.lower() == 'tomorrow':
                event_date = (now + timedelta(days=1)).date()
            elif date_str.lower() in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                                    'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
                # Handle day names
                event_date = (await self._get_next_weekday(date_str)).date()
            else:
                # Try to parse as a date string
                try:
                    event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        # Try alternative format MM/DD/YYYY
                        event_date = datetime.strptime(date_str, '%m/%d/%Y').date()
                    except ValueError:
                        raise ValueError(f"Unsupported date format: {date_str}")
            
            # Parse the time
            time_str = time_str.lower().replace(' ', '')
            if 'am' in time_str or 'pm' in time_str:
                # Handle 12-hour format
                try:
                    if 'pm' in time_str:
                        hour = int(time_str.replace('pm', ''))
                        if hour != 12:
                            hour += 12
                    else:  # am
                        hour = int(time_str.replace('am', ''))
                        if hour == 12:
                            hour = 0
                    minute = 0
                except ValueError:
                    # Try parsing with minutes
                    time_parts = time_str.replace('am', '').replace('pm', '').split(':')
                    if len(time_parts) == 2:
                        hour = int(time_parts[0])
                        minute = int(time_parts[1])
                        if 'pm' in time_str and hour != 12:
                            hour += 12
                        elif 'am' in time_str and hour == 12:
                            hour = 0
                    else:
                        raise ValueError(f"Invalid time format: {time_str}")
            else:
                # Handle 24-hour format or time without AM/PM
                try:
                    if ':' in time_str:
                        hour, minute = map(int, time_str.split(':'))
                    else:
                        hour = int(time_str)
                        minute = 0
                    
                    # If time is ambiguous (no AM/PM) and we're in a PM context, adjust hour
                    if is_pm and hour < 12:
                        hour += 12
                except ValueError:
                    raise ValueError(f"Invalid time format: {time_str}")
            
            # Create final datetime
            event_time = datetime.combine(event_date, time(hour, minute))
            
            # Verify the time hasn't passed
            if event_time < now:
                if date_str.lower() in ['today', 'tonight', 'morning', 'afternoon', 'evening']:
                    # For today's events that have passed, move to tomorrow
                    event_time += timedelta(days=1)
                elif date_str.lower() in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                                      'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
                    # For weekday names, automatically move to next week if time has passed
                    event_time += timedelta(days=7)
                else:
                    raise ValueError("Event time has already passed")
            
            return event_time
            
        except Exception as e:
            self.logger.error(f"Error calculating start time: {str(e)}")
            raise ValueError(f"Error calculating start time: {str(e)}")

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