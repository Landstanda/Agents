import pytest
import logging
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

# Mock implementations
class MockGoogleAuthModule:
    async def authenticate(self):
        logging.info("Mock: Google Auth successful")
        return {"access_token": "mock_token_123"}

class MockGoogleCalendarModule:
    async def create_event(self, title, start_time, end_time, attendees=None, description=None):
        logging.info(f"Mock: Created calendar event '{title}'")
        return {
            "event_id": "mock_event_123",
            "html_link": "https://calendar.google.com/mock_event_123"
        }
    
    async def check_availability(self, start_time, end_time, attendees):
        logging.info(f"Mock: Checking availability for {len(attendees)} attendees")
        return {"available": True, "conflicts": []}

class MockEmailSenderModule:
    async def send_notification(self, recipients, subject, body_template, attachments=None):
        logging.info(f"Mock: Sent email to {recipients}")
        return {"status": "sent", "message_id": "mock_email_123"}

class MockSlackModule:
    async def send_message(self, channel, message):
        logging.info(f"Mock: Sent message to {channel}")
        return {"status": "sent", "timestamp": datetime.now().timestamp()}

class MockNotificationModule:
    async def send_notification(self, recipient, message, channel="all"):
        logging.info(f"Mock: Sent notification to {recipient} via {channel}")
        return {"status": "sent"}

# The chain implementation
class MeetingSchedulerChain:
    def __init__(self):
        self.google_auth = MockGoogleAuthModule()
        self.calendar = MockGoogleCalendarModule()
        self.email = MockEmailSenderModule()
        self.slack = MockSlackModule()
        self.notification = MockNotificationModule()

    async def execute(self, chain_vars):
        try:
            # Step 1: Authenticate
            auth_result = await self.google_auth.authenticate()
            
            # Step 2: Check availability
            availability = await self.calendar.check_availability(
                start_time=chain_vars["start_time"],
                end_time=chain_vars["end_time"],
                attendees=chain_vars["attendees"]
            )
            
            if not availability["available"]:
                return {
                    "status": "conflict",
                    "conflicts": availability["conflicts"]
                }
            
            # Step 3: Create calendar event
            event = await self.calendar.create_event(
                title=chain_vars["title"],
                start_time=chain_vars["start_time"],
                end_time=chain_vars["end_time"],
                attendees=chain_vars["attendees"],
                description=chain_vars.get("description", "")
            )
            
            # Step 4: Send email notifications
            if chain_vars.get("send_email", True):
                await self.email.send_notification(
                    recipients=chain_vars["attendees"],
                    subject=f"Meeting Invitation: {chain_vars['title']}",
                    body_template="meeting_invitation",
                    attachments=event["html_link"]
                )
            
            # Step 5: Send Slack notification if requested
            if chain_vars.get("notify_slack"):
                await self.slack.send_message(
                    channel=chain_vars["slack_channel"],
                    message=f"New meeting scheduled: {chain_vars['title']}\nTime: {chain_vars['start_time']}"
                )
            
            # Step 6: Send additional notifications if specified
            if chain_vars.get("additional_notifications"):
                for recipient in chain_vars["additional_notifications"]:
                    await self.notification.send_notification(
                        recipient=recipient,
                        message=f"Meeting scheduled: {chain_vars['title']}"
                    )
            
            return {
                "status": "success",
                "event_id": event["event_id"],
                "event_link": event["html_link"]
            }
            
        except Exception as e:
            logging.error(f"Chain execution failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

# Tests
@pytest.mark.asyncio
async def test_basic_meeting_scheduling():
    chain = MeetingSchedulerChain()
    start_time = datetime.now() + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)
    
    chain_vars = {
        "title": "Team Sync",
        "start_time": start_time,
        "end_time": end_time,
        "attendees": ["team@company.com"],
        "description": "Weekly team sync meeting"
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"
    assert "event_id" in result
    assert "event_link" in result

@pytest.mark.asyncio
async def test_meeting_with_slack_notification():
    chain = MeetingSchedulerChain()
    start_time = datetime.now() + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)
    
    chain_vars = {
        "title": "Project Review",
        "start_time": start_time,
        "end_time": end_time,
        "attendees": ["team@company.com"],
        "notify_slack": True,
        "slack_channel": "project-updates",
        "description": "Monthly project review"
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"

@pytest.mark.asyncio
async def test_meeting_with_additional_notifications():
    chain = MeetingSchedulerChain()
    start_time = datetime.now() + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)
    
    chain_vars = {
        "title": "Client Meeting",
        "start_time": start_time,
        "end_time": end_time,
        "attendees": ["client@company.com", "team@company.com"],
        "notify_slack": True,
        "slack_channel": "client-meetings",
        "additional_notifications": ["manager@company.com"],
        "description": "Client progress review"
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"

@pytest.mark.asyncio
async def test_error_handling():
    chain = MeetingSchedulerChain()
    # Test with missing required fields
    chain_vars = {
        "title": "Test Meeting"
        # Missing start_time, end_time, and attendees
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "error"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__]) 