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
    """Test suite for EmailComposer with real GPT and Gmail integration"""

    @pytest.mark.asyncio
    async def test_product_inquiry_reply(self, email_composer, mock_customer_email):
        """
        Test composing and sending a reply to a product inquiry.
        Uses real GPT for content generation and real Gmail for sending.
        """
        print("\n=== Testing Product Inquiry Reply ===")
        
        # Prepare reply parameters
        reply_params = {
            'to': ['11jeff11@gmail.com'],  # The actual recipient
            'subject': f"Re: {mock_customer_email['subject']}",
            'purpose': 'Respond to product availability inquiry',
            'original_email': mock_customer_email['content'],
            'response_type': 'product_inquiry',
            'context': {
                'product_status': 'in stock',
                'shipping_time': '3 days',
                'product_details': {
                    'name': 'Luxury Face Cream',
                    'sizes': ['30ml', '50ml', '100ml'],
                    'prices': {'30ml': '$29.99', '50ml': '$49.99', '100ml': '$89.99'}
                }
            },
            'key_points': [
                'Confirm product is in stock',
                'Specify 3-day shipping timeframe',
                'List available sizes and prices',
                'Express appreciation for interest'
            ],
            'tone': 'professional and helpful'
        }

        try:
            # Initialize services
            await email_composer._initialize_service()
            
            # Step 1: Generate content using GPT
            print("\nGenerating email content...")
            content_result = await email_composer.execute({
                'action': 'generate_content',
                **reply_params
            })
            
            assert content_result['status'] == 'success', f"Content generation failed: {content_result.get('error')}"
            print("\nGenerated content:")
            print(content_result['content'])
            
            # Step 2: Prepare the email with the generated content
            print("\nPreparing email...")
            email_result = await email_composer.execute({
                'action': 'prepare',
                **reply_params,
                'content': content_result['content']
            })
            
            assert email_result['status'] == 'success', f"Email preparation failed: {email_result.get('error')}"
            print(f"\nEmail prepared with draft ID: {email_result['draft_id']}")
            
            # Step 3: Send the email
            print("\nSending email...")
            send_result = await email_composer.execute({
                'action': 'send',
                'draft_id': email_result['draft_id']
            })
            
            assert send_result['status'] == 'success', f"Email sending failed: {send_result.get('error')}"
            print(f"\nEmail sent successfully with message ID: {send_result.get('message_id')}")
            
            # Verify the results
            assert send_result.get('sent') == True, "Email was not sent"
            assert send_result.get('thread_id') is not None, "No thread ID returned"
            assert send_result.get('timestamp') is not None, "No timestamp returned"
            
        except Exception as e:
            pytest.fail(f"Test failed with error: {str(e)}")

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 