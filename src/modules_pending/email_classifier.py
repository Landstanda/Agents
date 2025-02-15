#!/usr/bin/env python3

from typing import Dict, Any, List
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from .gpt_handler import GPTHandler

logger = get_logger(__name__)

class EmailClassifierModule(BaseModule):
    """Module for classifying emails and determining actions"""
    
    def __init__(self):
        self.gpt = GPTHandler()
        
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email classification operations"""
        try:
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            if operation == 'classify_email':
                return await self._classify_email(params)
            elif operation == 'determine_action':
                return await self._determine_action(params)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except Exception as e:
            logger.error(f"Email classification error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _classify_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Classify an email based on its content"""
        try:
            subject = params.get('subject')
            body = params.get('body')
            sender = params.get('sender')
            
            if not all([subject, body, sender]):
                raise ValueError("Subject, body, and sender required")
                
            # Use GPT to classify email
            prompt = f"""
            Please classify this email:
            From: {sender}
            Subject: {subject}
            Body: {body}
            
            Classify into one of these categories:
            1. Action Required
            2. Information Only
            3. Follow-up Needed
            4. Urgent
            5. Spam/Marketing
            
            Also provide:
            - Priority (1-5)
            - Key topics (comma separated)
            - Suggested next actions
            """
            
            response = await self.gpt.generate_response(prompt, {})
            
            # Parse GPT response
            lines = response.strip().split('\n')
            category = next((line for line in lines if any(cat in line.lower() for cat in ['action required', 'information only', 'follow-up needed', 'urgent', 'spam'])), 'Information Only')
            priority = next((int(line[line.find(':')+1].strip()) for line in lines if 'priority' in line.lower()), 3)
            topics = next((line[line.find(':')+1].strip() for line in lines if 'topics' in line.lower()), '')
            actions = next((line[line.find(':')+1].strip() for line in lines if 'actions' in line.lower()), '')
            
            return {
                'success': True,
                'category': category,
                'priority': priority,
                'topics': topics.split(','),
                'suggested_actions': actions.split(';') if ';' in actions else [actions]
            }
            
        except Exception as e:
            logger.error(f"Error classifying email: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
            
    async def _determine_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Determine appropriate actions for an email"""
        try:
            category = params.get('category')
            priority = params.get('priority')
            topics = params.get('topics', [])
            
            if not all([category, priority]):
                raise ValueError("Category and priority required")
                
            # Use GPT to suggest actions
            prompt = f"""
            Based on this email classification:
            Category: {category}
            Priority: {priority}
            Topics: {', '.join(topics)}
            
            Suggest specific actions to take, considering:
            1. Required responses
            2. Task creation
            3. Calendar events
            4. Document updates
            5. Team notifications
            """
            
            response = await self.gpt.generate_response(prompt, {})
            
            # Parse GPT response into action items
            actions = [
                line.strip()[2:] for line in response.split('\n')
                if line.strip().startswith('-')
            ]
            
            return {
                'success': True,
                'actions': actions,
                'requires_response': 'response' in response.lower(),
                'create_task': 'task' in response.lower(),
                'schedule_event': 'schedule' in response.lower() or 'calendar' in response.lower()
            }
            
        except Exception as e:
            logger.error(f"Error determining actions: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        if operation == 'classify_email':
            return bool(params.get('email_data'))
        elif operation == 'determine_action':
            return bool(params.get('classification'))
            
        return False

    @property
    def capabilities(self) -> List[str]:
        return ['email_classification', 'action_determination', 'priority_assessment'] 