import pytest
import logging
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# Mock implementations
class MockBusinessContextModule:
    async def get_context(self, context_type, identifier=None):
        logging.info(f"Mock: Getting {context_type} context")
        return {
            "templates": {
                "client_update": "templates/client_update.md",
                "team_update": "templates/team_update.md"
            },
            "tone": "professional",
            "key_points": ["progress", "timeline", "next steps"]
        }

class MockDataCleanerModule:
    async def format_message(self, content, tone="professional"):
        logging.info(f"Mock: Formatting message with {tone} tone")
        return {
            "formatted_text": content,
            "word_count": len(content.split()),
            "tone_score": 0.9
        }
    
    async def validate_content(self, content, requirements):
        logging.info("Mock: Validating content")
        return {
            "valid": True,
            "missing_elements": [],
            "suggestions": []
        }

class MockEmailSenderModule:
    async def send_email(self, recipients, subject, content, attachments=None):
        logging.info(f"Mock: Sending email to {recipients}")
        return {
            "status": "sent",
            "message_id": "email_123",
            "timestamp": datetime.now()
        }

class MockSlackModule:
    async def send_message(self, channel, message, blocks=None):
        logging.info(f"Mock: Sending Slack message to {channel}")
        return {
            "status": "sent",
            "timestamp": datetime.now().timestamp()
        }
    
    async def upload_file(self, channel, file_content, title):
        logging.info(f"Mock: Uploading file to {channel}")
        return {"file_id": "file_123"}

class MockTrelloModule:
    async def create_card(self, list_id, title, description):
        logging.info(f"Mock: Creating Trello card '{title}'")
        return {
            "card_id": "card_123",
            "url": "https://trello.com/card_123"
        }
    
    async def add_comment(self, card_id, comment):
        logging.info(f"Mock: Adding comment to card {card_id}")
        return {"comment_id": "comment_123"}

class MockNotificationModule:
    async def send_notification(self, recipient, message, channel="all"):
        logging.info(f"Mock: Sending notification to {recipient}")
        return {"status": "sent"}

# The chain implementation
class BusinessCommunicationChain:
    def __init__(self):
        self.business_context = MockBusinessContextModule()
        self.data_cleaner = MockDataCleanerModule()
        self.email = MockEmailSenderModule()
        self.slack = MockSlackModule()
        self.trello = MockTrelloModule()
        self.notification = MockNotificationModule()

    async def execute(self, chain_vars):
        try:
            # Step 1: Get communication context
            context = await self.business_context.get_context(
                context_type=chain_vars["communication_type"]
            )
            
            # Step 2: Format and validate content
            formatted = await self.data_cleaner.format_message(
                content=chain_vars["content"],
                tone=chain_vars.get("tone", context["tone"])
            )
            
            validation = await self.data_cleaner.validate_content(
                content=formatted["formatted_text"],
                requirements=context["key_points"]
            )
            
            if not validation["valid"]:
                return {
                    "status": "validation_failed",
                    "missing_elements": validation["missing_elements"],
                    "suggestions": validation["suggestions"]
                }
            
            results = {
                "status": "success",
                "channels": []
            }
            
            # Step 3: Send email if requested
            if chain_vars.get("send_email"):
                email_result = await self.email.send_email(
                    recipients=chain_vars["email_recipients"],
                    subject=chain_vars["subject"],
                    content=formatted["formatted_text"],
                    attachments=chain_vars.get("attachments")
                )
                results["channels"].append({
                    "type": "email",
                    "status": email_result["status"],
                    "recipients": chain_vars["email_recipients"]
                })
            
            # Step 4: Send Slack message if requested
            if chain_vars.get("send_slack"):
                slack_result = await self.slack.send_message(
                    channel=chain_vars["slack_channel"],
                    message=formatted["formatted_text"]
                )
                
                # Upload attachments if any
                if chain_vars.get("attachments"):
                    for attachment in chain_vars["attachments"]:
                        await self.slack.upload_file(
                            channel=chain_vars["slack_channel"],
                            file_content=attachment["content"],
                            title=attachment["name"]
                        )
                
                results["channels"].append({
                    "type": "slack",
                    "status": slack_result["status"],
                    "channel": chain_vars["slack_channel"]
                })
            
            # Step 5: Create Trello card if requested
            if chain_vars.get("create_trello_card"):
                card = await self.trello.create_card(
                    list_id=chain_vars["trello_list_id"],
                    title=chain_vars["subject"],
                    description=formatted["formatted_text"]
                )
                
                if chain_vars.get("trello_comment"):
                    await self.trello.add_comment(
                        card_id=card["card_id"],
                        comment=chain_vars["trello_comment"]
                    )
                
                results["channels"].append({
                    "type": "trello",
                    "card_url": card["url"]
                })
            
            # Step 6: Send additional notifications if specified
            if chain_vars.get("notify_additional"):
                for recipient in chain_vars["notify_additional"]:
                    await self.notification.send_notification(
                        recipient=recipient,
                        message=f"New communication: {chain_vars['subject']}"
                    )
                
                results["channels"].append({
                    "type": "notification",
                    "recipients": chain_vars["notify_additional"]
                })
            
            return results
            
        except Exception as e:
            logging.error(f"Chain execution failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

# Tests
@pytest.mark.asyncio
async def test_basic_communication():
    chain = BusinessCommunicationChain()
    chain_vars = {
        "communication_type": "client_update",
        "subject": "Project Update",
        "content": "Progress update on the project...",
        "send_email": True,
        "email_recipients": ["client@company.com"],
        "send_slack": True,
        "slack_channel": "client-updates"
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"
    assert len(result["channels"]) == 2

@pytest.mark.asyncio
async def test_full_communication_suite():
    chain = BusinessCommunicationChain()
    chain_vars = {
        "communication_type": "team_update",
        "subject": "Sprint Review",
        "content": "Sprint review summary and next steps...",
        "send_email": True,
        "email_recipients": ["team@company.com"],
        "send_slack": True,
        "slack_channel": "team-updates",
        "create_trello_card": True,
        "trello_list_id": "list_123",
        "trello_comment": "Please review and add your feedback",
        "notify_additional": ["manager@company.com"],
        "attachments": [{
            "name": "sprint_metrics.pdf",
            "content": "pdf_content_here"
        }]
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"
    assert len(result["channels"]) == 4

@pytest.mark.asyncio
async def test_validation_failure():
    chain = BusinessCommunicationChain()
    chain_vars = {
        "communication_type": "client_update",
        "subject": "Incomplete Update",
        "content": "Just a brief note...",  # Missing required elements
        "send_email": True,
        "email_recipients": ["client@company.com"]
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "validation_failed"
    assert "missing_elements" in result

@pytest.mark.asyncio
async def test_error_handling():
    chain = BusinessCommunicationChain()
    # Test with missing required fields
    chain_vars = {
        "subject": "Test Communication"
        # Missing communication_type and content
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "error"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__]) 