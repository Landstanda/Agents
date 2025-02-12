import pytest
from src.modules.browser_automation import BrowserAutomationModule, BrowserAutomationError
import os
from pathlib import Path

@pytest.fixture
def browser():
    browser = BrowserAutomationModule(headless=True)
    yield browser
    browser.close()

def test_init():
    """Test module initialization"""
    browser = BrowserAutomationModule(headless=True)
    assert browser.driver is not None
    browser.close()

def test_navigate_to(browser):
    """Test navigation to a URL"""
    result = browser.navigate_to('https://www.example.com')
    assert result is True
    assert 'Example Domain' in browser.driver.title

def test_find_element(browser):
    """Test finding an element on the page"""
    browser.navigate_to('https://www.example.com')
    element = browser.find_element('tag_name', 'h1')
    assert element is not None
    assert element.text == 'Example Domain'

def test_click_element(browser):
    """Test clicking an element"""
    browser.navigate_to('https://www.example.com')
    # The example.com page has a link to iana.org
    result = browser.click_element('tag_name', 'a')
    assert result is True

def test_take_screenshot(browser, tmp_path):
    """Test taking a screenshot"""
    browser.navigate_to('https://www.example.com')
    screenshot_path = tmp_path / 'test_screenshot.png'
    result = browser.take_screenshot(str(screenshot_path))
    assert result is True
    assert screenshot_path.exists()

def test_get_page_source(browser):
    """Test getting page source"""
    browser.navigate_to('https://www.example.com')
    source = browser.get_page_source()
    assert isinstance(source, str)
    assert 'Example Domain' in source

def test_nonexistent_element(browser):
    """Test handling of non-existent element"""
    browser.navigate_to('https://www.example.com')
    with pytest.raises(BrowserAutomationError):
        browser.find_element('id', 'nonexistent-element')

def test_invalid_url(browser):
    """Test handling of invalid URL"""
    with pytest.raises(BrowserAutomationError):
        browser.navigate_to('https://thiswebsitedoesnotexist.com.invalid') 