from typing import Dict, Any, Optional
import logging
import os
from openai import AsyncOpenAI
from slack_sdk.web.async_client import AsyncWebClient
from src.tools.nlp import Ticket, TicketStatus
from src.utils.flow_logger import FlowLogger

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
            self.openai = AsyncOpenAI(api_key=self.openai_key)
        
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
        """
        Generate and send a message based on the ticket context.
        
        Args:
            ticket: The ticket containing full context and history
        """
        try:
            # Create prompt for GPT based on ticket context
            user_prompt = self._create_prompt(ticket)
            
            # Get GPT response
            response = await self.openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )
            
            if response.choices:
                message = response.choices[0].message.content.strip()
                ticket.add_message(message, "assistant")
                
                # Send to Slack
                await self.slack.chat_postMessage(
                    channel=ticket.channel_id,
                    text=message,
                    thread_ts=ticket.thread_ts
                )
                
                if ticket.status == TicketStatus.COMPLETED:
                    ticket.final_response = message
            else:
                logger.error("No response from GPT")
                # Send fallback message
                fallback = self._get_fallback_message(ticket)
                ticket.add_message(fallback, "assistant")
                await self.slack.chat_postMessage(
                    channel=ticket.channel_id,
                    text=fallback,
                    thread_ts=ticket.thread_ts
                )
                
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            ticket.add_error(str(e), "message_sending_error")
            # Send basic error message
            try:
                error_msg = self._get_fallback_message(ticket)
                ticket.add_message(error_msg, "assistant")
                await self.slack.chat_postMessage(
                    channel=ticket.channel_id,
                    text=error_msg,
                    thread_ts=ticket.thread_ts
                )
            except Exception as e2:
                logger.error(f"Failed to send fallback message: {str(e2)}")
    
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
                Errors: {self._format_errors(ticket)}
                Previous messages: {self._format_message_history(ticket)}
                Generate a friendly message explaining the error.
            """
            
        elif status == TicketStatus.SERVICE_CREATION:
            return f"""
                I need to inform the user about a new service.
                Original request: {ticket.original_message}
                Created services: {ticket.created_services}
                Previous messages: {self._format_message_history(ticket)}
                Generate a message about the new service being created.
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
            f"{msg['source']}: {msg['message']}"
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
            TicketStatus.CREATED: "I've received your request."
        }
        
        return fallbacks.get(status, "I'm processing your request.") 