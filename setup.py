from setuptools import setup, find_packages

setup(
    name="office_assistant",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "slack_sdk",
        "pytest",
        "pytest-asyncio",
        "aiohttp",
        "pyyaml",
        "python-dotenv",
        "openai",
    ],
    python_requires=">=3.8",
) 