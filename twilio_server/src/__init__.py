"""AI God Project - A modular voice assistant system."""

from .chat import ChatManager, chat_manager
from .config import Config, config
from .personality import PersonalityManager, personality_manager
from .speech import SpeechRecognizer, speech_recognizer
from .tts import TTSManager, tts_manager
from .utils import logger, log_timing, log_structured_data, cache
from .user import UserManager, user_manager
from .performance import performance_monitor, monitor_operation
from .entertainment import entertainment_manager
from .coordinator import InteractionCoordinator, interaction_coordinator

__version__ = "1.0.0"
__author__ = "AI God Project Team"

__all__ = [
    "ChatManager",
    "chat_manager",
    "Config",
    "config",
    "PersonalityManager",
    "personality_manager",
    "SpeechRecognizer",
    "speech_recognizer",
    "TTSManager",
    "tts_manager",
    "UserManager",
    "user_manager",
    "logger",
    "log_timing",
    "log_structured_data",
    "cache",
    "performance_monitor",
    "monitor_operation",
    "entertainment_manager",
    "InteractionCoordinator",
    "interaction_coordinator"
] 