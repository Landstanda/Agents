from setuptools import setup, find_packages

setup(
    name="ai_secretary",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pyyaml",
        "google-auth-oauthlib",
        "google-auth",
        "google-api-python-client",
    ],
    python_requires=">=3.8",
) 