import asyncio
import logging
from pathlib import Path
from src.core.agent import Agent
from src.models import Ticket, TicketStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)

async def test_agent():
    """Test the agent implementation with a simple service"""
    try:
        logger.info("Starting agent test")
        
        # Create agent
        agent = Agent()
        await agent.initialize()
        
        # Create test ticket
        ticket = Ticket(
            user_info={"user_id": "test_user", "channel_id": "test_channel"},
            original_message="Test service execution"
        )
        ticket.service = "test_service"
        ticket.entities = {
            "test_entity": "test_value"  # Required entity for test service
        }
        
        # Process ticket
        logger.info("Processing test ticket")
        await agent.process_ticket(ticket)
        
        # Check results
        logger.info(f"Ticket status: {ticket.status}")
        logger.info(f"Ticket errors: {list(ticket.errors)}")
        logger.info(f"Step results: {ticket.step_results}")
        
        # Verify success
        assert ticket.status == TicketStatus.COMPLETED, "Service execution failed"
        assert len(ticket.step_results) > 0, "No step results recorded"
        
        logger.info("✓ Test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run test
    asyncio.run(test_agent()) 