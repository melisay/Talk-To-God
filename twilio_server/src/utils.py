import logging
import logging.handlers
from pathlib import Path
from json import dumps
import time
from typing import Any, List, Optional, Dict  # whatever other typing names you need
from functools import wraps
import asyncio
from .config import config
from datetime import datetime

def setup_logging() -> logging.Logger:
    """Set up logging with rotation and proper formatting."""
    # Get the root logger and remove any existing handlers
    logger = logging.getLogger("ai_god")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # Prevent propagation to root logger
    
    # Create formatters with better readability
    file_formatter = logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # File handler with rotation
    log_file = config.paths.LOG_DIR / "ai_god.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler with cleaner output
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Global logger instance
logger = setup_logging()

def log_structured_data(level: int, event: str, data: dict) -> None:
    """Log structured data in a consistent format."""
    # Format the log message
    log_msg = {
        "event": event,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        **data
    }
    
    # Convert to pretty JSON for readability
    formatted_msg = dumps(log_msg, indent=2)
    
    # Format as timestamp level: { JSON }
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    level_name = "INFO" if level == logging.INFO else "ERROR" if level == logging.ERROR else "WARNING" if level == logging.WARNING else "DEBUG"
    final_msg = f"{timestamp} {level_name}: {formatted_msg}"
    
    # Log with appropriate level
    if level == logging.DEBUG:
        logger.debug(final_msg)
    elif level == logging.INFO:
        logger.info(final_msg)
    elif level == logging.WARNING:
        logger.warning(final_msg)
    elif level == logging.ERROR:
        logger.error(final_msg)
    else:
        logger.info(final_msg)

def log_timing(func):
    """Decorator to log function timing."""
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        duration = time.time() - start_time
        
        # Log timing in structured format
        log_structured_data(
            logging.DEBUG,
            "function_timing",
            {
                "function": func.__name__,
                "duration": f"{duration:.2f}s"
            }
        )
        return result
    return wrapper

class Cache:
    """LRU Cache implementation with size limit and TTL."""
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl  # Time to live in seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_order: List[str] = []
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache and update access order."""
        if key in self.cache:
            # Check if item has expired
            if time.time() - self.cache[key]['timestamp'] > self.ttl:
                self._remove(key)
                return None
                
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]['value']
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set item in cache with LRU eviction and TTL."""
        if key in self.cache:
            self.access_order.remove(key)
        elif len(self.cache) >= self.max_size:
            oldest_key = self.access_order.pop(0)
            del self.cache[oldest_key]
        
        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
        self.access_order.append(key)
    
    def _remove(self, key: str) -> None:
        """Remove item from cache."""
        if key in self.cache:
            del self.cache[key]
            self.access_order.remove(key)
    
    def clear(self) -> None:
        """Clear the cache."""
        self.cache.clear()
        self.access_order.clear()
    
    def cleanup_expired(self) -> None:
        """Remove expired items from cache."""
        current_time = time.time()
        expired_keys = [
            key for key, data in self.cache.items()
            if current_time - data['timestamp'] > self.ttl
        ]
        for key in expired_keys:
            self._remove(key)

# Global cache instances with different TTLs
tts_cache = Cache(max_size=50, ttl=86400)  # 24 hours for TTS
response_cache = Cache(max_size=100, ttl=3600)  # 1 hour for responses
entertainment_cache = Cache(max_size=200, ttl=7200)  # 2 hours for entertainment

def get_cached_tts(text: str, voice_id: str) -> Optional[str]:
    """Get cached TTS audio file path."""
    cache_key = f"tts_{voice_id}_{hash(text)}"
    return tts_cache.get(cache_key)

def set_cached_tts(text: str, voice_id: str, file_path: str) -> None:
    """Cache TTS audio file path."""
    cache_key = f"tts_{voice_id}_{hash(text)}"
    tts_cache.set(cache_key, file_path)

def get_cached_response(text: str, personality: str) -> Optional[str]:
    """Get cached AI response."""
    cache_key = f"response_{personality}_{hash(text)}"
    return response_cache.get(cache_key)

def set_cached_response(text: str, personality: str, response: str) -> None:
    """Cache AI response."""
    cache_key = f"response_{personality}_{hash(text)}"
    response_cache.set(cache_key, response)

def get_cached_entertainment(category: str, item: str) -> Optional[Any]:
    """Get cached entertainment content."""
    cache_key = f"ent_{category}_{item}"
    return entertainment_cache.get(cache_key)

def set_cached_entertainment(category: str, item: str, content: Any) -> None:
    """Cache entertainment content."""
    cache_key = f"ent_{category}_{item}"
    entertainment_cache.set(cache_key, content)

# Performance monitoring
class PerformanceStats:
    def __init__(self):
        self.stats: Dict[str, List[float]] = {
            'speech_recognition': [],
            'tts_generation': [],
            'chatgpt_response': [],
            'entertainment': [],
            'total_processing': []
        }
        self.max_samples = 100
    
    def add_timing(self, operation: str, duration: float) -> None:
        """Add timing data for an operation."""
        if operation in self.stats:
            self.stats[operation].append(duration)
            if len(self.stats[operation]) > self.max_samples:
                self.stats[operation].pop(0)
    
    def get_average(self, operation: str) -> float:
        """Get average duration for an operation."""
        if operation in self.stats and self.stats[operation]:
            return sum(self.stats[operation]) / len(self.stats[operation])
        return 0.0
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all operations."""
        return {
            op: {
                'avg': self.get_average(op),
                'min': min(times) if times else 0,
                'max': max(times) if times else 0,
                'samples': len(times)
            }
            for op, times in self.stats.items()
        }

# Global performance stats instance
performance_stats = PerformanceStats()

# Global cache instance for chat responses
cache = Cache(max_size=100, ttl=3600)  # 1 hour TTL for chat responses

# Export the cache instance
__all__ = ['logger', 'log_timing', 'log_structured_data', 'cache', 
           'get_cached_tts', 'set_cached_tts',
           'get_cached_response', 'set_cached_response',
           'get_cached_entertainment', 'set_cached_entertainment'] 