from setuptools import setup, find_packages

setup(
    name="office-agent",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        line.strip()
        for line in open("requirements/base.txt")
        if line.strip() and not line.startswith("#")
    ],
    extras_require={
        "dev": [
            line.strip()
            for line in open("requirements/dev.txt")
            if line.strip() and not line.startswith("#") and not line.startswith("-r")
        ],
        "prod": [
            line.strip()
            for line in open("requirements/prod.txt")
            if line.strip() and not line.startswith("#") and not line.startswith("-r")
        ],
    },
) 