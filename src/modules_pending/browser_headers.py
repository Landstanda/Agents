from typing import Dict, Any, List
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger

logger = get_logger(__name__)

class BrowserHeadersModule(BaseModule):
    """Module for managing browser-like headers for web requests"""
    
    def __init__(self):
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add browser headers to the parameters"""
        headers = params.get('headers', {})
        headers.update(self.default_headers)
        return {'headers': headers, **params}
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        return isinstance(params, dict)
    
    @property
    def capabilities(self) -> List[str]:
        return ['browser_headers', 'web_request_headers'] 