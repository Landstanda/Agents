import pytest
import logging
from unittest.mock import Mock, AsyncMock
from datetime import datetime

# Mock implementations of our modules
class MockGoogleAuthModule:
    async def authenticate(self):
        logging.info("Mock: Google Auth successful")
        return {"access_token": "mock_token_123"}

class MockGoogleDocsModule:
    async def create_document(self, title, content, template=None):
        logging.info(f"Mock: Created document '{title}'")
        return {
            "doc_id": "mock_doc_123",
            "url": "https://docs.google.com/mock_doc_123"
        }

class MockDocManagementModule:
    async def process_document(self, doc_id, permissions):
        logging.info(f"Mock: Processed document {doc_id} with {permissions} permissions")
        return {"status": "success"}

class MockSlackModule:
    async def share_document(self, channel, doc_link, message):
        logging.info(f"Mock: Shared {doc_link} to {channel}")
        return {"status": "sent", "timestamp": datetime.now().timestamp()}

class MockEmailSenderModule:
    async def send_notification(self, recipients, subject, body_template, attachments):
        logging.info(f"Mock: Sent email to {recipients}")
        return {"status": "sent", "message_id": "mock_email_123"}

# The actual chain implementation
class DocumentCreationChain:
    def __init__(self):
        self.google_auth = MockGoogleAuthModule()
        self.google_docs = MockGoogleDocsModule()
        self.doc_management = MockDocManagementModule()
        self.slack = MockSlackModule()
        self.email = MockEmailSenderModule()

    async def execute(self, chain_vars):
        try:
            # Step 1: Authenticate
            auth_result = await self.google_auth.authenticate()
            
            # Step 2: Create document
            doc_result = await self.google_docs.create_document(
                title=chain_vars["doc_title"],
                content=chain_vars["doc_content"],
                template=chain_vars.get("template_id")
            )
            
            # Step 3: Process document
            await self.doc_management.process_document(
                doc_id=doc_result["doc_id"],
                permissions="edit"
            )
            
            # Step 4: Share on Slack if requested
            if chain_vars.get("share_on_slack"):
                await self.slack.share_document(
                    channel=chain_vars["slack_channel"],
                    doc_link=doc_result["url"],
                    message=f"New document created: {chain_vars['doc_title']}"
                )
            
            # Step 5: Send email if requested
            if chain_vars.get("send_email"):
                await self.email.send_notification(
                    recipients=chain_vars["email_recipients"],
                    subject=f"New Document Shared: {chain_vars['doc_title']}",
                    body_template="doc_share_template",
                    attachments=doc_result["url"]
                )
            
            return {
                "status": "success",
                "doc_id": doc_result["doc_id"],
                "doc_url": doc_result["url"]
            }
            
        except Exception as e:
            logging.error(f"Chain execution failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

# Tests
@pytest.mark.asyncio
async def test_basic_document_creation():
    chain = DocumentCreationChain()
    chain_vars = {
        "doc_title": "Test Document",
        "doc_content": "Test content",
        "template_id": None,
        "share_on_slack": False,
        "send_email": False
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"
    assert "doc_id" in result
    assert "doc_url" in result

@pytest.mark.asyncio
async def test_document_with_slack_sharing():
    chain = DocumentCreationChain()
    chain_vars = {
        "doc_title": "Team Update",
        "doc_content": "Weekly updates",
        "template_id": "weekly_template",
        "share_on_slack": True,
        "slack_channel": "team-updates",
        "send_email": False
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"

@pytest.mark.asyncio
async def test_full_distribution():
    chain = DocumentCreationChain()
    chain_vars = {
        "doc_title": "Q4 Planning",
        "doc_content": "Quarterly planning details",
        "template_id": "quarterly_template",
        "share_on_slack": True,
        "slack_channel": "planning",
        "send_email": True,
        "email_recipients": ["team@company.com"]
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"

@pytest.mark.asyncio
async def test_error_handling():
    chain = DocumentCreationChain()
    # Test with missing required fields
    chain_vars = {
        "doc_title": "Test Document"
        # Missing doc_content
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "error"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__]) 