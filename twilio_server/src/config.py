"""Configuration management for the AI God project."""

import os
from dataclasses import dataclass, field
from typing import List, Dict
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class TwilioConfig:
    """Twilio configuration settings."""
    ACCOUNT_SID: str = field(default_factory=lambda: os.getenv("TWILIO_ACCOUNT_SID", ""))
    AUTH_TOKEN: str = field(default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN", ""))
    TRUNK_SID: str = field(default_factory=lambda: os.getenv("TWILIO_TRUNK_SID", ""))
    VOICE_URL: str = field(default_factory=lambda: os.getenv("VOICE_URL", "https://your-domain.com/voice"))

@dataclass
class VoiceConfig:
    """Voice configuration settings."""
    VOICE_NIKKI: str = "WoGJO0bsQ5xvIQwKIRtC"  # Nikki voice ID
    VOICE_TOM: str = "OWXgblXycW2yI83Vj3xf"    # Tom voice ID
    STABILITY: float = 0.5
    SIMILARITY_BOOST: float = 0.75

@dataclass
class SpeechConfig:
    """Speech recognition configuration settings."""
    WAKE_UP_WORDS: List[str] = field(default_factory=lambda: [
        "hey god", "okay god", "yo god", "wake up", "hey tom", "hey nikki"
    ])
    INTERRUPT_KEYWORDS: List[str] = field(default_factory=lambda: ["stop", "quiet"])
    TIMEOUT: int = 10
    PHRASE_TIME_LIMIT: int = 15
    ENERGY_THRESHOLD: int = 150
    PAUSE_THRESHOLD: float = 0.5
    DYNAMIC_ENERGY_THRESHOLD: bool = True
    DYNAMIC_ENERGY_ADJUSTMENT_DAMPING: float = 0.15
    DYNAMIC_ENERGY_RATIO: float = 1.5
    AMBIENT_NOISE_ADJUSTMENT: float = 1.2
    MIN_PHRASE_DURATION: float = 0.2
    MAX_PHRASE_DURATION: float = 5.0
    ADJUST_FOR_AMBIENT_NOISE: bool = True
    ADJUST_FOR_AMBIENT_NOISE_DURATION: float = 0.5

@dataclass
class APIConfig:
    """API configuration settings."""
    OPENAI_API_KEY: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    ELEVENLABS_API_KEY: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    OPENAI_MAX_TOKENS: int = 150
    OPENAI_TEMPERATURE: float = 0.7
    ELEVENLABS_STREAM_URL: str = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"

@dataclass
class PathConfig:
    """Path configuration settings."""
    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    CACHE_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent / "cache")
    LOG_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent / "logs")

@dataclass
class Config:
    """Main configuration class."""
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)
    api: APIConfig = field(default_factory=APIConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    twilio: TwilioConfig = field(default_factory=TwilioConfig)

    def __post_init__(self):
        """Create necessary directories after initialization."""
        self.paths.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.paths.LOG_DIR.mkdir(parents=True, exist_ok=True)

# Global config instance
config = Config() 