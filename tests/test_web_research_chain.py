import pytest
import logging
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# Mock implementations
class MockBrowserAutomationModule:
    async def navigate_to(self, url):
        logging.info(f"Mock: Navigating to {url}")
        return {"status": "success", "page_loaded": True}
    
    async def get_page_content(self):
        logging.info("Mock: Getting page content")
        return {
            "html": "<html><body>Sample content</body></html>",
            "text": "Sample content",
            "links": ["https://example.com/page1", "https://example.com/page2"]
        }
    
    async def take_screenshot(self):
        logging.info("Mock: Taking screenshot")
        return {"image_data": "base64_encoded_image"}

class MockCoreRequestModule:
    async def get(self, url, headers=None):
        logging.info(f"Mock: GET request to {url}")
        return {
            "status": 200,
            "content": "Sample API response",
            "headers": {"content-type": "text/html"}
        }

class MockHTMLParserModule:
    async def extract_content(self, html, selectors=None):
        logging.info("Mock: Extracting content from HTML")
        return {
            "title": "Sample Page",
            "main_content": "Main content text",
            "metadata": {"author": "John Doe", "date": "2024-01-01"}
        }
    
    async def extract_links(self, html, base_url):
        logging.info("Mock: Extracting links")
        return {
            "internal_links": ["https://example.com/page1"],
            "external_links": ["https://other.com/page1"]
        }

class MockDataCleanerModule:
    async def clean_text(self, text):
        logging.info("Mock: Cleaning text")
        return {
            "cleaned_text": text.strip(),
            "word_count": len(text.split()),
            "language": "en"
        }
    
    async def extract_entities(self, text):
        logging.info("Mock: Extracting entities")
        return {
            "organizations": ["Company X"],
            "people": ["John Doe"],
            "locations": ["New York"]
        }

class MockGoogleDocsModule:
    async def create_document(self, title, content):
        logging.info(f"Mock: Creating document '{title}'")
        return {
            "doc_id": "doc_123",
            "url": "https://docs.google.com/doc_123"
        }
    
    async def add_section(self, doc_id, content, heading=None):
        logging.info(f"Mock: Adding section to document {doc_id}")
        return {"status": "success"}

# The chain implementation
class WebResearchChain:
    def __init__(self):
        self.browser = MockBrowserAutomationModule()
        self.request = MockCoreRequestModule()
        self.parser = MockHTMLParserModule()
        self.cleaner = MockDataCleanerModule()
        self.docs = MockGoogleDocsModule()

    async def execute(self, chain_vars):
        try:
            research_data = []
            visited_urls = set()
            
            # Create research document
            doc = await self.docs.create_document(
                title=chain_vars["research_title"],
                content=f"Research: {chain_vars['research_title']}\nDate: {datetime.now()}"
            )
            
            # Process each URL
            for url in chain_vars["urls"]:
                if url in visited_urls:
                    continue
                    
                visited_urls.add(url)
                
                # Step 1: Get page content
                if chain_vars.get("use_browser", False):
                    await self.browser.navigate_to(url)
                    page_data = await self.browser.get_page_content()
                    if chain_vars.get("take_screenshots"):
                        screenshot = await self.browser.take_screenshot()
                else:
                    response = await self.request.get(url)
                    page_data = {"html": response["content"], "text": response["content"]}
                
                # Step 2: Parse content
                parsed = await self.parser.extract_content(page_data["html"])
                
                # Step 3: Clean and analyze text
                cleaned = await self.cleaner.clean_text(parsed["main_content"])
                entities = await self.cleaner.extract_entities(cleaned["cleaned_text"])
                
                # Step 4: Extract additional links if recursive
                if chain_vars.get("recursive"):
                    links = await self.parser.extract_links(page_data["html"], url)
                    new_urls = [link for link in links["internal_links"] 
                              if link not in visited_urls]
                    chain_vars["urls"].extend(new_urls[:chain_vars.get("max_recursive", 3)])
                
                # Step 5: Add to research document
                await self.docs.add_section(
                    doc_id=doc["doc_id"],
                    heading=f"Research from {url}",
                    content=f"""
                    Content Summary:
                    {cleaned['cleaned_text'][:500]}...
                    
                    Key Entities:
                    - Organizations: {', '.join(entities['organizations'])}
                    - People: {', '.join(entities['people'])}
                    - Locations: {', '.join(entities['locations'])}
                    
                    Word Count: {cleaned['word_count']}
                    Language: {cleaned['language']}
                    """
                )
                
                research_data.append({
                    "url": url,
                    "title": parsed["title"],
                    "summary": cleaned["cleaned_text"][:200],
                    "entities": entities,
                    "word_count": cleaned["word_count"]
                })
            
            return {
                "status": "success",
                "doc_url": doc["url"],
                "processed_urls": len(visited_urls),
                "research_data": research_data
            }
            
        except Exception as e:
            logging.error(f"Chain execution failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

# Tests
@pytest.mark.asyncio
async def test_basic_web_research():
    chain = WebResearchChain()
    chain_vars = {
        "research_title": "Market Research",
        "urls": ["https://example.com/market", "https://example.com/industry"],
        "use_browser": False
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"
    assert "doc_url" in result
    assert result["processed_urls"] == 2

@pytest.mark.asyncio
async def test_browser_based_research():
    chain = WebResearchChain()
    chain_vars = {
        "research_title": "Competitor Analysis",
        "urls": ["https://competitor1.com", "https://competitor2.com"],
        "use_browser": True,
        "take_screenshots": True
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"
    assert result["processed_urls"] == 2

@pytest.mark.asyncio
async def test_recursive_research():
    chain = WebResearchChain()
    chain_vars = {
        "research_title": "Technology Trends",
        "urls": ["https://example.com/tech"],
        "use_browser": False,
        "recursive": True,
        "max_recursive": 2
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"
    assert result["processed_urls"] > 1

@pytest.mark.asyncio
async def test_error_handling():
    chain = WebResearchChain()
    # Test with invalid URL
    chain_vars = {
        "research_title": "Test Research",
        "urls": []  # Empty URL list
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"
    assert result["processed_urls"] == 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__]) 