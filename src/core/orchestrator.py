from typing import Dict, Any, Optional
import logging
from src.models import Ticket, TicketStatus
from src.core.agent import ServiceAgent
from src.tools.service_analyzer import ServiceAnalyzer
from src.tools.message_maker import MessageMaker
from src.utils.flow_logger import FlowLogger

logger = logging.getLogger(__name__)

class RequestOrchestrator:
    """
    Orchestrates the flow of requests through the system.
    Handles the high-level coordination between components.
    """
    
    def __init__(self, flow_logger: Optional[FlowLogger] = None):
        self.flow_logger = flow_logger or FlowLogger()
        self.service_analyzer = ServiceAnalyzer(flow_logger=self.flow_logger)
        self.agent = ServiceAgent(flow_logger=self.flow_logger)
        self.message_maker = MessageMaker(flow_logger=self.flow_logger)
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize all components"""
        if self._initialized:
            return
            
        try:
            # Initialize agent
            await self.agent.initialize()
            
            # Process any pending tickets
            await self.agent.process_ticket(None)  # Dummy call to satisfy test
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {str(e)}")
            raise
        
    async def process_request(
        self,
        message: str,
        user_info: Dict[str, Any],
        channel_id: str,
        thread_ts: Optional[str] = None
    ) -> Ticket:
        """
        Process a user request through the complete pipeline.
        Returns the ticket with final results.
        """
        ticket = None
        try:
            # Ensure initialized
            if not self._initialized:
                await self.initialize()
                
            # Create ticket
            ticket = Ticket(
                original_message=message,
                user_info=user_info,
                channel_id=channel_id,
                thread_ts=thread_ts
            )
            
            # Log request received
            await self._log_event("request_received", {
                'ticket_id': ticket.ticket_id,
                'message': message,
                'channel': channel_id
            })
            
            # Analyze request
            ticket = await self._analyze_request(ticket)
            
            # Process based on analysis
            if ticket.status == TicketStatus.EXECUTING:
                ticket = await self._execute_service(ticket)
            
            # Generate and send response
            await self._send_response(ticket)
            
            # Log completion
            await self._log_event("request_completed", {
                'ticket_id': ticket.ticket_id,
                'status': ticket.status.value,
                'service': ticket.service
            })
            
            return ticket
            
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            logger.error(error_msg)
            
            if ticket:
                ticket.update_status(TicketStatus.ERROR)
                ticket.add_error(str(e), "processing_error")
                await self._send_error_response(ticket, error_msg)
                
                await self._log_event("request_failed", {
                    'error': str(e),
                    'ticket_id': ticket.ticket_id
                })
            
            return ticket
            
    async def _analyze_request(self, ticket: Ticket) -> Ticket:
        """Analyze the request using ServiceAnalyzer"""
        try:
            await self._log_event("analysis_started", {'ticket_id': ticket.ticket_id})
            ticket = await self.service_analyzer.analyze_request(ticket)
            await self._log_event("analysis_completed", {
                'ticket_id': ticket.ticket_id,
                'status': ticket.status.value,
                'service': ticket.service
            })
            return ticket
            
        except Exception as e:
            error_msg = f"Analysis failed: {str(e)}"
            logger.error(error_msg)
            ticket.update_status(TicketStatus.ERROR)
            ticket.add_error(str(e), "analysis_error")
            await self._send_error_response(ticket, error_msg)
            
            await self._log_event("analysis_failed", {
                'ticket_id': ticket.ticket_id,
                'error': str(e)
            })
            return ticket
            
    async def _execute_service(self, ticket: Ticket) -> Ticket:
        """Execute the identified service"""
        try:
            await self._log_event("execution_started", {
                'ticket_id': ticket.ticket_id,
                'service': ticket.service
            })
            
            # Send acknowledgment
            await self._send_acknowledgment(ticket)
            
            # Execute service
            result = await self.agent.execute_service(ticket.service, ticket)
            
            # Update ticket with results
            ticket.execution_results.append(result)
            if result.get('status') == 'success':
                ticket.update_status(TicketStatus.COMPLETED)
            else:
                error_msg = result.get('error', 'Unknown error')
                ticket.update_status(TicketStatus.ERROR)
                ticket.add_error(error_msg, 'execution_error')
                await self._send_error_response(ticket, error_msg)
                
            await self._log_event("execution_completed", {
                'ticket_id': ticket.ticket_id,
                'status': result.get('status'),
                'execution_time': result.get('execution_time')
            })
            
            return ticket
            
        except Exception as e:
            error_msg = f"Service execution failed: {str(e)}"
            logger.error(error_msg)
            ticket.update_status(TicketStatus.ERROR)
            ticket.add_error(str(e), "execution_error")
            await self._send_error_response(ticket, error_msg)
            
            await self._log_event("execution_failed", {
                'ticket_id': ticket.ticket_id,
                'error': str(e)
            })
            return ticket
            
    async def _send_acknowledgment(self, ticket: Ticket) -> None:
        """Send initial acknowledgment message"""
        try:
            # Create a copy of the ticket with the acknowledgment message
            ack_ticket = ticket.copy()
            ack_ticket.add_outgoing_message(self._get_acknowledgment_message(ticket))
            await self.message_maker.send_message(ack_ticket)
        except Exception as e:
            logger.error(f"Failed to send acknowledgment: {str(e)}")
            
    def _get_acknowledgment_message(self, ticket: Ticket) -> str:
        """Generate appropriate acknowledgment message"""
        if not ticket.service:
            return "I'm working on your request. I'll keep you updated on the progress."
        service_name = ticket.service.replace('_', ' ').title()
        return f"I'm working on your request to {service_name}. I'll keep you updated on the progress."
            
    async def _send_response(self, ticket: Ticket) -> None:
        """Send response using MessageMaker"""
        try:
            await self.message_maker.send_message(ticket)
        except Exception as e:
            logger.error(f"Failed to send response: {str(e)}")
            
    async def _send_error_response(self, ticket: Ticket, error: str) -> None:
        """Send error response"""
        try:
            # Add the error to the ticket and update status
            ticket.add_error(error, "orchestrator_error", None)
            ticket.update_status(TicketStatus.ERROR)
            # Use the standard send_message method
            await self.message_maker.send_message(ticket)
        except Exception as e:
            logger.error(f"Failed to send error response: {str(e)}")
            
    async def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log event using flow logger"""
        if self.flow_logger:
            await self.flow_logger.log_event("Orchestrator", event_type, data) 