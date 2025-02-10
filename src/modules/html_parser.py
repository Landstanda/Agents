#!/usr/bin/env python3

from bs4 import BeautifulSoup
from bs4.element import Comment
import re
from typing import List, Dict, Union, Optional
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)

class HTMLParserModule:
    """Module for parsing and extracting information from HTML content."""
    
    def __init__(self):
        self.soup = None
        
    def load_html(self, html_content: str, parser: str = 'html.parser') -> bool:
        """
        Load HTML content into the parser.
        
        Args:
            html_content (str): Raw HTML content to parse
            parser (str): Parser to use ('html.parser', 'lxml', etc.)
            
        Returns:
            bool: True if loading successful, False otherwise
        """
        try:
            self.soup = BeautifulSoup(html_content, parser)
            return True
        except Exception as e:
            logger.error(f"Failed to load HTML content: {str(e)}")
            return False
            
    def extract_text(self, selector: Optional[str] = None, clean: bool = True) -> str:
        """
        Extract text content from HTML, optionally filtered by CSS selector.
        
        Args:
            selector (str, optional): CSS selector to filter content
            clean (bool): Whether to clean extracted text
            
        Returns:
            str: Extracted text content
        """
        if not self.soup:
            return ""
            
        try:
            if selector:
                elements = self.soup.select(selector)
                text = ' '.join(elem.get_text() for elem in elements)
            else:
                text = self.soup.get_text()
                
            if clean:
                # Remove extra whitespace and normalize
                text = re.sub(r'\s+', ' ', text).strip()
                
            return text
        except Exception as e:
            logger.error(f"Failed to extract text: {str(e)}")
            return ""
            
    def extract_links(self, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Extract all links from the HTML content.
        
        Args:
            base_url (str, optional): Base URL for resolving relative links
            
        Returns:
            List[Dict[str, str]]: List of dictionaries containing link info
        """
        if not self.soup:
            return []
            
        try:
            links = []
            for a in self.soup.find_all('a', href=True):
                href = a['href']
                if base_url:
                    href = urljoin(base_url, href)
                    
                links.append({
                    'url': href,
                    'text': a.get_text(strip=True),
                    'title': a.get('title', '')
                })
            return links
        except Exception as e:
            logger.error(f"Failed to extract links: {str(e)}")
            return []
            
    def extract_tables(self) -> List[List[List[str]]]:
        """
        Extract all tables from the HTML content.
        
        Returns:
            List[List[List[str]]]: List of tables, each containing rows of cells
        """
        if not self.soup:
            return []
            
        try:
            tables = []
            for table in self.soup.find_all('table'):
                current_table = []
                rows = table.find_all('tr')
                
                for row in rows:
                    # Handle both header and data cells
                    cells = row.find_all(['td', 'th'])
                    current_row = [cell.get_text(strip=True) for cell in cells]
                    if current_row:  # Only add non-empty rows
                        current_table.append(current_row)
                        
                if current_table:  # Only add non-empty tables
                    tables.append(current_table)
            return tables
        except Exception as e:
            logger.error(f"Failed to extract tables: {str(e)}")
            return []
            
    def extract_forms(self) -> List[Dict[str, Union[str, List[Dict[str, str]]]]]:
        """
        Extract all forms and their input fields from the HTML content.
        
        Returns:
            List[Dict]: List of dictionaries containing form information
        """
        if not self.soup:
            return []
            
        try:
            forms = []
            for form in self.soup.find_all('form'):
                current_form = {
                    'action': form.get('action', ''),
                    'method': form.get('method', 'get').upper(),
                    'fields': []
                }
                
                for input_field in form.find_all(['input', 'textarea', 'select']):
                    field_info = {
                        'type': input_field.get('type', 'text'),
                        'name': input_field.get('name', ''),
                        'id': input_field.get('id', ''),
                        'value': input_field.get('value', ''),
                        'required': input_field.has_attr('required')
                    }
                    current_form['fields'].append(field_info)
                    
                forms.append(current_form)
            return forms
        except Exception as e:
            logger.error(f"Failed to extract forms: {str(e)}")
            return []
            
    def find_elements(self, selector: str) -> List[Dict[str, str]]:
        """
        Find all elements matching a CSS selector.
        
        Args:
            selector (str): CSS selector to match elements
            
        Returns:
            List[Dict[str, str]]: List of dictionaries containing element info
        """
        if not self.soup:
            return []
            
        try:
            elements = []
            for elem in self.soup.select(selector):
                element_info = {
                    'tag': elem.name,
                    'text': elem.get_text(strip=True),
                    'html': str(elem)
                }
                # Add all attributes
                element_info.update(elem.attrs)
                elements.append(element_info)
            return elements
        except Exception as e:
            logger.error(f"Failed to find elements: {str(e)}")
            return []
            
    def clean_html(self, content: str) -> str:
        """
        Clean HTML content by removing scripts, styles, and comments.
        
        Args:
            content (str): HTML content to clean
            
        Returns:
            str: Cleaned HTML content
        """
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove unwanted tags
            for element in soup(['script', 'style', 'iframe']):
                element.decompose()
                
            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
                
            return str(soup)
        except Exception as e:
            logger.error(f"Failed to clean HTML: {str(e)}")
            return content 