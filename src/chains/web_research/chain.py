#!/usr/bin/env python3

from typing import Dict, Any, List
from ...modules.base_chain import Chain
from ...utils.logging import get_logger
import json
from datetime import datetime

logger = get_logger(__name__)

class WebResearchChain(Chain):
    """Chain for conducting web research and compiling information"""
    
    def __init__(self):
        super().__init__("web_research_chain", "1.0")
        
        # Required modules
        from ...modules.browser_automation import BrowserAutomationModule
        from ...modules.core_request import CoreRequestModule
        from ...modules.html_parser import HTMLParserModule
        from ...modules.data_cleaner import DataCleanerModule
        from ...modules.google_docs import GoogleDocsModule
        
        # Initialize modules
        self.modules = {
            'browser': BrowserAutomationModule(),
            'request': CoreRequestModule(),
            'parser': HTMLParserModule(),
            'cleaner': DataCleanerModule(),
            'docs': GoogleDocsModule()
        }
        
        # Define required and optional variables
        self.required_variables = ['text']  # Natural language request
        self.optional_variables = [
            'topic',        # Research topic
            'depth',        # How deep to follow links (default: 1)
            'max_pages',    # Maximum pages to process (default: 10)
            'save_format',  # Format to save results (default: 'doc')
            'use_browser'   # Whether to use browser automation (default: False)
        ]
        
        # Define success criteria
        self.success_criteria = [
            "Research topic is properly analyzed",
            "Relevant information is extracted",
            "Content is cleaned and organized",
            "Results are saved in specified format",
            "Links are properly followed to specified depth"
        ]
    
    async def execute(self, chain_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the web research chain"""
        try:
            # Validate variables
            validation = self.validate_variables(chain_vars)
            if validation['missing']:
                return {
                    'status': 'error',
                    'error': f"Missing required variables: {', '.join(validation['missing'])}"
                }
            
            # Log start of execution
            self.log_execution("start", {"status": "started", "variables": chain_vars})
            
            # Process the natural language request
            request = chain_vars['text']
            topic = chain_vars.get('topic', request)
            depth = int(chain_vars.get('depth', 1))
            max_pages = int(chain_vars.get('max_pages', 10))
            save_format = chain_vars.get('save_format', 'doc')
            use_browser = chain_vars.get('use_browser', False)
            
            # Initialize results storage
            research_data = {
                'topic': topic,
                'timestamp': datetime.now().isoformat(),
                'sources': [],
                'content': {}
            }
            
            # Step 1: Create research document
            doc_result = await self._execute_module(
                'docs',
                'create_document',
                title=f"Research: {topic}",
                content=f"# Research Report: {topic}\n\nGenerated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
            
            if doc_result['status'] != 'success':
                return doc_result
            
            doc_id = doc_result['result']['id']
            
            # Step 2: Process initial URLs
            initial_urls = await self._get_initial_urls(topic)
            processed_urls = set()
            urls_to_process = initial_urls.copy()
            
            while urls_to_process and len(processed_urls) < max_pages:
                current_url = urls_to_process.pop(0)
                
                if current_url in processed_urls:
                    continue
                
                # Process the URL
                page_data = await self._process_url(
                    current_url, 
                    use_browser=use_browser
                )
                
                if page_data:
                    processed_urls.add(current_url)
                    research_data['sources'].append(current_url)
                    research_data['content'][current_url] = page_data
                    
                    # Add section to document
                    section_content = self._format_page_data(page_data, current_url)
                    await self._execute_module(
                        'docs',
                        'add_section',
                        doc_id=doc_id,
                        content=section_content
                    )
                    
                    # Follow links if needed
                    if depth > 1 and len(processed_urls) < max_pages:
                        new_urls = page_data.get('links', [])
                        urls_to_process.extend([
                            url for url in new_urls 
                            if url not in processed_urls 
                            and url not in urls_to_process
                        ])
            
            # Step 3: Add summary section
            summary = self._create_research_summary(research_data)
            await self._execute_module(
                'docs',
                'add_section',
                doc_id=doc_id,
                content=summary,
                position='start'
            )
            
            # Return success result
            return {
                'status': 'success',
                'message': f"Research completed with {len(processed_urls)} sources",
                'research_data': research_data,
                'doc_id': doc_id,
                'actions': [{
                    'type': 'send_message',
                    'text': f"📚 Research on '{topic}' completed!\n"
                           f"• Processed {len(processed_urls)} sources\n"
                           f"• Created document: {doc_result['result']['url']}"
                }]
            }
            
        except Exception as e:
            logger.error(f"Error in web research chain: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def _get_initial_urls(self, topic: str) -> List[str]:
        """Get initial URLs for research"""
        # Use search API or direct URLs based on topic
        # This is a simplified implementation
        search_result = await self._execute_module(
            'request',
            'search',
            query=topic,
            num_results=5
        )
        
        if search_result['status'] == 'success':
            return search_result['result']['urls']
        return []
    
    async def _process_url(self, url: str, use_browser: bool = False) -> Dict[str, Any]:
        """Process a single URL and extract information"""
        try:
            # Get page content
            if use_browser:
                content_result = await self._execute_module(
                    'browser',
                    'get_page_content',
                    url=url
                )
            else:
                content_result = await self._execute_module(
                    'request',
                    'get',
                    url=url
                )
            
            if content_result['status'] != 'success':
                return None
            
            content = content_result['result']
            
            # Parse HTML
            parse_result = await self._execute_module(
                'parser',
                'extract_content',
                html=content
            )
            
            if parse_result['status'] != 'success':
                return None
            
            parsed_data = parse_result['result']
            
            # Clean text
            clean_result = await self._execute_module(
                'cleaner',
                'clean_text',
                text=parsed_data['text']
            )
            
            if clean_result['status'] == 'success':
                parsed_data['cleaned_text'] = clean_result['result']
            
            # Extract entities
            entities_result = await self._execute_module(
                'cleaner',
                'extract_entities',
                text=parsed_data['cleaned_text']
            )
            
            if entities_result['status'] == 'success':
                parsed_data['entities'] = entities_result['result']
            
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            return None
    
    def _format_page_data(self, page_data: Dict[str, Any], url: str) -> str:
        """Format page data for document section"""
        section = f"## Source: {url}\n\n"
        
        if page_data.get('title'):
            section += f"### {page_data['title']}\n\n"
        
        if page_data.get('cleaned_text'):
            section += f"{page_data['cleaned_text']}\n\n"
        
        if page_data.get('entities'):
            section += "### Key Entities\n\n"
            for entity_type, entities in page_data['entities'].items():
                section += f"**{entity_type}**: {', '.join(entities)}\n"
            section += "\n"
        
        return section
    
    def _create_research_summary(self, research_data: Dict[str, Any]) -> str:
        """Create a summary of the research"""
        summary = "## Executive Summary\n\n"
        
        # Add overview
        summary += f"This research report covers '{research_data['topic']}' "
        summary += f"and includes information from {len(research_data['sources'])} sources.\n\n"
        
        # Add key findings
        summary += "### Key Findings\n\n"
        
        # Aggregate entities across all sources
        all_entities = {}
        for page_data in research_data['content'].values():
            if page_data.get('entities'):
                for entity_type, entities in page_data['entities'].items():
                    if entity_type not in all_entities:
                        all_entities[entity_type] = set()
                    all_entities[entity_type].update(entities)
        
        # Add most common entities
        for entity_type, entities in all_entities.items():
            summary += f"**{entity_type}**: {', '.join(list(entities)[:5])}\n"
        
        summary += "\n### Sources\n\n"
        for url in research_data['sources']:
            summary += f"- {url}\n"
        
        return summary 