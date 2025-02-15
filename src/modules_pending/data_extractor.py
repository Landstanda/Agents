from typing import Dict, Any, List
import re
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger

logger = get_logger(__name__)

class DataExtractorModule(BaseModule):
    """Module for extracting and processing data"""
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and extract specific data from input
        
        Expected params:
        - data: Dict[str, Any] - Input data to process
        - patterns: Dict[str, str] - Regex patterns for extraction
        - filters: Dict[str, Any] - Optional filtering criteria
        
        Returns:
        - extracted_data: Dict[str, Any] - Processed results
        """
        try:
            input_data = params['data']
            patterns = params.get('patterns', {})
            filters = params.get('filters', {})
            
            results = {}
            
            for key, data in input_data.items():
                extracted = {}
                
                for pattern_key, pattern in patterns.items():
                    if isinstance(data, str):
                        matches = re.findall(pattern, data)
                        extracted[pattern_key] = matches
                    elif isinstance(data, dict):
                        extracted[pattern_key] = {
                            k: re.findall(pattern, str(v))
                            for k, v in data.items()
                        }
                
                # Apply filters
                if filters:
                    extracted = self._apply_filters(extracted, filters)
                
                results[key] = extracted
            
            return {'extracted_data': results}
            
        except Exception as e:
            logger.error(f"Data extraction error: {str(e)}")
            raise
    
    def _apply_filters(self, data: Dict, filters: Dict) -> Dict:
        """Apply filtering criteria to extracted data"""
        filtered_data = {}
        for key, value in data.items():
            if key in filters:
                if callable(filters[key]):
                    filtered_data[key] = filters[key](value)
                else:
                    filtered_data[key] = value
        return filtered_data
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        return (
            isinstance(params.get('data'), dict) and
            isinstance(params.get('patterns', {}), dict)
        )
    
    @property
    def capabilities(self) -> List[str]:
        return ['data_extraction', 'text_processing', 'filtering'] 