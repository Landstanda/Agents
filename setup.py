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
        "google-api-python-client",
        "google-auth-httplib2",
        "google-auth-oauthlib",
        "pytest-mock",
    ],
    python_requires=">=3.8",
) 