#!/usr/bin/env python3
import asyncio
import logging
from src.models import Ticket, TicketStatus
from src.core.orchestrator import RequestOrchestrator
from src.utils.flow_logger import FlowLogger

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_ticket_status_transitions():
    """Test ticket status transitions to identify invalid transitions"""
    logger.info("Testing ticket status transitions")
    
    # Create a test ticket
    ticket = Ticket(
        original_message="Test message",
        user_info={"user_id": "test_user"},
        channel_id="test_channel"
    )
    
    # Print initial status
    logger.info(f"Initial ticket status: {ticket.status}")
    
    # Test all possible transitions
    transitions_to_test = [
        (TicketStatus.CREATED, TicketStatus.ANALYZING),
        (TicketStatus.ANALYZING, TicketStatus.EXECUTING),
        (TicketStatus.EXECUTING, TicketStatus.COMPLETED),
        (TicketStatus.EXECUTING, TicketStatus.ERROR),
        (TicketStatus.EXECUTING, TicketStatus.ANALYZING),  # This is the problematic one
        (TicketStatus.ERROR, TicketStatus.ANALYZING),
        (TicketStatus.COMPLETED, TicketStatus.ANALYZING)
    ]
    
    for from_status, to_status in transitions_to_test:
        # Reset ticket status to the starting status
        ticket.status = from_status
        ticket.status_history = [{
            "status": from_status,
            "timestamp": ticket.created_at
        }]
        
        try:
            logger.info(f"Testing transition from {from_status} to {to_status}")
            ticket.update_status(to_status)
            logger.info(f"✅ Transition successful: {from_status} -> {to_status}")
        except ValueError as e:
            logger.error(f"❌ Transition failed: {from_status} -> {to_status}: {str(e)}")

async def test_ticket_copy():
    """Test if Ticket has a copy method or how to implement one"""
    logger.info("Testing ticket copy functionality")
    
    # Create a test ticket
    ticket = Ticket(
        original_message="Test message",
        user_info={"user_id": "test_user"},
        channel_id="test_channel"
    )
    
    # Check if copy method exists
    if hasattr(ticket, 'copy'):
        logger.info("✅ Ticket has a copy method")
    else:
        logger.error("❌ Ticket does not have a copy method")
        
        # Create a copy manually using to_dict and from_dict
        logger.info("Creating a copy manually using to_dict and from_dict")
        ticket_dict = ticket.to_dict()
        ticket_copy = Ticket.from_dict(ticket_dict)
        
        logger.info(f"Original ticket ID: {ticket.ticket_id}")
        logger.info(f"Copied ticket ID: {ticket_copy.ticket_id}")
        
        # Compare attributes
        logger.info("Comparing attributes:")
        logger.info(f"Same status: {ticket.status == ticket_copy.status}")
        logger.info(f"Same message: {ticket.original_message == ticket_copy.original_message}")

async def test_orchestrator_acknowledgment():
    """Test the acknowledgment functionality in the orchestrator"""
    logger.info("Testing orchestrator acknowledgment")
    
    # Create flow logger and orchestrator
    flow_logger = FlowLogger()
    orchestrator = RequestOrchestrator(flow_logger=flow_logger)
    
    # Initialize orchestrator
    await orchestrator.initialize()
    
    # Create a test ticket
    ticket = Ticket(
        original_message="Test message",
        user_info={"user_id": "test_user"},
        channel_id="test_channel"
    )
    
    # Test the _send_acknowledgment method
    try:
        await orchestrator._send_acknowledgment(ticket)
        logger.info("✅ Acknowledgment sent successfully")
    except Exception as e:
        logger.error(f"❌ Failed to send acknowledgment: {str(e)}")
        
        # Inspect the method to see what's happening
        logger.info("Inspecting _send_acknowledgment method:")
        logger.info(f"Method code: {orchestrator._send_acknowledgment.__code__}")

async def main():
    """Run all tests"""
    logger.info("Starting troubleshooting tests")
    
    await test_ticket_status_transitions()
    logger.info("-" * 50)
    
    await test_ticket_copy()
    logger.info("-" * 50)
    
    await test_orchestrator_acknowledgment()
    
    logger.info("Troubleshooting tests completed")

if __name__ == "__main__":
    asyncio.run(main()) 