from setuptools import setup, find_packages

setup(
    name="office-agent",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "pytest",
        "pytest-asyncio",
        "aiohttp",  # For async HTTP calls
    ],
) 