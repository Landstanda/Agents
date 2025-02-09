#!/usr/bin/env python3

from typing import Dict, Any, List
from ..core.chain_interface import BaseChain
from ..modules.email_reader import EmailReaderModule
from ..modules.email_classifier import EmailClassifierModule
from ..modules.response_generator import ResponseGeneratorModule
from ..modules.email_sender import EmailSenderModule
from ..utils.logging import get_logger

logger = get_logger(__name__)

class EmailProcessingChain(BaseChain):
    """Chain for processing emails from reading to response"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._initialize_modules()
        
    def execute(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute the email processing chain"""
        try:
            # Initialize chain state
            state = {
                'params': params or {},
                'results': {},
                'errors': []
            }
            
            # Step 1: Read emails
            state = self._read_emails(state)
            if state['errors']:
                return self._handle_chain_failure(state)
                
            # Process each email
            processed_emails = []
            for email in state['results'].get('emails', []):
                email_state = self._process_single_email(email, state['params'])
                processed_emails.append(email_state)
                
            # Prepare final results
            final_results = {
                'processed_emails': processed_emails,
                'success_count': sum(1 for email in processed_emails if email.get('success', False)),
                'error_count': sum(1 for email in processed_emails if not email.get('success', False)),
                'timestamp': state['results'].get('timestamp')
            }
            
            return {
                'success': True,
                'results': final_results,
                'errors': state['errors']
            }
            
        except Exception as e:
            logger.error(f"Chain execution failed: {str(e)}")
            return {
                'success': False,
                'results': None,
                'errors': [str(e)]
            }
            
    def _initialize_modules(self):
        """Initialize all required modules"""
        try:
            self.email_reader = EmailReaderModule()
            self.email_classifier = EmailClassifierModule()
            self.response_generator = ResponseGeneratorModule()
            self.email_sender = EmailSenderModule(self.config.get('smtp_config'))
            
        except Exception as e:
            logger.error(f"Failed to initialize modules: {str(e)}")
            raise
            
    def _read_emails(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Read emails using the EmailReaderModule"""
        try:
            read_params = {
                'operation': 'get_recent_emails',
                'max_emails': state['params'].get('max_emails', 10),
                'unread_only': state['params'].get('unread_only', True)
            }
            
            results = self.email_reader.execute(read_params)
            state['results'].update(results)
            return state
            
        except Exception as e:
            logger.error(f"Email reading failed: {str(e)}")
            state['errors'].append(str(e))
            return state
            
    def _process_single_email(self, email: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single email through classification, response generation, and sending"""
        try:
            # Step 2: Classify email
            classification = self.email_classifier.execute({
                'operation': 'classify_email',
                'email_data': email
            })
            
            if not classification.get('success', False):
                raise ValueError("Email classification failed")
                
            # Step 3: Generate response
            response = self.response_generator.execute({
                'operation': 'generate_response',
                'email_data': email,
                'classification': classification['classification'],
                'business_context': params.get('business_context', {})
            })
            
            if not response.get('success', False):
                raise ValueError("Response generation failed")
                
            # Step 4: Send response
            if params.get('auto_send', False):
                send_result = self.email_sender.execute({
                    'operation': 'send_email',
                    'to_address': email.get('from'),
                    'response_data': response['response']
                })
            else:
                send_result = {
                    'success': True,
                    'status': 'draft',
                    'response_data': response['response']
                }
                
            # Prepare result for this email
            return {
                'success': True,
                'email_id': email.get('message_id'),
                'classification': classification['classification'],
                'response': response['response'],
                'send_result': send_result
            }
            
        except Exception as e:
            logger.error(f"Email processing failed: {str(e)}")
            return {
                'success': False,
                'email_id': email.get('message_id'),
                'error': str(e)
            }
            
    def _handle_chain_failure(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chain failure and return appropriate response"""
        return {
            'success': False,
            'results': state.get('results'),
            'errors': state['errors']
        }
        
    @property
    def capabilities(self) -> List[str]:
        return [
            'email_processing',
            'auto_response',
            'email_classification',
            'response_generation'
        ] 