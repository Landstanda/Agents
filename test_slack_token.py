#!/usr/bin/env python3

import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_token():
    """Simple test to verify Slack token"""
    token = os.getenv('SLACK_BOT_TOKEN')
    if not token:
        print("ERROR: No token found in environment!")
        return
        
    print(f"Token found: {token[:20]}... (length: {len(token)})")
    
    try:
        # Initialize client
        print("\nInitializing Slack client...")
        client = WebClient(token=token)
        
        # Try a simple API call
        print("Testing connection...")
        response = client.auth_test()
        
        print("\nConnection successful!")
        print(f"Connected as: {response['bot_id']}")
        print(f"Connected to workspace: {response['team']}")
        print(f"Bot name: {response['user']}")
        
    except SlackApiError as e:
        print(f"\nError: {e.response['error']}")
        if 'response' in e.__dict__:
            print(f"Full error: {e.response}")
        print("\nPossible issues:")
        print("1. Token might not be active yet")
        print("2. Bot might not have required scopes")
        print("3. App might need to be reinstalled")
        
if __name__ == "__main__":
    test_token() 