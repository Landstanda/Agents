from typing import Dict, Any, List
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from ..core.module_interface import BaseModule
from ..utils.logging import get_logger

logger = get_logger(__name__)

class WebScraperModule(BaseModule):
    """Module for scraping web content"""
    
    def __init__(self):
        self._session = None
    
    async def _ensure_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute web scraping operation
        
        Expected params:
        - url: str or List[str] - URLs to scrape
        - selectors: Dict[str, str] - CSS selectors to extract
        - headers: Dict[str, str] - Request headers
        
        Returns:
        - scraped_data: Dict[str, Any] - Extracted content
        """
        try:
            await self._ensure_session()
            urls = params['url'] if isinstance(params['url'], list) else [params['url']]
            headers = params.get('headers', {})
            results = {}
            
            for url in urls:
                try:
                    async with self._session.get(url, headers=headers, timeout=30) as response:
                        if response.status != 200:
                            logger.error(f"Failed to fetch {url}: Status {response.status}")
                            continue
                            
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        page_data = {}
                        for key, selector in params['selectors'].items():
                            elements = soup.select(selector)
                            page_data[key] = [el.get_text(strip=True) for el in elements if el.get_text(strip=True)]
                        
                        # Special handling for headlines
                        if 'headlines' in page_data:
                            # Remove duplicates while preserving order
                            seen = set()
                            page_data['headlines'] = [
                                x for x in page_data['headlines'] 
                                if not (x in seen or seen.add(x))
                            ]
                        
                        results[url] = page_data
                        
                except Exception as e:
                    logger.error(f"Error scraping {url}: {str(e)}")
                    results[url] = {"error": str(e)}
            
            return {'scraped_data': results}
            
        except Exception as e:
            logger.error(f"Scraping error: {str(e)}")
            raise
        finally:
            if self._session:
                await self._session.close()
                self._session = None
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        return (
            isinstance(params.get('url'), (str, list)) and
            isinstance(params.get('selectors'), dict)
        )
    
    @property
    def capabilities(self) -> List[str]:
        return ['web_scraping', 'html_parsing', 'data_collection'] 