from setuptools import setup, find_packages

setup(
    name="agents",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'aiohttp>=3.8.0',
        'beautifulsoup4>=4.9.3',
    ],
) 