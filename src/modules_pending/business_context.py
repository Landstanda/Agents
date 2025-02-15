#!/usr/bin/env python3

import json
import os
from typing import Dict, Any, List
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger

logger = get_logger(__name__)

class BusinessContextModule(BaseModule):
    """Module for managing business context and plans"""
    
    def __init__(self):
        self.context_file = "business_context.json"
        self.context = self._load_context()
        
    def _load_context(self) -> Dict[str, Any]:
        """Load business context from file"""
        if os.path.exists(self.context_file):
            try:
                with open(self.context_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading context: {str(e)}")
                
        return {
            "business_name": "",
            "description": "",
            "goals": [],
            "plans": [],
            "current_phase": "",
            "key_features": [],
            "target_market": "",
            "timeline": {},
            "team": [],
            "resources": []
        }
        
    def _save_context(self):
        """Save business context to file"""
        try:
            with open(self.context_file, 'w') as f:
                json.dump(self.context, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving context: {str(e)}")
            
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute context operations"""
        try:
            operation = params.get('operation')
            if not operation:
                raise ValueError("No operation specified")
                
            if operation == 'update_context':
                return self._update_context(params)
            elif operation == 'get_context':
                return self._get_context(params)
            elif operation == 'import_context':
                return self._import_context(params)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except Exception as e:
            logger.error(f"Context operation error: {str(e)}")
            raise
            
    def _update_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update specific parts of the business context"""
        updates = params.get('updates', {})
        for key, value in updates.items():
            if key in self.context:
                self.context[key] = value
                
        self._save_context()
        return {'context': self.context}
        
    def _get_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get current business context"""
        section = params.get('section')
        if section:
            return {'context': {section: self.context.get(section)}}
        return {'context': self.context}
        
    def _import_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Import business context from text"""
        text = params.get('text', '')
        
        # Use GPT to parse the text into structured context
        from .gpt_handler import GPTHandler
        gpt = GPTHandler()
        
        prompt = f"""Parse this business context into a structured format:

{text}

Extract and organize the information into these categories:
- Business name
- Description
- Main goals
- Key features/products
- Target market
- Timeline/phases
- Team structure
- Required resources

Format the response as JSON with this structure:
{{
    "business_name": "string",
    "description": "string",
    "goals": ["goal1", "goal2", ...],
    "key_features": ["feature1", "feature2", ...],
    "target_market": "string",
    "timeline": {{"phase1": "description1", ...}},
    "team": ["role1", "role2", ...],
    "resources": ["resource1", "resource2", ...]
}}"""

        response = gpt.generate_response('system', prompt)
        try:
            import json
            parsed_context = json.loads(response)
            self.context.update(parsed_context)
            self._save_context()
            return {'context': self.context}
        except:
            logger.error("Failed to parse context")
            return {'error': 'Failed to parse business context'}

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        if not isinstance(params, dict):
            return False
            
        operation = params.get('operation')
        if not operation:
            return False
            
        if operation == 'update_context':
            return isinstance(params.get('updates'), dict)
        elif operation == 'get_context':
            return True
        elif operation == 'import_context':
            return bool(params.get('text'))
            
        return False

    @property
    def capabilities(self) -> List[str]:
        return ['context_management', 'business_planning', 'gpt_integration'] 