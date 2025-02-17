import pytest
import os
from datetime import datetime
from src.modules.email_composer import EmailComposer
from src.modules.gpt_handler import GPTHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@pytest.fixture
def email_composer():
    """Create an EmailComposer instance"""
    return EmailComposer()

@pytest.fixture
def mock_customer_email():
    """Create a mock customer inquiry email"""
    return {
        'from': 'customer@example.com',
        'subject': 'Product Availability Inquiry - Luxury Face Cream',
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'content': """
Dear Support Team,

I'm interested in purchasing your Luxury Face Cream that I saw advertised on your website.
Could you please let me know if it's currently in stock and how long it would take to ship?
Also, what size options are available?

Thank you for your help!

Best regards,
Sarah Johnson
"""
    }

class TestEmailComposer:
    """Test suite for EmailComposer"""

    @pytest.mark.asyncio
    async def test_new_email_composition(self, email_composer):
        """Test composing a new email"""
        print("\n=== Testing New Email Composition ===")
        
        # Test parameters
        params = {
            'subject': 'Project Update Meeting',
            'purpose': 'Schedule a team meeting to discuss project progress',
            'to': ['team@company.com'],
            'context': 'We need to review Q1 goals and plan for Q2',
            'tone': 'professional'
        }
        
        # Generate email content
        result = await email_composer.execute({
            'action': 'compose',
            'params': params
        })
        
        # Verify response
        assert result['status'] == 'success', \
            f"Email composition failed: {result.get('error')}"
            
        print("\nGPT Response Details:")
        print(f"Subject: {result['subject']}")
        print("\nGenerated Email Content:")
        print(result['content'])
        print("\nRaw GPT Response:")
        print(result['raw_response'])
        
        # Basic content checks
        assert 'Project Update Meeting' in result['subject'], "Subject not properly set"
        assert 'team' in result['content'].lower(), "Recipient reference not found"
        assert len(result['content'].split('\n')) > 3, "Email too short"
        
    @pytest.mark.asyncio
    async def test_email_reply(self, email_composer):
        """Test composing an email reply"""
        print("\n=== Testing Email Reply ===")
        
        # Original email
        original_email = """
Dear Team,

I hope this email finds you well. I wanted to follow up on the project timeline 
discussion from last week. Could we schedule a meeting to review the current 
status and address any potential delays?

Best regards,
John"""
        
        # Test parameters
        params = {
            'original_email': original_email,
            'response_type': 'agreement',
            'key_points': ['Confirm meeting', 'Suggest time slots', 'Mention prepared status update'],
            'context': 'We have a status report ready to present',
            'tone': 'professional'
        }
        
        # Generate reply
        result = await email_composer.execute({
            'action': 'compose',
            'params': params
        })
        
        # Verify response
        assert result['status'] == 'success', \
            f"Reply composition failed: {result.get('error')}"
            
        print("\nGPT Response Details:")
        print(f"Subject: {result['subject']}")
        print("\nGenerated Email Content:")
        print(result['content'])
        print("\nRaw GPT Response:")
        print(result['raw_response'])
        
        # Basic content checks
        assert result['subject'].startswith('Re:'), "Reply subject should start with 'Re:'"
        assert 'Dear' in result['content'], "No greeting found"
        assert 'meeting' in result['content'].lower(), "No meeting reference found"
        assert 'status' in result['content'].lower(), "No status reference found"
        assert len(result['content'].split('\n')) > 3, "Reply too short"

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 