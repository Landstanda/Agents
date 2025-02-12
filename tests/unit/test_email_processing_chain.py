import pytest
import logging
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# Mock implementations
class MockEmailReaderModule:
    async def fetch_emails(self, since=None, folder="INBOX"):
        logging.info(f"Mock: Fetching emails from {folder}")
        return [{
            "id": "email_123",
            "subject": "Urgent: Client Meeting",
            "from": "client@company.com",
            "body": "We need to discuss the project ASAP",
            "date": datetime.now(),
            "labels": ["client", "urgent"]
        }, {
            "id": "email_124",
            "subject": "Weekly Report",
            "from": "team@company.com",
            "body": "Here's the weekly progress report",
            "date": datetime.now(),
            "labels": ["internal", "report"]
        }]

    async def apply_labels(self, email_id, labels):
        logging.info(f"Mock: Applied labels {labels} to email {email_id}")
        return {"status": "success"}

    async def move_to_folder(self, email_id, folder):
        logging.info(f"Mock: Moved email {email_id} to {folder}")
        return {"status": "success"}

class MockDataCleanerModule:
    async def clean_email_content(self, content):
        logging.info("Mock: Cleaning email content")
        return {
            "cleaned_text": content,
            "extracted_entities": ["meeting", "project"],
            "priority_score": 0.8
        }

class MockNotificationModule:
    async def send_notification(self, recipient, message, channel="all"):
        logging.info(f"Mock: Sent notification to {recipient} via {channel}")
        return {"status": "sent"}

class MockSlackModule:
    async def send_message(self, channel, message):
        logging.info(f"Mock: Sent message to {channel}")
        return {"status": "sent", "timestamp": datetime.now().timestamp()}

class MockGoogleDriveModule:
    async def create_folder(self, name, parent_id=None):
        logging.info(f"Mock: Created folder {name}")
        return {"folder_id": "folder_123"}

    async def save_email(self, email_data, folder_id):
        logging.info(f"Mock: Saved email to folder {folder_id}")
        return {
            "file_id": "file_123",
            "url": "https://drive.google.com/file_123"
        }

# The chain implementation
class EmailProcessingChain:
    def __init__(self):
        self.email_reader = MockEmailReaderModule()
        self.data_cleaner = MockDataCleanerModule()
        self.notification = MockNotificationModule()
        self.slack = MockSlackModule()
        self.drive = MockGoogleDriveModule()

    async def execute(self, chain_vars):
        try:
            # Step 1: Fetch new emails
            emails = await self.email_reader.fetch_emails(
                since=chain_vars.get("since"),
                folder=chain_vars.get("folder", "INBOX")
            )
            
            processed_emails = []
            for email in emails:
                # Step 2: Clean and analyze email content
                analysis = await self.data_cleaner.clean_email_content(email["body"])
                
                # Step 3: Determine priority and actions
                is_urgent = (
                    "urgent" in email["subject"].lower() or
                    analysis["priority_score"] > 0.7 or
                    "urgent" in email.get("labels", [])
                )
                
                # Step 4: Apply labels based on content
                labels = set(email.get("labels", []))
                labels.update(analysis["extracted_entities"])
                await self.email_reader.apply_labels(email["id"], list(labels))
                
                # Step 5: Send notifications for urgent emails
                if is_urgent and chain_vars.get("notify_urgent", True):
                    # Notify on Slack
                    await self.slack.send_message(
                        channel=chain_vars.get("urgent_channel", "urgent-emails"),
                        message=f"Urgent Email: {email['subject']}\nFrom: {email['from']}"
                    )
                    
                    # Send additional notifications
                    if chain_vars.get("notify_team"):
                        await self.notification.send_notification(
                            recipient=chain_vars["notify_team"],
                            message=f"Urgent email received from {email['from']}"
                        )
                
                # Step 6: Archive if specified
                if chain_vars.get("archive_emails"):
                    folder = await self.drive.create_folder(
                        name=f"Emails/{datetime.now().strftime('%Y-%m')}"
                    )
                    
                    archived = await self.drive.save_email(
                        email_data=email,
                        folder_id=folder["folder_id"]
                    )
                    
                    # Move to archived folder in email
                    await self.email_reader.move_to_folder(
                        email_id=email["id"],
                        folder="Archived"
                    )
                
                processed_emails.append({
                    "email_id": email["id"],
                    "subject": email["subject"],
                    "is_urgent": is_urgent,
                    "labels": list(labels),
                    "priority_score": analysis["priority_score"]
                })
            
            return {
                "status": "success",
                "processed_count": len(processed_emails),
                "urgent_count": sum(1 for e in processed_emails if e["is_urgent"]),
                "processed_emails": processed_emails
            }
            
        except Exception as e:
            logging.error(f"Chain execution failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

# Tests
@pytest.mark.asyncio
async def test_basic_email_processing():
    chain = EmailProcessingChain()
    chain_vars = {
        "folder": "INBOX",
        "notify_urgent": True,
        "urgent_channel": "urgent-emails"
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"
    assert result["processed_count"] > 0
    assert "urgent_count" in result

@pytest.mark.asyncio
async def test_email_processing_with_archiving():
    chain = EmailProcessingChain()
    chain_vars = {
        "folder": "INBOX",
        "notify_urgent": True,
        "urgent_channel": "urgent-emails",
        "archive_emails": True,
        "notify_team": ["manager@company.com"]
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"
    assert result["processed_count"] > 0

@pytest.mark.asyncio
async def test_email_processing_with_team_notification():
    chain = EmailProcessingChain()
    chain_vars = {
        "folder": "INBOX",
        "notify_urgent": True,
        "notify_team": ["team@company.com"],
        "urgent_channel": "team-urgent"
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"

@pytest.mark.asyncio
async def test_error_handling():
    chain = EmailProcessingChain()
    # Test with invalid folder
    chain_vars = {
        "folder": None,
        "notify_urgent": True
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"  # Should still work with default INBOX

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__]) 