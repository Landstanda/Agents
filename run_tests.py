#!/usr/bin/env python3

import pytest
import sys
from src.office.utils.logging_config import setup_logging

def main():
    """Run the test suite with proper logging configuration."""
    # Setup logging
    setup_logging()
    
    # Run pytest with command line arguments
    args = sys.argv[1:] if len(sys.argv) > 1 else ['tests/']
    exit_code = pytest.main(args)
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main()) 