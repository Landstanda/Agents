#!/usr/bin/env python3

import os
from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger
from dotenv import load_dotenv
import json

logger = get_logger(__name__)

class GPTHandler(BaseModule):
    """Module for handling GPT API interactions and response processing"""
    
    def __init__(self):
        super().__init__()
        load_dotenv()
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute GPT operations
        
        Args:
            params: Dictionary containing:
                - prompt: The complete, formatted prompt
                - response_format: Optional format specification ('json' or 'text')
                - validation_schema: Optional schema for validating responses
                - model: Optional model to use (defaults to gpt-4)
                - temperature: Optional temperature setting (defaults to 0.1)
                - max_tokens: Optional max tokens (defaults to 500)
        """
        try:
            prompt = params.get('prompt')
            if not prompt:
                raise ValueError("Prompt is required")
            
            # Log the prompt for debugging
            logger.info("=== GPT Prompt ===")
            logger.info(prompt)
            logger.info("=================")
            
            # Prepare API call parameters
            messages = [{"role": "user", "content": prompt}]
            
            # Add system message if provided
            if params.get('system_message'):
                messages.insert(0, {"role": "system", "content": params['system_message']})
            
            # If JSON response is required, modify the system message
            if params.get('response_format') == 'json':
                json_system_message = """You are a JSON response system. Follow these rules strictly:
1. ONLY output valid JSON objects
2. Do not include any explanatory text
3. Do not use markdown formatting
4. Ensure all required fields are present
5. Use the exact field names specified
6. Format numbers as proper JSON numbers (not strings)
7. Never include comments or explanations
8. No line breaks in the output
9. No whitespace before or after the JSON"""
                
                if params.get('system_message'):
                    messages[0]["content"] = f"{json_system_message}\n\n{messages[0]['content']}"
                else:
                    messages.insert(0, {"role": "system", "content": json_system_message})
            
            completion_params = {
                'model': params.get('model', 'gpt-4'),
                'messages': messages,
                'temperature': params.get('temperature', 0.1),
                'max_tokens': params.get('max_tokens', 500)
            }
            
            # Get response from GPT
            response = await self.client.chat.completions.create(**completion_params)
            
            if not response.choices:
                raise ValueError("No response generated")
            
            content = response.choices[0].message.content.strip()
            
            # Log raw response for debugging
            logger.info("=== Raw GPT Response ===")
            logger.info(content)
            logger.info("=======================")
            
            # Process response based on format
            if params.get('response_format') == 'json':
                try:
                    # Clean up the response
                    content = content.replace('```json\n', '').replace('\n```', '')
                    content = content.strip('`').strip()
                    content = content.replace('\n', '').replace('\r', '')
                    
                    # Parse and validate JSON
                    parsed_json = json.loads(content)
                    
                    # Apply validation schema if provided
                    if params.get('validation_schema'):
                        self._validate_response(parsed_json, params['validation_schema'])
                    
                    return {
                        'status': 'success',
                        'content': json.dumps(parsed_json)
                    }
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON response: {str(e)}\nContent: {content}")
                    return {
                        'status': 'error',
                        'error': f"Invalid JSON response: {str(e)}"
                    }
            else:
                # Return text response as is
                return {
                    'status': 'success',
                    'content': content
                }
                
        except Exception as e:
            logger.error(f"Error in GPT operation: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    def _validate_response(self, response: Dict[str, Any], schema: Dict[str, Any]) -> None:
        """Validate response against a schema"""
        if 'required_fields' in schema:
            missing_fields = [
                field for field in schema['required_fields']
                if field not in response
            ]
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
        
        if 'field_types' in schema:
            for field, expected_type in schema['field_types'].items():
                if field in response:
                    value = response[field]
                    if expected_type == 'number':
                        if not isinstance(value, (int, float)):
                            response[field] = float(value)
                    elif not isinstance(value, eval(expected_type)):
                        raise ValueError(f"Invalid type for {field}: expected {expected_type}")
        
        if 'value_ranges' in schema:
            for field, (min_val, max_val) in schema['value_ranges'].items():
                if field in response:
                    value = float(response[field])
                    if not min_val <= value <= max_val:
                        raise ValueError(f"Value for {field} must be between {min_val} and {max_val}")

    @property
    def capabilities(self) -> List[str]:
        return [
            'gpt_interaction',
            'response_validation',
            'error_handling'
        ] 