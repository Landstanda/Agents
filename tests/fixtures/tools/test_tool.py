from typing import Dict, Any

class TestTool:
    """A test tool for testing purposes."""
    
    async def test_action(self, param1: str) -> Dict[str, Any]:
        """A test action that returns the input parameter."""
        return {
            'status': 'success',
            'result': param1
        } 