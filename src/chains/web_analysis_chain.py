from typing import List, Dict, Any
from ..core.function_chain import FunctionChain
from ..modules.browser_headers import BrowserHeadersModule
from ..modules.web_scraper import WebScraperModule
from ..modules.data_extractor import DataExtractorModule
from ..modules.report_generator import ReportGeneratorModule
from ..utils.logging import get_logger

logger = get_logger(__name__)

class WebAnalysisChain(FunctionChain):
    """Chain for scraping, processing, and reporting web content"""
    
    def __init__(self):
        super().__init__([
            BrowserHeadersModule(),
            WebScraperModule(),
            DataExtractorModule(),
            ReportGeneratorModule()
        ])
        self.id = 'web_analysis_chain'
    
    async def analyze_websites(
        self,
        urls: List[str],
        selectors: Dict[str, str] = None,
        patterns: Dict[str, str] = None,
        output_path: str = 'output/analysis.json',
        format: str = 'json'
    ) -> Dict[str, Any]:
        """
        Analyze websites and generate a report
        """
        # Specialized selectors for headlines
        if selectors is None:
            selectors = {
                'headlines': 'h1, h2, h3, .headline, .title, [class*="headline"], [class*="title"]',
                'links': 'a',
                'main_content': 'article, main, .content, #content, .main',
                'paragraphs': 'p'
            }
        
        if patterns is None:
            patterns = {
                'urls': r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*'
            }
        
        try:
            result = await self.execute_chain({
                'url': urls,
                'selectors': selectors,
                'patterns': patterns,
                'output_path': output_path,
                'format': format
            })
            
            # Format the results for better readability
            if result and 'scraped_data' in result:
                formatted_results = {}
                for url, data in result['scraped_data'].items():
                    if 'headlines' in data:
                        formatted_results[url] = {
                            'headlines': [h for h in data['headlines'] if len(h) > 1]
                        }
                return formatted_results
            return result
            
        except Exception as e:
            logger.error(f"Chain execution failed: {str(e)}")
            return {'error': str(e)} 