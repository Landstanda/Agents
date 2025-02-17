#!/usr/bin/env python3

from typing import Dict, Any, List, Optional
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
                - conditions: List of condition rules to evaluate
                - context: Current execution context with variables to check
                - loop_check: Optional loop continuation check
        """
        try:
            if not params.get('conditions'):
                raise ValueError("No conditions provided")
                
            context = params.get('context', {})
            
            # Handle loop continuation check
            if params.get('loop_check'):
                return await self._evaluate_loop_condition(params['loop_check'], context)
            
            # Handle regular conditions
            return await self._evaluate_conditions(params['conditions'], context)
            
        except Exception as e:
            logger.error(f"Condition evaluation error: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _evaluate_conditions(self, conditions: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a list of conditions against the current context"""
        try:
            for condition in conditions:
                if not condition.get('if'):
                    continue
                    
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
                return all(
                    await self._evaluate_single_condition(c, context)
                    for c in condition['and']
                )
                
            # Handle OR conditions
            if 'or' in condition:
                return any(
                    await self._evaluate_single_condition(c, context)
                    for c in condition['or']
                )
                
            # Handle field comparisons
            if 'field' in condition:
                field_value = self._get_field_value(condition['field'], context)
                
                if 'equals' in condition:
                    return field_value == condition['equals']
                    
                if 'contains' in condition:
                    return condition['contains'].lower() in str(field_value).lower()
                    
                if 'greater_than' in condition:
                    return float(field_value) > float(condition['greater_than'])
                    
                if 'less_than' in condition:
                    return float(field_value) < float(condition['less_than'])
                    
            # Handle existence checks
            if 'exists' in condition:
                return condition['exists'] in context
                
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
            value = context
            for key in field_path.split('.'):
                value = value.get(key, {})
            return value
        except Exception:
            return None

    @property
    def capabilities(self) -> List[str]:
        return [
            'condition_evaluation',
            'loop_control',
            'flow_management'
        ] 