from typing import Dict, Any, List
import os
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from ..utils.credential_manager import CredentialManager
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = get_logger(__name__)

class SlackModule(BaseModule):
    """Module for Slack integration and communication"""
    
    def __init__(self):
        self.credential_manager = CredentialManager()
        self.client = None
        self.service_name = 'slack'
        
    def initialize_client(self) -> None:
        """Initialize Slack client with token"""
        if not self.client:
            token = os.getenv('SLACK_BOT_TOKEN')
            if not token:
                raise ValueError("SLACK_BOT_TOKEN not set in environment")
            self.client = WebClient(token=token)
            
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Slack operations based on parameters"""
        try:
            self.initialize_client()
            
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            if operation == 'send_message':
                return self._send_message(params)
            elif operation == 'list_channels':
                return self._list_channels()
            elif operation == 'create_channel':
                return self._create_channel(params)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except SlackApiError as e:
            logger.error(f"Slack API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Slack operation error: {str(e)}")
            raise
            
    def _send_message(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to a Slack channel"""
        channel = params.get('channel')
        text = params.get('text')
        
        if not channel or not text:
            raise ValueError("Channel and text required for send_message")
            
        response = self.client.chat_postMessage(
            channel=channel,
            text=text
        )
        
        return {
            'message_ts': response['ts'],
            'channel': response['channel'],
            **params
        }
        
    def _list_channels(self) -> Dict[str, Any]:
        """List all accessible channels"""
        response = self.client.conversations_list()
        return {
            'channels': response['channels']
        }
        
    def _create_channel(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Slack channel"""
        name = params.get('name')
        if not name:
            raise ValueError("Channel name required for create_channel")
            
        response = self.client.conversations_create(
            name=name,
            is_private=params.get('is_private', False)
        )
        
        return {
            'channel_id': response['channel']['id'],
            'channel_name': response['channel']['name'],
            **params
        }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        if operation == 'send_message':
            return bool(params.get('channel') and params.get('text'))
        elif operation == 'create_channel':
            return bool(params.get('name'))
        elif operation == 'list_channels':
            return True
            
        return False

    @property
    def capabilities(self) -> List[str]:
        return ['slack_messaging', 'channel_management', 'team_communication'] 