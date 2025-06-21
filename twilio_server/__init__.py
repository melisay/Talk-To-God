"""
AI God Project - Twilio Version Package
This package contains the Twilio version of the AI God system.
"""

from .server_main import app, initialize_application
from .src.sounds import SoundManager

__all__ = ['app', 'initialize_application', 'SoundManager'] 