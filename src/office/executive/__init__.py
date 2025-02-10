"""
The executive package contains high-level decision making and coordination components.
This includes the CEO, management team, and other executive-level modules.
"""

from .ceo import CEO
from .gpt_client import GPTClient

__all__ = ['CEO', 'GPTClient'] 