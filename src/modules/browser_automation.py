import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from typing import Optional, Dict, List
import logging
from src.utils.logging import get_logger
import os
from pathlib import Path

logger = get_logger(__name__)

class BrowserAutomationError(Exception):
    """Custom exception for BrowserAutomationModule errors"""
    pass

class BrowserAutomationModule:
    """Module for handling browser automation tasks"""
    
    def __init__(self, headless: bool = True):
        """
        Initialize browser automation module
        
        Args:
            headless: Whether to run browser in headless mode
        """
        self.logger = logger
        self.headless = headless
        self.driver = None
        self._setup_driver()
    
    def _setup_driver(self):
        """Set up the Selenium WebDriver"""
        try:
            options = uc.ChromeOptions()
            if self.headless:
                options.add_argument('--headless')
                options.add_argument('--disable-gpu')  # Required for headless on some systems
            
            # Add additional options for better compatibility
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            # Set up download preferences
            prefs = {
                "download.default_directory": str(Path.home() / 'Downloads'),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            options.add_experimental_option("prefs", prefs)
            
            # Get the absolute path to the local chromedriver
            driver_path = str(Path(__file__).parent.parent.parent / 'drivers' / 'chromedriver')
            
            # Initialize the Chrome driver
            self.driver = uc.Chrome(
                options=options,
                driver_executable_path=driver_path,
                browser_executable_path='/usr/bin/chromium-browser'
            )
            self.driver.implicitly_wait(10)  # Set implicit wait time
            self.logger.info("Browser driver initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize browser driver: {str(e)}")
            raise BrowserAutomationError(f"Browser driver initialization failed: {str(e)}")
    
    def navigate_to(self, url: str) -> bool:
        """
        Navigate to a specific URL
        
        Args:
            url: The URL to navigate to
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.driver.get(url)
            return True
        except Exception as e:
            self.logger.error(f"Failed to navigate to {url}: {str(e)}")
            raise BrowserAutomationError(f"Navigation failed: {str(e)}")
    
    def find_element(self, by: str, value: str, timeout: int = 10):
        """
        Find an element on the page
        
        Args:
            by: Type of selector (id, class_name, css_selector, etc.)
            value: Value to search for
            timeout: How long to wait for element
            
        Returns:
            WebElement if found
            
        Raises:
            BrowserAutomationError if element not found
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((getattr(By, by.upper()), value))
            )
            return element
        except TimeoutException:
            self.logger.error(f"Element not found: {by}={value}")
            raise BrowserAutomationError(f"Element not found: {by}={value}")
    
    def click_element(self, by: str, value: str, timeout: int = 10) -> bool:
        """
        Click an element on the page
        
        Args:
            by: Type of selector
            value: Value to search for
            timeout: How long to wait for element
            
        Returns:
            bool: True if successful
        """
        try:
            element = self.find_element(by, value, timeout)
            element.click()
            return True
        except Exception as e:
            self.logger.error(f"Failed to click element {by}={value}: {str(e)}")
            raise BrowserAutomationError(f"Click failed: {str(e)}")
    
    def fill_form(self, form_data: Dict[str, str]) -> bool:
        """
        Fill a form with provided data
        
        Args:
            form_data: Dictionary of element identifiers and values
            
        Returns:
            bool: True if successful
        """
        try:
            for identifier, value in form_data.items():
                element = self.find_element('name', identifier)
                element.clear()
                element.send_keys(value)
            return True
        except Exception as e:
            self.logger.error(f"Failed to fill form: {str(e)}")
            raise BrowserAutomationError(f"Form fill failed: {str(e)}")
    
    def get_page_source(self) -> str:
        """Get current page HTML source"""
        return self.driver.page_source
    
    def take_screenshot(self, filename: str) -> bool:
        """
        Take a screenshot of the current page
        
        Args:
            filename: Where to save the screenshot
            
        Returns:
            bool: True if successful
        """
        try:
            self.driver.save_screenshot(filename)
            return True
        except Exception as e:
            self.logger.error(f"Failed to take screenshot: {str(e)}")
            raise BrowserAutomationError(f"Screenshot failed: {str(e)}")
    
    def close(self):
        """Close the browser"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except Exception as e:
                self.logger.error(f"Failed to close browser: {str(e)}")
    
    def __del__(self):
        """Ensure browser is closed on object destruction"""
        self.close() 