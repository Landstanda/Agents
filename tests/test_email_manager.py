import pytest
import os
from datetime import datetime
from src.modules.email_manager import EmailManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@pytest.fixture
def email_manager():
    """Create an EmailManager instance"""
    return EmailManager()

@pytest.fixture
def sample_emails():
    """Create sample emails for testing classification"""
    return {
        "urgent_support": {
            "from": "customer@company.com",
            "subject": "URGENT: System Down - Cannot Process Orders",
            "content": """
Dear Support Team,

Our order processing system has been down for the last hour and we're losing sales.
This is severely impacting our business operations.
Please help resolve this ASAP.

Best regards,
John Smith
Operations Manager
"""
        },
        "product_inquiry": {
            "from": "potential_customer@email.com",
            "subject": "Question about Enterprise Package Pricing",
            "content": """
Hello Sales Team,

I'm interested in your enterprise software package for my company.
We have about 500 users and would like to know:
1. Pricing for this scale
2. Implementation timeline
3. Available support packages

Looking forward to your response.

Best regards,
Sarah Wilson
Technology Director
"""
        },
        "feedback": {
            "from": "user@startup.com",
            "subject": "Feature Suggestion - Dashboard Enhancement",
            "content": """
Hi Product Team,

I've been using your software for 6 months and love it.
I have a suggestion that could make the dashboard even better:
Adding customizable widgets would help us track our most important metrics.

Thanks for considering this!

Best,
Mike Johnson
"""
        },
        "newsletter": {
            "from": "marketing@techjournal.com",
            "subject": "Tech Weekly Newsletter - Latest Industry Updates",
            "content": """
Your Weekly Tech Digest

Top Stories:
1. AI Advances in 2024
2. New Cloud Computing Trends
3. Cybersecurity Best Practices

Click here to read more...

Unsubscribe | Privacy Policy
"""
        }
    }

class TestEmailManager:
    """Test suite for EmailManager with real GPT integration"""

    @pytest.mark.asyncio
    async def test_email_classification(self, email_manager, sample_emails):
        """
        Test email classification functionality.
        Verifies:
        - Correct category identification
        - Priority assignment
        - Action determination
        - Folder movement
        """
        print("\n=== Testing Email Classification ===")
        
        # Initialize service
        await email_manager._initialize_service()
        
        # Test classification for each sample email
        for email_type, email_content in sample_emails.items():
            print(f"\nClassifying {email_type} email...")
            
            # Create test email in Gmail (you might need to implement this)
            # For now, we'll assume we have an email ID
            email_id = "test_email_id"  # This should be a real email ID
            
            # Classify the email
            classification_result = await email_manager.execute({
                'action': 'classify_email',
                'email_id': email_id
            })
            
            assert classification_result['status'] == 'success', \
                f"Classification failed: {classification_result.get('error')}"
            
            classification = classification_result['classification']
            print("\nClassification results:")
            print(f"Category: {classification['category']}")
            print(f"Priority: {classification['priority']}")
            print(f"Confidence: {classification['confidence']}")
            print(f"Actions: {classification['actions']}")
            print(f"Requires Response: {classification['requires_response']}")
            print(f"Reasoning: {classification['reasoning']}")
            
            # Process the classification
            process_result = await email_manager.execute({
                'action': 'process_classification',
                'classification': classification
            })
            
            assert process_result['status'] == 'success', \
                f"Processing failed: {process_result.get('error')}"
            
            print("\nProcessing results:")
            print(f"Actions performed: {process_result['actions_performed']}")
            print(f"Final folder: {process_result['folder']}")
            
            # Verify classification makes sense
            if email_type == 'urgent_support':
                assert classification['priority'] in ['immediate', 'high'], \
                    "Urgent support should have high priority"
                assert classification['requires_response'] == True, \
                    "Urgent support should require response"
                
            elif email_type == 'product_inquiry':
                assert 'sales_opportunity' in classification['category'], \
                    "Sales inquiry not properly categorized"
                assert classification['auto_response_possible'] == True, \
                    "Standard inquiry should allow auto-response"
                
            elif email_type == 'feedback':
                assert 'feedback' in classification['category'], \
                    "Feedback not properly categorized"
                
            elif email_type == 'newsletter':
                assert 'newsletter' in classification['category'], \
                    "Newsletter not properly categorized"
                assert classification['priority'] == 'low', \
                    "Newsletter should have low priority"

    @pytest.mark.asyncio
    async def test_real_email_classification(self, email_manager):
        """
        Test classification of a single email in Gmail.
        Tests:
        1. Email content retrieval
        2. GPT classification response format
        3. Label application based on classification
        """
        print("\n=== Testing Email Classification ===")
        
        # Initialize service
        await email_manager._initialize_service()
        
        # Get the most recent unread email
        print("\nFetching most recent unread email...")
        messages = email_manager.service.users().messages().list(
            userId='me',
            q='is:unread',
            maxResults=1
        ).execute()
        
        if not messages.get('messages'):
            pytest.fail("No unread messages found. Please ensure a test email was sent.")
        
        # Get the email details
        email_id = messages['messages'][0]['id']
        email_data = email_manager.service.users().messages().get(
            userId='me',
            id=email_id,
            format='full'
        ).execute()
        
        # Extract and display email details
        headers = email_data['payload']['headers']
        subject = next(h['value'] for h in headers if h['name'].lower() == 'subject')
        sender = next(h['value'] for h in headers if h['name'].lower() == 'from')
        
        print("\nEmail Details:")
        print(f"From: {sender}")
        print(f"Subject: {subject}")
        
        # Step 1: Test email classification
        print("\nClassifying email...")
        classification_result = await email_manager.execute({
            'action': 'classify_email',
            'email_id': email_id
        })
        
        # Verify classification response format
        assert classification_result['status'] == 'success', \
            f"Classification failed: {classification_result.get('error')}"
            
        classification = classification_result['classification']
        print("\nClassification Results:")
        print(f"Category: {classification['category']}")
        print(f"Confidence: {classification['confidence']}")
        print(f"Summary: {classification['summary']}")
        
        # Verify classification has required fields
        assert 'category' in classification, "Classification missing 'category'"
        assert 'confidence' in classification, "Classification missing 'confidence'"
        assert 'summary' in classification, "Classification missing 'summary'"
        assert isinstance(classification['confidence'], float), "Confidence should be a float"
        assert 0 <= classification['confidence'] <= 1, "Confidence should be between 0 and 1"
        
        # Step 2: Test label application
        print("\nApplying label based on classification...")
        process_result = await email_manager.execute({
            'action': 'process_classification',
            'classification': {
                **classification,
                'email_id': email_id
            }
        })
        
        # Verify label application
        assert process_result['status'] == 'success', \
            f"Label application failed: {process_result.get('error')}"
        
        print(f"Label applied: {process_result['label_added']}")
        
        # Verify label matches category
        category = email_manager.classification_schema['categories'][classification['category']]
        assert process_result['label_added'] == category['folder'], \
            f"Applied label '{process_result['label_added']}' doesn't match category folder '{category['folder']}'"

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 