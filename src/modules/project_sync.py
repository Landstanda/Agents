#!/usr/bin/env python3

from typing import Dict, Any, List
import os
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from .trello_integration import TrelloModule
from .gpt_handler import GPTHandler

logger = get_logger(__name__)

class ProjectSyncModule(BaseModule):
    """Module for syncing project information between GPT and Trello"""
    
    def __init__(self):
        self.trello = TrelloModule()
        self.gpt = GPTHandler()
        
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute project sync operations"""
        try:
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            if operation == 'setup_project_board':
                return self._setup_project_board(params)
            elif operation == 'create_task_list':
                return self._create_task_list(params)
            elif operation == 'sync_project_info':
                return self._sync_project_info(params)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except Exception as e:
            logger.error(f"Project sync error: {str(e)}")
            raise
            
    def _setup_project_board(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set up a new project board with standard lists"""
        project_name = params.get('project_name', 'Business Project')
        context = params.get('context', '')
        
        # Use GPT to generate board structure based on project context
        prompt = f"""Based on this business project context:
{context}

Generate a Trello board structure with:
1. The main lists needed (e.g., Planning, In Progress, Done)
2. Key tasks for each list
3. Any important labels we should create

Format the response as JSON with this structure:
{{
    "lists": ["list1", "list2", ...],
    "tasks": {{
        "list1": [{"name": "task1", "description": "desc1"}, ...],
        "list2": [{"name": "task2", "description": "desc2"}, ...]
    }},
    "labels": [{"name": "label1", "color": "red"}, ...]
}}"""

        # Get GPT's suggestions
        response = self.gpt.generate_response('system', prompt)
        try:
            import json
            structure = json.loads(response)
        except:
            logger.error("Failed to parse GPT response as JSON")
            structure = {
                "lists": ["Planning", "In Progress", "Review", "Done"],
                "tasks": {
                    "Planning": [],
                    "In Progress": [],
                    "Review": [],
                    "Done": []
                },
                "labels": [
                    {"name": "High Priority", "color": "red"},
                    {"name": "In Review", "color": "yellow"},
                    {"name": "Completed", "color": "green"}
                ]
            }
        
        # Create the board
        board_result = self.trello.execute({
            'operation': 'create_board',
            'name': project_name
        })
        
        board_id = board_result['id']
        lists_created = {}
        
        # Create lists
        for list_name in structure['lists']:
            list_result = self.trello.execute({
                'operation': 'create_list',
                'board_id': board_id,
                'name': list_name
            })
            lists_created[list_name] = list_result['id']
            
        # Create tasks
        for list_name, tasks in structure['tasks'].items():
            if list_name in lists_created:
                for task in tasks:
                    self.trello.execute({
                        'operation': 'create_card',
                        'list_id': lists_created[list_name],
                        'name': task['name'],
                        'description': task.get('description', '')
                    })
        
        return {
            'board_id': board_id,
            'lists': lists_created,
            'structure': structure
        }
        
    def _create_task_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a task list based on project context"""
        board_id = params.get('board_id')
        list_name = params.get('list_name', 'New Tasks')
        context = params.get('context', '')
        
        # Use GPT to generate tasks based on context
        prompt = f"""Based on this business context:
{context}

Generate a list of specific, actionable tasks that need to be done.
Format each task with:
1. A clear, concise name
2. A detailed description
3. Any relevant notes or dependencies

Format the response as JSON with this structure:
{{
    "tasks": [
        {{"name": "task1", "description": "desc1", "notes": "note1"}},
        {{"name": "task2", "description": "desc2", "notes": "note2"}}
    ]
}}"""

        # Get GPT's suggestions
        response = self.gpt.generate_response('system', prompt)
        try:
            import json
            tasks = json.loads(response)['tasks']
        except:
            logger.error("Failed to parse GPT response as JSON")
            return {'error': 'Failed to generate tasks'}
            
        # Create a new list
        list_result = self.trello.execute({
            'operation': 'create_list',
            'board_id': board_id,
            'name': list_name
        })
        
        # Add tasks to the list
        created_tasks = []
        for task in tasks:
            description = f"{task['description']}\n\nNotes: {task.get('notes', 'None')}"
            task_result = self.trello.execute({
                'operation': 'create_card',
                'list_id': list_result['id'],
                'name': task['name'],
                'description': description
            })
            created_tasks.append(task_result)
            
        return {
            'list_id': list_result['id'],
            'tasks': created_tasks
        }
        
    def _sync_project_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sync project information between GPT and Trello"""
        # This method can be expanded to keep project info in sync
        pass

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        if operation == 'setup_project_board':
            return True  # All parameters are optional
        elif operation == 'create_task_list':
            return bool(params.get('board_id'))
        elif operation == 'sync_project_info':
            return True
            
        return False

    @property
    def capabilities(self) -> List[str]:
        return ['project_sync', 'task_management', 'gpt_integration'] 