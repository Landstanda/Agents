#!/usr/bin/env python3

import os
import json
import yaml
from typing import Dict, List, Any, Tuple
from ..utils.logging import get_logger
import importlib
import inspect
import re
from datetime import datetime

logger = get_logger(__name__)

class Brain:
    def __init__(self):
        self.modules = self.load_modules()
        self.request_handler = self._load_chain_implementation('request_handler_chain')
        if not self.request_handler:
            raise ValueError("Could not load request handler chain")
        self.chains = {}
        self._load_chains()
        self.capabilities = self.analyze_capabilities()
        self.context_history = {}  # Store conversation context per user
        
    def load_modules(self) -> Dict[str, Any]:
        """Load all available modules"""
        modules = {}
        module_dir = os.path.dirname(__file__)
        
        # Map of module names to file names
        module_files = {
            "GoogleAuthModule": "google_auth",
            "SystemInteractionModule": "system_interaction",
            "SlackModule": "slack_integration",
            "TrelloModule": "trello_integration",
            "EmailReaderModule": "email_reader",
            "EmailSenderModule": "email_sender",
            "NotificationModule": "notification",
            "DocManagementModule": "doc_management",
            "FileTransferModule": "file_transfer",
            "ProjectSyncModule": "project_sync",
            "BusinessContextModule": "business_context",
            "BrowserHeadersModule": "browser_headers",
            "BrowserAutomationModule": "browser_automation",
            "CoreRequestModule": "core_request",
            "SessionManagerModule": "session_manager",
            "BasicAuthModule": "basic_auth",
            "HTMLParserModule": "html_parser",
            "DataCleanerModule": "data_cleaner",
            "GoogleDriveModule": "google_drive",
            "GoogleDocsModule": "google_docs",
            "GoogleCalendarModule": "google_calendar"
        }
        
        for module_name, module_file in module_files.items():
            try:
                # Import module from the current package
                module = importlib.import_module(f".{module_file}", package="src.modules")
                
                # Get the actual class from the module
                module_class = getattr(module, module_name)
                
                # Store module class
                modules[module_name] = module_class
                logger.info(f"Loaded module: {module_name}")
                
            except Exception as e:
                logger.error(f"Error loading module {module_name}: {str(e)}")
        
        return modules

    def _load_chains(self):
        """Load all other chains"""
        try:
            # Load chain definitions from markdown
            chain_file = os.path.join(os.path.dirname(__file__), 
                                    '../../docs/CHAIN_DEFINITIONS.md')
            
            with open(chain_file, 'r') as f:
                content = f.read()
            
            # Parse the markdown to extract chain definitions
            sections = content.split('## ')[1:]  # Split by section headers
            
            for section in sections:
                if '```python' in section:  # Only process python code blocks
                    # Get chain name from first line of section
                    chain_name = section.split('\n')[0].strip()
                    
                    # Extract the python code block
                    code_block = section.split('```python')[1].split('```')[0]
                    
                    # Parse the chain definition
                    chain_def = self._parse_chain_definition(code_block)
                    
                    if chain_def:
                        # Try to load the actual chain implementation
                        chain_impl = self._load_chain_implementation(chain_name)
                        if chain_impl:
                            self.chains[chain_name] = chain_impl
                        else:
                            self.chains[chain_name] = chain_def
                        logger.info(f"Loaded chain: {chain_name}")
            
        except Exception as e:
            logger.error(f"Error loading chain definitions: {str(e)}")

    def _parse_chain_definition(self, code_block: str) -> Dict[str, Any]:
        """Parse a chain definition from its code block"""
        try:
            lines = code_block.strip().split('\n')
            chain_def = {
                'name': '',
                'status': '',
                'version': '',
                'input_variables': [],
                'success_criteria': [],
                'module_sequence': []
            }
            
            current_section = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('# Chain Name:'):
                    chain_def['name'] = line.split(':')[1].strip()
                elif line.startswith('# Status:'):
                    chain_def['status'] = line.split(':')[1].strip()
                elif line.startswith('# Version:'):
                    chain_def['version'] = line.split(':')[1].strip()
                elif line.startswith('Input_Variables:'):
                    current_section = 'input_variables'
                elif line.startswith('Success_Criteria:'):
                    current_section = 'success_criteria'
                elif line.startswith('Module_Sequence:'):
                    current_section = 'module_sequence'
                elif line.startswith('-') and current_section:
                    item = line[1:].strip()
                    chain_def[current_section].append(item)
                
            return chain_def
            
        except Exception as e:
            logger.error(f"Error parsing chain definition: {str(e)}")
            return None

    def _load_chain_implementation(self, chain_name: str) -> Any:
        """Load the actual chain implementation class"""
        try:
            # Convert chain name to module path
            # e.g. 'email_processing_chain' -> 'src.chains.email_processing.chain'
            chain_name = chain_name.lower()
            if chain_name.endswith('_chain'):
                module_name = chain_name[:-6]  # Remove '_chain' suffix
            else:
                module_name = chain_name
            
            module_path = f"src.chains.{module_name}.chain"
            
            try:
                # Import the module
                module = importlib.import_module(module_path)
                
                # Get the chain class (assumed to be the only class in the module)
                chain_classes = [obj for name, obj in inspect.getmembers(module, inspect.isclass)
                               if name.endswith('Chain')]
                
                if chain_classes:
                    # Initialize the chain with default config
                    chain_class = chain_classes[0]
                    chain_instance = chain_class()
                    logger.info(f"Successfully loaded chain implementation: {chain_name}")
                    return chain_instance
                
                logger.warning(f"No chain class found in module: {module_path}")
                return None
                
            except ImportError as e:
                logger.warning(f"Could not import chain module {module_path}: {str(e)}")
                return None
            except Exception as e:
                logger.warning(f"Error loading chain {chain_name}: {str(e)}")
                return None
            
        except Exception as e:
            logger.warning(f"Could not load chain implementation for {chain_name}: {str(e)}")
            return None

    def analyze_capabilities(self) -> Dict[str, List[str]]:
        """Analyze and categorize available capabilities"""
        capabilities = {
            'document_management': [],
            'communication': [],
            'project_management': [],
            'research': [],
            'email': [],
            'calendar': [],
            'automation': []
        }
        
        # Analyze modules
        for module_name in self.modules:
            if 'Doc' in module_name or 'File' in module_name:
                capabilities['document_management'].append(module_name)
            if 'Slack' in module_name or 'Email' in module_name or 'Notification' in module_name:
                capabilities['communication'].append(module_name)
            if 'Project' in module_name or 'Trello' in module_name:
                capabilities['project_management'].append(module_name)
            if 'Browser' in module_name or 'HTML' in module_name:
                capabilities['research'].append(module_name)
            if 'Email' in module_name:
                capabilities['email'].append(module_name)
            if 'Calendar' in module_name:
                capabilities['calendar'].append(module_name)
            if 'Automation' in module_name:
                capabilities['automation'].append(module_name)
        
        # Add chains to capabilities
        for chain_name, chain_def in self.chains.items():
            category = self._categorize_chain(chain_name, chain_def)
            if category in capabilities:
                capabilities[category].append(f"Chain: {chain_name}")
        
        return capabilities

    def _categorize_chain(self, chain_name: str, chain_def: Dict) -> str:
        """Categorize a chain based on its name and definition"""
        name_lower = chain_name.lower()
        if 'document' in name_lower or 'doc' in name_lower:
            return 'document_management'
        if 'communication' in name_lower or 'message' in name_lower:
            return 'communication'
        if 'project' in name_lower or 'task' in name_lower:
            return 'project_management'
        if 'research' in name_lower or 'search' in name_lower:
            return 'research'
        if 'email' in name_lower:
            return 'email'
        if 'meeting' in name_lower or 'calendar' in name_lower:
            return 'calendar'
        return 'automation'

    def get_capability_description(self) -> str:
        """Generate a description of all capabilities"""
        description = "I can help you with the following:\n\n"
        
        for category, items in self.capabilities.items():
            if items:  # Only include categories with capabilities
                description += f"*{category.replace('_', ' ').title()}*:\n"
                for item in items:
                    description += f"- {item}\n"
                description += "\n"
        
        return description

    def _analyze_request(self, request: str) -> Tuple[str, Dict[str, Any]]:
        """Analyze a natural language request to determine intent and extract variables"""
        request_lower = request.lower()
        extracted_vars = {}
        
        # Common patterns for intent recognition
        patterns = {
            'email_processing': [
                r'process.*email',
                r'check.*email',
                r'handle.*email',
                r'manage.*email',
                r'organize.*email'
            ],
            'web_research': [
                r'research.*about',
                r'find.*information',
                r'search.*for',
                r'look.*up',
                r'gather.*data'
            ],
            'business_communication': [
                r'send.*message',
                r'communicate.*with',
                r'notify.*team',
                r'update.*status',
                r'post.*update'
            ],
            'document_management': [
                r'create.*document',
                r'update.*file',
                r'organize.*files',
                r'manage.*docs',
                r'handle.*documents'
            ],
            'project_management': [
                r'create.*task',
                r'update.*project',
                r'track.*progress',
                r'manage.*project',
                r'assign.*task'
            ]
        }
        
        # Try to match patterns to determine intent
        for intent, pattern_list in patterns.items():
            for pattern in pattern_list:
                if re.search(pattern, request_lower):
                    return intent, self._extract_variables(request, intent)
        
        # Default to general request if no specific intent is found
        return 'general', {'text': request}
    
    def _extract_variables(self, request: str, intent: str) -> Dict[str, Any]:
        """Extract variables from the request based on intent"""
        variables = {}
        
        # Common variable extraction patterns
        email_patterns = {
            'folder': r'(?:in|to|from).*folder[:\s]+([^\s,\.]+)',
            'label': r'label[:\s]+([^\s,\.]+)',
            'urgent': r'urgent|important|priority',
            'archive': r'archive|store|save'
        }
        
        web_research_patterns = {
            'topic': r'(?:about|for|on)[:\s]+([^,\.]+)',
            'depth': r'(?:depth|level)[:\s]+(\d+)',
            'max_pages': r'(?:max|limit)[:\s]+(\d+).*pages',
            'save_format': r'save.*(?:as|in)[:\s]+(\w+)'
        }
        
        communication_patterns = {
            'channel': r'(?:in|to)[:\s]+#([^\s,\.]+)',
            'recipients': r'to[:\s]+@([^\s,\.]+)',
            'priority': r'(?:priority|urgency)[:\s]+(\w+)',
            'schedule': r'(?:at|on)[:\s]+([\w\s\d:]+)'
        }
        
        # Extract variables based on intent
        if intent == 'email_processing':
            patterns = email_patterns
        elif intent == 'web_research':
            patterns = web_research_patterns
        elif intent == 'business_communication':
            patterns = communication_patterns
        else:
            patterns = {}
        
        # Apply patterns to extract variables
        for var_name, pattern in patterns.items():
            match = re.search(pattern, request, re.IGNORECASE)
            if match:
                variables[var_name] = match.group(1)
        
        # Add the original text for context
        variables['text'] = request
        
        return variables
    
    def _get_chain_for_intent(self, intent: str, variables: Dict[str, Any]) -> str:
        """Get the most appropriate chain for the given intent and variables"""
        # Map intents to chain names
        intent_chain_map = {
            'email_processing': 'email_processing_chain',
            'web_research': 'web_research_chain',
            'business_communication': 'business_communication_chain',
            'document_management': 'document_management_chain',
            'project_management': 'project_management_chain'
        }
        
        return intent_chain_map.get(intent, 'general_chain')
    
    def _update_context(self, user: str, request: str, result: Dict[str, Any]) -> None:
        """Update conversation context for a user"""
        if user not in self.context_history:
            self.context_history[user] = []
            
        self.context_history[user].append({
            'timestamp': datetime.now().isoformat(),
            'request': request,
            'result': result
        })
        
        # Keep only last 10 interactions
        if len(self.context_history[user]) > 10:
            self.context_history[user] = self.context_history[user][-10:]
    
    async def process_request(self, request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a request through the brain"""
        try:
            # First analyze request through request handler
            handler_result = await self.request_handler.execute({
                'text': request,
                **(context or {})
            })
            
            if handler_result['status'] != 'success':
                return handler_result
                
            # If it's a conversation, return directly
            if handler_result['data']['type'] == 'conversation':
                return handler_result
                
            # If it's a task, route to appropriate chain
            chain_name = handler_result['data']['chain']
            if chain_name not in self.chains:
                return {
                    'status': 'error',
                    'message': f"Chain {chain_name} not found",
                    'data': None
                }
                
            # Process through appropriate chain
            chain = self.chains[chain_name]
            variables = handler_result['data'].get('variables', {})
            variables['text'] = request  # Always include original text
            
            chain_result = await chain.execute({
                'text': request,
                **variables,
                **(context or {})
            })
            
            return chain_result
            
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'data': None
            }

    def get_module(self, module_name: str) -> Any:
        """Get a module instance by name"""
        return self.modules.get(module_name)

    def get_chain(self, chain_name: str) -> Dict[str, Any]:
        """Get a chain definition by name"""
        return self.chains.get(chain_name)

    async def execute_chain(self, chain_name: str, request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a chain by name, adapting between execute() and process() methods"""
        chain = self.get_chain(chain_name)
        if not chain:
            return {
                'status': 'error',
                'message': f'Chain {chain_name} not found',
                'data': None
            }
        
        try:
            # Try process() first (new interface)
            if hasattr(chain, 'process'):
                return await chain.process(request, context)
            # Fall back to execute() (old interface)
            elif hasattr(chain, 'execute'):
                return await chain.execute(request, context)
            else:
                return {
                    'status': 'error',
                    'message': f'Chain {chain_name} has no process() or execute() method',
                    'data': None
                }
        except Exception as e:
            logger.error(f"Error executing chain {chain_name}: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error executing chain {chain_name}: {str(e)}',
                'data': None
            } 