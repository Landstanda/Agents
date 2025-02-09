#!/usr/bin/env python3

from typing import Dict, Any, List
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from .gpt_handler import GPTHandler

logger = get_logger(__name__)

class ResponseGeneratorModule(BaseModule):
    """Module for generating email responses"""
    
    def __init__(self):
        self.gpt = GPTHandler()
        
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute response generation operations"""
        try:
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            if operation == 'generate_response':
                return self._generate_response(params)
            elif operation == 'review_response':
                return self._review_response(params)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except Exception as e:
            logger.error(f"Response generation error: {str(e)}")
            raise
            
    def _generate_response(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an appropriate email response"""
        email_data = params.get('email_data')
        classification = params.get('classification')
        business_context = params.get('business_context', {})
        
        if not email_data or not classification:
            raise ValueError("Email data and classification required")
            
        # Create prompt for GPT
        prompt = f"""Generate a professional email response based on this context:

Original Email:
Subject: {email_data.get('subject', '')}
From: {email_data.get('from', '')}
Body:
{email_data.get('body', '')}

Classification:
Categories: {', '.join(classification.get('categories', []))}
Priority: {classification.get('priority', 'Medium')}
Time Sensitivity: {classification.get('time_sensitivity', 'Normal')}

Business Context:
Company Name: {business_context.get('company_name', 'Our Company')}
Role: {business_context.get('role', 'Business Representative')}
Tone: {business_context.get('tone', 'Professional')}

Requirements:
1. Maintain a {business_context.get('tone', 'professional')} tone
2. Address all key points from the original email
3. Include clear next steps or actions if needed
4. Be concise but thorough
5. Include a proper greeting and signature

Format the response as JSON with this structure:
{{
    "subject": "Re: Original Subject",
    "body": "The complete email body",
    "next_steps": ["step1", "step2"],
    "follow_up_needed": true/false,
    "follow_up_date": "YYYY-MM-DD or null"
}}"""

        response = self.gpt.generate_response('system', prompt)
        try:
            import json
            response_data = json.loads(response)
            return {
                'email_id': email_data.get('message_id'),
                'response': response_data
            }
        except:
            logger.error("Failed to parse GPT response")
            return {
                'email_id': email_data.get('message_id'),
                'response': {
                    'subject': f"Re: {email_data.get('subject', '')}",
                    'body': "I apologize, but I am unable to generate a response at this time. Please try again later.",
                    'next_steps': [],
                    'follow_up_needed': False,
                    'follow_up_date': None
                }
            }
            
    def _review_response(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Review and suggest improvements for a draft response"""
        draft_response = params.get('draft_response')
        original_email = params.get('original_email')
        
        if not draft_response or not original_email:
            raise ValueError("Draft response and original email required")
            
        prompt = f"""Review this email response and suggest improvements:

Original Email:
{original_email}

Draft Response:
{draft_response}

Analyze the response for:
1. Tone and professionalism
2. Completeness (addressing all points)
3. Clarity and conciseness
4. Grammar and spelling
5. Appropriate next steps

Provide feedback in JSON format:
{{
    "is_appropriate": true/false,
    "suggestions": ["suggestion1", "suggestion2"],
    "improved_version": "Complete improved response if needed",
    "tone_analysis": "Analysis of the tone",
    "completeness_score": 0-100
}}"""

        response = self.gpt.generate_response('system', prompt)
        try:
            import json
            review_data = json.loads(response)
            return review_data
        except:
            logger.error("Failed to parse GPT review response")
            return {
                'is_appropriate': True,
                'suggestions': ["Unable to analyze response"],
                'improved_version': draft_response,
                'tone_analysis': "Analysis unavailable",
                'completeness_score': 0
            }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        if operation == 'generate_response':
            return bool(params.get('email_data')) and bool(params.get('classification'))
        elif operation == 'review_response':
            return bool(params.get('draft_response')) and bool(params.get('original_email'))
            
        return False

    @property
    def capabilities(self) -> List[str]:
        return ['response_generation', 'response_review', 'improvement_suggestions'] 