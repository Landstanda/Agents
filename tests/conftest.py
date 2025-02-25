import pytest
import asyncio
from typing import Generator
from src.core.agent import BaseAgent

def pytest_configure(config):
    """Configure pytest with asyncio markers"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def agent(event_loop):
    """Create and initialize a BaseAgent instance"""
    agent = BaseAgent()
    await agent.initialize()
    return agent 