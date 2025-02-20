#!/usr/bin/env python3

from typing import Dict, Any, List, Optional, Union
from ..core.module_interface import BaseModule
import logging

logger = logging.getLogger(__name__)

class ConditionHandler(BaseModule):
    """Module for handling conditional logic and control flow in service execution"""
    
    def __init__(self):
        super().__init__()
        
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute condition evaluation
        
        Args:
            params: Dictionary containing:
                - conditions: List or Dict of condition rules to evaluate
                - context: Current execution context with variables to check
                - loop_check: Optional loop continuation check
        """
        try:
            context = params.get('context', {})
            
            # Handle loop continuation check
            if params.get('loop_check'):
                return await self._evaluate_loop_condition(params['loop_check'], context)
            
            # Validate conditions exist
            if 'conditions' not in params:
                raise ValueError("No conditions provided")
            
            # Handle regular conditions
            conditions = params['conditions']
            
            # For single condition with field check, validate field exists
            if isinstance(conditions, dict) and 'field' in conditions:
                field_value = self._get_field_value(conditions['field'], context)
                if field_value is None:
                    return {
                        'status': 'error',
                        'error': f"Invalid field path: {conditions['field']}"
                    }
            
            # For list of conditions, check each one
            if isinstance(conditions, list):
                for condition in conditions:
                    if isinstance(condition, dict) and 'field' in condition:
                        field_value = self._get_field_value(condition['field'], context)
                        if field_value is None:
                            return {
                                'status': 'error',
                                'error': f"Invalid field path: {condition['field']}"
                            }
            
            # If all validations pass, evaluate conditions
            return await self._evaluate_conditions(conditions, context)
            
        except Exception as e:
            logger.error(f"Condition evaluation error: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _evaluate_conditions(self, conditions: Union[List[Dict[str, Any]], Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate conditions against the current context"""
        try:
            # Handle dictionary format conditions (for AND/OR/direct conditions)
            if isinstance(conditions, dict):
                result = await self._evaluate_single_condition(conditions, context)
                return {
                    'status': 'success',
                    'result': result,
                    'next_step': conditions.get('then_step') if result else conditions.get('else_step')
                }
            
            # Handle list format conditions
            for condition in conditions:
                if not isinstance(condition, dict):
                    continue
                    
                if 'if' in condition:
                    result = await self._evaluate_single_condition(condition['if'], context)
                    
                    if result:
                        return {
                            'status': 'success',
                            'result': True,
                            'next_step': condition.get('then_step')
                        }
                    elif 'else_step' in condition:
                        return {
                            'status': 'success',
                            'result': False,
                            'next_step': condition['else_step']
                        }
                        
            # No conditions matched
            return {
                'status': 'success',
                'result': False,
                'next_step': None
            }
            
        except Exception as e:
            logger.error(f"Error evaluating conditions: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _evaluate_single_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate a single condition rule"""
        try:
            # Handle AND conditions
            if 'and' in condition:
                results = []
                for c in condition['and']:
                    result = await self._evaluate_single_condition(c, context)
                    results.append(result)
                return all(results)
                
            # Handle OR conditions
            if 'or' in condition:
                results = []
                for c in condition['or']:
                    result = await self._evaluate_single_condition(c, context)
                    results.append(result)
                return any(results)
                
            # Handle field comparisons
            if 'field' in condition:
                field_value = self._get_field_value(condition['field'], context)
                
                if field_value is None:
                    return False
                    
                if 'equals' in condition:
                    return field_value == condition['equals']
                    
                if 'contains' in condition:
                    return str(condition['contains']).lower() in str(field_value).lower()
                    
                if 'greater_than' in condition:
                    try:
                        return float(field_value) > float(condition['greater_than'])
                    except (ValueError, TypeError):
                        return False
                    
                if 'less_than' in condition:
                    try:
                        return float(field_value) < float(condition['less_than'])
                    except (ValueError, TypeError):
                        return False
                    
            # Handle existence checks
            if 'exists' in condition:
                path = condition['exists'].split('.')
                value = context
                for key in path:
                    if not isinstance(value, dict) or key not in value:
                        return False
                    value = value[key]
                return True
                
            raise ValueError(f"Invalid condition format: {condition}")
            
        except Exception as e:
            logger.error(f"Error evaluating single condition: {str(e)}")
            return False
            
    async def _evaluate_loop_condition(self, loop_check: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate loop continuation condition"""
        try:
            # Get the loop control field
            control_field = loop_check.get('while')
            if not control_field:
                raise ValueError("Loop check missing 'while' condition")
                
            # Check if we should continue looping
            should_continue = bool(context.get(control_field))
            
            return {
                'status': 'success',
                'continue_loop': should_continue,
                'next_step': loop_check.get('then_step', 1) if should_continue else loop_check.get('else_step', 'complete')
            }
            
        except Exception as e:
            logger.error(f"Error evaluating loop condition: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    def _get_field_value(self, field_path: str, context: Dict[str, Any]) -> Any:
        """Get a value from the context using dot notation for nested fields"""
        try:
            if not field_path:
                return None
                
            value = context
            path_parts = field_path.split('.')
            
            for key in path_parts[:-1]:
                if not isinstance(value, dict) or key not in value:
                    return None
                value = value[key]
                
            last_key = path_parts[-1]
            if not isinstance(value, dict) or last_key not in value:
                return None
                
            return value[last_key]
            
        except Exception:
            return None

    @property
    def capabilities(self) -> List[str]:
        return [
            'condition_evaluation',
            'loop_control',
            'flow_management'
        ] 