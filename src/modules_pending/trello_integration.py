#!/usr/bin/env python3

from typing import Dict, Any, List
import os
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from ..utils.credential_manager import CredentialManager
import requests

logger = get_logger(__name__)

class TrelloModule(BaseModule):
    """Module for Trello integration and task management"""
    
    def __init__(self):
        self.credential_manager = CredentialManager()
        self.api_key = os.getenv('TRELLO_API_KEY')
        self.token = os.getenv('TRELLO_TOKEN')
        self.base_url = "https://api.trello.com/1"
        
        if not self.api_key or not self.token:
            raise ValueError("Trello API credentials not found in environment variables")
            
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Trello operations based on parameters"""
        try:
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            if operation == 'create_board':
                return self._create_board(params)
            elif operation == 'create_list':
                return self._create_list(params)
            elif operation == 'create_card':
                return self._create_card(params)
            elif operation == 'get_boards':
                return self._get_boards()
            elif operation == 'get_lists':
                return self._get_lists(params)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except Exception as e:
            logger.error(f"Trello operation error: {str(e)}")
            raise
            
    def _create_board(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Trello board"""
        name = params.get('name')
        if not name:
            raise ValueError("Board name required")
            
        url = f"{self.base_url}/boards"
        query = {
            'name': name,
            'key': self.api_key,
            'token': self.token,
            'defaultLists': 'false'
        }
        
        response = requests.post(url, params=query)
        response.raise_for_status()
        return response.json()
        
    def _create_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new list in a board"""
        board_id = params.get('board_id')
        name = params.get('name')
        
        if not board_id or not name:
            raise ValueError("Board ID and list name required")
            
        url = f"{self.base_url}/lists"
        query = {
            'name': name,
            'idBoard': board_id,
            'key': self.api_key,
            'token': self.token
        }
        
        response = requests.post(url, params=query)
        response.raise_for_status()
        return response.json()
        
    def _create_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new card in a list"""
        list_id = params.get('list_id')
        name = params.get('name')
        description = params.get('description', '')
        
        if not list_id or not name:
            raise ValueError("List ID and card name required")
            
        url = f"{self.base_url}/cards"
        query = {
            'name': name,
            'desc': description,
            'idList': list_id,
            'key': self.api_key,
            'token': self.token
        }
        
        response = requests.post(url, params=query)
        response.raise_for_status()
        return response.json()
        
    def _get_boards(self) -> Dict[str, Any]:
        """Get all boards for the authenticated user"""
        url = f"{self.base_url}/members/me/boards"
        query = {
            'key': self.api_key,
            'token': self.token
        }
        
        response = requests.get(url, params=query)
        response.raise_for_status()
        return {'boards': response.json()}
        
    def _get_lists(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get all lists in a board"""
        board_id = params.get('board_id')
        if not board_id:
            raise ValueError("Board ID required")
            
        url = f"{self.base_url}/boards/{board_id}/lists"
        query = {
            'key': self.api_key,
            'token': self.token
        }
        
        response = requests.get(url, params=query)
        response.raise_for_status()
        return {'lists': response.json()}

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        if operation == 'create_board':
            return bool(params.get('name'))
        elif operation == 'create_list':
            return bool(params.get('board_id') and params.get('name'))
        elif operation == 'create_card':
            return bool(params.get('list_id') and params.get('name'))
        elif operation == 'get_lists':
            return bool(params.get('board_id'))
        elif operation == 'get_boards':
            return True
            
        return False

    @property
    def capabilities(self) -> List[str]:
        return ['trello_management', 'task_tracking', 'board_management', 'card_management'] 