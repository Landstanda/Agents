from typing import Dict, Any, Optional
import logging
import os
from openai import AsyncOpenAI
from slack_sdk.web.async_client import AsyncWebClient
from src.models import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger
import httpx

logger = logging.getLogger(__name__)

class MessageMaker:
    """
    Generates and sends user messages via Slack.
    Takes context, formats with GPT, and sends via Slack.
    By default, uses real GPT for message generation. For testing,
    mock clients can be provided using use_mock=True.
    """
    
    def __init__(self, use_mock: bool = False, mock_openai = None, mock_slack = None, flow_logger: Optional[FlowLogger] = None, slack_token: Optional[str] = None):
        """Initialize the message maker with Slack and OpenAI clients.
        
        Args:
            use_mock: Whether to use mock clients (for testing)
            mock_openai: Optional mock OpenAI client (only used if use_mock=True)
            mock_slack: Optional mock Slack client (only used if use_mock=True)
            flow_logger: Optional flow logger for event tracking
            slack_token: Optional Slack token to use (if not provided, will use from env)
        """
        if use_mock:
            # Use mock clients for testing
            self.slack = mock_slack or AsyncWebClient(token="mock_token")
            self.openai = mock_openai or AsyncOpenAI(api_key="mock_key")
        else:
            # Use real clients by default
            self.slack_token = slack_token or os.getenv("SLACK_BOT_TOKEN")
            self.openai_key = os.getenv("OPENAI_API_KEY")
            
            if not self.slack_token or not self.openai_key:
                raise ValueError("Missing required environment variables SLACK_BOT_TOKEN or OPENAI_API_KEY")
                
            self.slack = AsyncWebClient(token=self.slack_token)
            
            # Create httpx client with proper configuration
            http_client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True
            )
            
            # Initialize OpenAI client with http_client
            self.openai = AsyncOpenAI(
                api_key=self.openai_key,
                http_client=http_client
            )
        
        self.flow_logger = flow_logger
        
        # System prompt for GPT
        self.system_prompt = """You are a helpful and professional AI assistant.
        Your messages should be:
        - Clear and concise
        - Professional but friendly
        - Focused on the current task
        - Free of technical jargon
        - Only report on actions that were actually completed
        - Do not suggest or imply actions that weren't taken

        When reporting task completion:
        - Be specific about what was done
        - Don't mention actions that weren't performed
        - Don't promise future actions
        - If an error occurred, clearly state what went wrong
        """
    
    async def send_message(self, ticket: Ticket) -> None:
        """Send message to user based on ticket state."""
        try:
            prompt = self._create_prompt(ticket)
            
            # Get GPT response
            response = await self.openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )
            
            if response.choices:
                message = response.choices[0].message.content.strip()
            else:
                message = self._get_fallback_message(ticket)
            
            # Add message to ticket and send to Slack
            ticket.add_outgoing_message(message)
            ticket.final_response = message  # Set the final response
            await self.slack.chat_postMessage(
                channel=ticket.channel_id,
                thread_ts=ticket.thread_ts,
                text=message
            )
            
        except Exception as e:
            self.logger.error(f"Error sending message: {str(e)}")
            # Only send a fallback message if we haven't already sent a message
            if not ticket.final_response:
                fallback_msg = self._get_fallback_message(ticket)
                ticket.add_outgoing_message(fallback_msg)
                ticket.final_response = fallback_msg
                await self.slack.chat_postMessage(
                    channel=ticket.channel_id,
                    thread_ts=ticket.thread_ts,
                    text=fallback_msg
                )
    
    def _create_prompt(self, ticket: Ticket) -> str:
        """Create GPT prompt based on ticket context."""
        status = ticket.status
        
        if status == TicketStatus.WAITING_INPUT:
            return f"""
                I need to ask the user for some information.
                Original request: {ticket.original_message}
                Missing information: {ticket.missing_entities}
                Service context: {ticket.service}
                Previous messages: {self._format_message_history(ticket)}
                Generate a friendly message asking for this information.
            """
            
        elif status == TicketStatus.COMPLETED:
            return f"""
                I need to inform the user about their completed request.
                Original request: {ticket.original_message}
                Service: {ticket.service}
                Steps executed: {self._format_steps(ticket)}
                Results: {ticket.execution_results}
                Previous messages: {self._format_message_history(ticket)}
                Generate a friendly message summarizing what was done.
            """
            
        elif status == TicketStatus.ERROR:
            return f"""
                I need to inform the user about an error.
                Original request: {ticket.original_message}
                Error details: {self._format_errors(ticket)}
                Previous messages: {self._format_message_history(ticket)}
                Generate a clear and friendly message explaining what went wrong and what the user can do next.
                Be specific about the error: {ticket.get_last_error().get('message') if ticket.get_last_error() else 'Unknown error'}
            """
            
        elif status == TicketStatus.SERVICE_CREATION:
            return f"""
                I need to inform the user about a new service being created.
                Original request: {ticket.original_message}
                Created services: {[s.get('name', '') for s in ticket.created_services]}
                Service details: {ticket.created_services[-1] if ticket.created_services else {}}
                Previous messages: {self._format_message_history(ticket)}
                Generate an informative message about the new service being created, including its purpose and capabilities.
            """
            
        return f"""
            I need to send a message to the user.
            Original request: {ticket.original_message}
            Current status: {status.value}
            Context: {ticket.to_dict()}
            Previous messages: {self._format_message_history(ticket)}
            Generate an appropriate response.
        """
    
    def _format_message_history(self, ticket: Ticket) -> str:
        """Format message history for GPT prompt."""
        return "\n".join([
            f"{msg.direction}: {msg.content}"
            for msg in ticket.messages[-5:]  # Last 5 messages for context
        ])
    
    def _format_steps(self, ticket: Ticket) -> str:
        """Format executed steps for GPT prompt."""
        return "\n".join([
            f"- {step['step']}: {step['action']} ({step['result']})"
            for step in ticket.steps_executed
        ])
    
    def _format_errors(self, ticket: Ticket) -> str:
        """Format errors for GPT prompt."""
        return "\n".join([
            f"- {error['type']}: {error['message']}"
            for error in ticket.errors
        ])
    
    def _get_fallback_message(self, ticket: Ticket) -> str:
        """Get a basic fallback message if GPT fails."""
        status = ticket.status
        
        fallbacks = {
            TicketStatus.WAITING_INPUT: f"I need some additional information: {', '.join(ticket.missing_entities)}",
            TicketStatus.COMPLETED: "I've completed your request successfully.",
            TicketStatus.ERROR: f"I apologize, but I encountered an error: {ticket.errors[-1]['message'] if ticket.errors else 'Unknown error'}",
            TicketStatus.SERVICE_CREATION: f"I'm creating a new service to handle your request.",
            TicketStatus.EXECUTING: "I'm processing your request.",
            TicketStatus.ANALYZING: "I'm analyzing your request.",
            TicketStatus.CREATED: "I'm processing your request."
        }
        
        return fallbacks.get(status, "I'm processing your request.") 