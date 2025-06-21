"""Configuration settings optimized for Raspberry Pi."""
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class Paths:
    """Path configurations optimized for Raspberry Pi."""
    BASE_DIR: Path = Path(__file__).parent.parent
    LOG_DIR: Path = BASE_DIR / "logs"
    CACHE_DIR: Path = BASE_DIR / "cache"
    TTS_CACHE_DIR: Path = CACHE_DIR / "tts"
    USER_DATA_DIR: Path = BASE_DIR / "user_data"
    MAX_LOG_SIZE: int = 5 * 1024 * 1024  # 5MB for Raspberry Pi
    MAX_LOG_BACKUPS: int = 3  # Reduced number of backups

@dataclass
class Speech:
    """Speech recognition settings optimized for Raspberry Pi."""
    WAKE_UP_WORDS: List[str] = ["hey tom", "hey nikki", "wake up"]
    ENERGY_THRESHOLD: int = 300  # Lower threshold for better wake word detection
    PAUSE_THRESHOLD: float = 0.6  # Shorter pause threshold
    PHRASE_TIMEOUT: float = 2.0  # Shorter timeout
    AMBIENT_NOISE_ADJUSTMENT: float = 1.2  # More aggressive noise adjustment
    DYNAMIC_ENERGY_THRESHOLD: bool = True
    DYNAMIC_ENERGY_ADJUSTMENT_DAMPING: float = 0.15
    DYNAMIC_ENERGY_RATIO: float = 1.5

@dataclass
class Voice:
    """Voice settings optimized for Raspberry Pi."""
    VOICE_TOM: str = "OWXgblXycW2yI83Vj3xf"    # Tom voice ID
    VOICE_NIKKI: str = "WoGJO0bsQ5xvIQwKIRtC"  # Nikki voice ID
    SPEAKING_RATE: float = 1.0
    PITCH: float = 0.0
    VOLUME: float = 1.0
    SAMPLE_RATE: int = 16000  # Lower sample rate for better performance

@dataclass
class Cache:
    """Cache settings optimized for Raspberry Pi."""
    TTS_CACHE_SIZE: int = 25  # Reduced cache size
    TTS_CACHE_TTL: int = 43200  # 12 hours
    RESPONSE_CACHE_SIZE: int = 50  # Reduced cache size
    RESPONSE_CACHE_TTL: int = 1800  # 30 minutes
    ENTERTAINMENT_CACHE_SIZE: int = 100  # Reduced cache size
    ENTERTAINMENT_CACHE_TTL: int = 3600  # 1 hour
    CLEANUP_INTERVAL: int = 300  # 5 minutes

@dataclass
class Performance:
    """Performance settings optimized for Raspberry Pi."""
    MAX_CONCURRENT_REQUESTS: int = 2  # Reduced concurrent requests
    REQUEST_TIMEOUT: float = 10.0  # Shorter timeout
    MAX_RETRIES: int = 2  # Fewer retries
    RETRY_DELAY: float = 1.0
    BATCH_SIZE: int = 1  # No batching on Raspberry Pi
    USE_UVLOOP: bool = True
    LOG_LEVEL: str = "INFO"  # Reduced logging
    ENABLE_PERFORMANCE_MONITORING: bool = True
    PERFORMANCE_SAMPLE_SIZE: int = 50  # Reduced sample size

@dataclass
class Config:
    """Main configuration class for Raspberry Pi."""
    paths: Paths = Paths()
    speech: Speech = Speech()
    voice: Voice = Voice()
    cache: Cache = Cache()
    performance: Performance = Performance()
    
    def __post_init__(self):
        """Create necessary directories."""
        self.paths.LOG_DIR.mkdir(exist_ok=True)
        self.paths.CACHE_DIR.mkdir(exist_ok=True)
        self.paths.TTS_CACHE_DIR.mkdir(exist_ok=True)
        self.paths.USER_DATA_DIR.mkdir(exist_ok=True)

# Global config instance
config = Config() 