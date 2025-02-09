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
        
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email classification operations"""
        try:
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            if operation == 'classify_email':
                return self._classify_email(params)
            elif operation == 'determine_action':
                return self._determine_action(params)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except Exception as e:
            logger.error(f"Email classification error: {str(e)}")
            raise
            
    def _classify_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Classify an email's content and determine its category"""
        email_data = params.get('email_data')
        if not email_data:
            raise ValueError("Email data required")
            
        # Create prompt for GPT
        prompt = f"""Analyze this email and classify it:

Subject: {email_data.get('subject', '')}
From: {email_data.get('from', '')}
Body:
{email_data.get('body', '')}

Classify this email into one or more of these categories:
1. Customer Inquiry
2. Support Request
3. Business Proposal
4. Task/Action Required
5. FYI/Newsletter
6. Meeting/Schedule
7. Urgent/Important
8. Spam/Promotional

Also determine:
- Priority (High/Medium/Low)
- Response Required (Yes/No)
- Time Sensitivity (Urgent/Normal/None)

Format the response as JSON with this structure:
{{
    "categories": ["category1", "category2"],
    "priority": "High/Medium/Low",
    "needs_response": true/false,
    "time_sensitivity": "Urgent/Normal/None",
    "summary": "Brief summary of the email content",
    "key_points": ["point1", "point2"]
}}"""

        response = self.gpt.generate_response('system', prompt)
        try:
            import json
            classification = json.loads(response)
            return {
                'email_id': email_data.get('message_id'),
                'classification': classification
            }
        except:
            logger.error("Failed to parse GPT response")
            return {
                'email_id': email_data.get('message_id'),
                'classification': {
                    'categories': ['Unclassified'],
                    'priority': 'Medium',
                    'needs_response': False,
                    'time_sensitivity': 'Normal',
                    'summary': 'Failed to classify email',
                    'key_points': []
                }
            }
            
    def _determine_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Determine what actions should be taken for an email"""
        classification = params.get('classification')
        if not classification:
            raise ValueError("Classification data required")
            
        actions = []
        
        # Determine actions based on classification
        if classification.get('needs_response'):
            actions.append({
                'type': 'generate_response',
                'priority': classification.get('priority', 'Medium')
            })
            
        if 'Task/Action Required' in classification.get('categories', []):
            actions.append({
                'type': 'create_task',
                'priority': classification.get('priority', 'Medium')
            })
            
        if 'Meeting/Schedule' in classification.get('categories', []):
            actions.append({
                'type': 'schedule_meeting',
                'priority': classification.get('priority', 'Medium')
            })
            
        if classification.get('time_sensitivity') == 'Urgent':
            actions.append({
                'type': 'notify_team',
                'priority': 'High'
            })
            
        return {
            'actions': actions,
            'classification': classification
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