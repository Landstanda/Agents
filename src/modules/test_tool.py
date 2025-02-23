from src.core.module_interface import BaseModule
from src.models import Ticket

class TestTool(BaseModule):
    """A simple test tool for verifying tool loading"""
    
    async def execute(self, ticket: Ticket, params: dict) -> dict:
        """Execute the test tool."""
        return {
            "success": True,
            "data": {
                "status": "success",
                "message": "Test tool executed successfully"
            }
        }
        
    @property
    def capabilities(self) -> list:
        """Return list of tool capabilities"""
        return ['test'] 