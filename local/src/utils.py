import logging
import logging.handlers
from pathlib import Path
from json import dumps
import time
import traceback
from typing import Any, List, Optional, Dict
from functools import wraps
import asyncio
from .config import config
from datetime import datetime
from dataclasses import dataclass
import sys

@dataclass
class LogMetrics:
    """Enhanced metrics for logging."""
    timestamp: str
    event_type: str
    latency: float
    cache_status: str
    personality: str
    user_input: Optional[str] = None
    response_length: Optional[int] = None
    error: Optional[str] = None
    performance_metrics: Optional[Dict[str, float]] = None

class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Convert log record to dict
        log_dict = {
            "event": getattr(record, 'event_type', 'log'),
            "timestamp": datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            "message": record.getMessage()
        }
        
        # Handle data serialization
        data = getattr(record, 'data', {})
        if data:
            # Convert PosixPath to string
            serialized_data = {}
            for key, value in data.items():
                if isinstance(value, Path):
                    serialized_data[key] = str(value)
                else:
                    serialized_data[key] = value
            log_dict.update(serialized_data)
        
        # Add metrics if available
        if hasattr(record, 'metrics'):
            log_dict["metrics"] = record.metrics
        
        # Add stack trace for errors (only once)
        if record.exc_info and not log_dict.get("stack_trace"):
            log_dict["stack_trace"] = self.formatException(record.exc_info)
        
        # Format as timestamp level: { JSON }
        return f"{log_dict['timestamp']} {record.levelname}: {dumps(log_dict, indent=2)}"

class EnhancedLogger:
    """Enhanced logging system with clean, professional output."""
    
    def __init__(self):
        self.logger = logging.getLogger('ai_god')
        self.logger.setLevel(logging.INFO)
        
        # Create logs directory if it doesn't exist
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Single file handler for all logs
        file_handler = logging.handlers.RotatingFileHandler(
            'logs/ai_god.log',  # Single log file
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.INFO)
        
        # Console handler with custom formatter for clean output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)  # Show all logs in console
        
        # Custom formatter for console output
        class ConsoleFormatter(logging.Formatter):
            def format(self, record):
                # Get the original message
                message = record.getMessage()
                
                # Add prefixes based on level
                if record.levelno == logging.INFO:
                    return f"[INFO] {message}"
                elif record.levelno == logging.WARNING:
                    return f"[WARN] {message}"
                elif record.levelno == logging.ERROR:
                    return f"[ERROR] {message}"
                elif record.levelno == logging.CRITICAL:
                    return f"[CRITICAL] {message}"
                else:
                    return message
        
        # Set formatters
        file_handler.setFormatter(JsonFormatter())  # JSON for file
        console_handler.setFormatter(ConsoleFormatter())  # Clean for console
        
        # Remove any existing handlers
        self.logger.handlers = []
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Initialize metrics
        self.metrics: Dict[str, List[float]] = {
            'speech_recognition': [],
            'tts_generation': [],
            'chatgpt_response': [],
            'personality_switch': [],
            'total_processing': [],
            'wake_word_detection': [],
            'audio_playback': [],
            'cache_hits': [],
            'cache_misses': []
        }
        self.max_samples = 100
    
    def _make_log_record(self, level: int, event_type: str, data: Dict[str, Any], metrics: Optional[Dict[str, float]] = None) -> None:
        """Create a log record with structured data."""
        # Update metrics with current values if available
        if metrics:
            for name, value in metrics.items():
                if name in self.metrics:
                    self.add_metric(name, value)
        
        # Get current metrics
        current_metrics = {
            name: self._get_metric_avg(name)
            for name in self.metrics.keys()
        }
        
        extra = {
            'event_type': event_type,
            'data': data,
            'metrics': current_metrics
        }
        
        self.logger.log(level, dumps(data), extra=extra)

    def log_structured_data(self, level: int, event_type: str, data: Dict[str, Any]) -> None:
        """Log structured data with clean, professional output."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Format message based on event type
            if event_type == "User input received":
                message = f"User Input ({timestamp}): {data['text']}"
                if 'confidence' in data:
                    message += f" [Confidence: {data['confidence']:.2%}]"
                    
            elif event_type == "ChatGPT response generated":
                personality = data.get('personality', 'unknown').replace('_', ' ').title()
                response = data.get('response', '').strip()
                if response:  # Only log if there's a response
                    message = f"{personality} Response ({timestamp}): {response}"
                else:
                    return  # Skip empty responses
                
            elif event_type == "TTS generated successfully":
                voice = data.get('voice_name', 'unknown').replace('_', ' ').title()
                message = f"TTS Generated ({timestamp}): {voice}"
                if 'duration' in data:
                    message += f" [Duration: {data['duration']:.2f}s]"
                    
            elif event_type == "voice_switch_start":
                from_personality = data.get('from_personality', 'unknown').replace('_', ' ').title()
                to_personality = data.get('to_personality', 'unknown').replace('_', ' ').title()
                message = f"Voice Switch ({timestamp}): {from_personality} → {to_personality}"
                if 'time_since_last_switch' in data:
                    message += f" [Time since last switch: {data['time_since_last_switch']}]"
                    
            elif event_type == "voice_changed":
                voice = data.get('voice_name', 'unknown').replace('_', ' ').title()
                message = f"Voice Changed ({timestamp}): {voice}"
                
            elif event_type == "conversation_start":
                # Skip redundant conversation start logs
                return
                
            elif event_type == "conversation_complete":
                personality = data.get('personality', 'unknown').replace('_', ' ').title()
                latencies = data.get('latencies', {})
                message = f"Conversation Complete ({timestamp}):\n"
                message += f"Personality: {personality}\n"
                if 'user_input' in data:
                    message += f"User: {data['user_input']}\n"
                if 'response' in data:
                    message += f"AI: {data['response']}\n"
                if latencies:
                    message += "\nPerformance Metrics:\n"
                    for op, time in latencies.items():
                        if time > 0:  # Only show non-zero latencies
                            message += f"  {op.replace('_', ' ').title()}: {time:.3f}s\n"
                if 'cache_status' in data:
                    message += f"\nCache Status: {data['cache_status']}"
                    
            elif event_type == "error_occurred":
                # Skip speech recognition timeout errors
                if "listening timed out" in str(data.get('error_message', '')):
                    return
                
                message = f"Error ({timestamp}):\n"
                message += f"Type: {data.get('error_type', 'Unknown')}\n"
                message += f"Message: {data.get('error_message', 'No message')}\n"
                if 'context' in data:
                    message += "\nContext:\n"
                    for key, value in data['context'].items():
                        if key != 'stack_trace':
                            message += f"  {key}: {value}\n"
                            
            elif event_type in ["tts_request", "tts_generation_start", "tts_generation_complete", 
                              "audio_playback_start", "audio_playback_complete", "tts_cache_hit"]:
                # Skip redundant TTS status messages
                return
                
            else:
                # For other events, create a simple formatted message
                message = f"{event_type} ({timestamp}): {dumps(data, indent=2)}"
            
            # Log with proper level
            self.logger.log(level, message)
            
        except Exception as e:
            self.logger.error(f"Error in structured logging: {str(e)}")
            self.logger.info(f"Event: {event_type}, Data: {dumps(data)}")
    
    def log_startup(self) -> None:
        """Log system startup."""
        self._make_log_record(
            logging.INFO,
            "startup",
            {
                "version": "1.0.0",
                "platform": sys.platform,
                "python_version": sys.version,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )

    def log_tts_request(self, text: str, voice_id: str, cache_path: Optional[str] = None) -> None:
        """Log TTS request with cache status."""
        data = {
            "text": text,
            "voice_id": voice_id,
            "text_length": len(text),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if cache_path:
            data["cache_path"] = str(cache_path)
            data["cache_status"] = "hit"
            self.add_metric("cache_hits", 1.0)
        else:
            data["cache_status"] = "miss"
            self.add_metric("cache_misses", 1.0)
        
        self.log_structured_data(logging.INFO, "tts_request", data)

    def log_audio_playback(self, file_path: str, success: bool, error: Optional[str] = None) -> None:
        """Log audio playback attempt."""
        data = {
            "file_path": str(file_path),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "success": success
        }
        if error:
            data["error"] = error
        
        self.log_structured_data(logging.INFO, "audio_playback", data)
    
    def log_interaction(
        self,
        user_input: str,
        response: str,
        personality: str,
        latencies: Dict[str, float],
        cache_status: str = "miss"
    ) -> None:
        """Log a complete interaction with enhanced metrics."""
        metrics = LogMetrics(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            event_type="interaction",
            latency=latencies.get('total', 0),
            cache_status=cache_status,
            personality=personality,
            user_input=user_input,
            response_length=len(response),
            performance_metrics=latencies
        )
        
        self.log_structured_data(
            logging.INFO,
            "conversation_complete",
            {
                "user_input": metrics.user_input,
                "response": response,
                "personality": metrics.personality,
                "cache_status": metrics.cache_status,
                "latencies": metrics.performance_metrics,
                "response_length": metrics.response_length,
                "interaction_type": "voice" if "speech_recognition" in latencies else "text"
            }
        )
    
    def log_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        personality: str
    ) -> None:
        """Log errors with enhanced context."""
        # Extract latencies from context if available
        latencies = context.get('latencies', {})
        for name, value in latencies.items():
            if name in self.metrics:
                self.add_metric(name, value)
        
        self.log_structured_data(
            logging.ERROR,
            "error_occurred",
            {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": {
                    k: v for k, v in context.items() 
                    if k != 'stack_trace'  # Don't duplicate stack trace
                },
                "personality": personality,
                "stack_trace": traceback.format_exc()
            }
        )
    
    def _get_metric_avg(self, metric_name: str) -> float:
        """Calculate average for a specific metric."""
        if not self.metrics[metric_name]:
            return 0.0
        return sum(self.metrics[metric_name]) / len(self.metrics[metric_name])
    
    def _get_all_metrics(self) -> Dict[str, float]:
        """Get all current metric averages."""
        return {
            name: self._get_metric_avg(name)
            for name in self.metrics.keys()
        }
    
    def add_metric(self, metric_name: str, value: float) -> None:
        """Add a new metric value."""
        if metric_name in self.metrics:
            self.metrics[metric_name].append(value)
            if len(self.metrics[metric_name]) > self.max_samples:
                self.metrics[metric_name].pop(0)

# Create global logger instance
enhanced_logger = EnhancedLogger()

# Create global logger for backward compatibility
logger = enhanced_logger.logger

# Global logging functions
def add_metric(metric_name: str, value: float) -> None:
    """Add a metric value to the enhanced logger."""
    enhanced_logger.add_metric(metric_name, value)

def log_interaction(
    user_input: str,
    response: str,
    personality: str,
    latencies: Dict[str, float],
    cache_status: str = "miss"
) -> None:
    """Log a complete interaction with enhanced metrics."""
    enhanced_logger.log_interaction(
        user_input=user_input,
        response=response,
        personality=personality,
        latencies=latencies,
        cache_status=cache_status
    )

def log_error(
    error: Exception,
    context: Dict[str, Any],
    personality: str
) -> None:
    """Log errors with enhanced context."""
    enhanced_logger.log_error(error, context, personality)

def log_structured_data(level: int, event_type: str, data: Dict[str, Any]) -> None:
    """Log structured data with clean, professional output."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format message based on event type
        if event_type == "User input received":
            message = f"User Input ({timestamp}): {data['text']}"
            if 'confidence' in data:
                message += f" [Confidence: {data['confidence']:.2%}]"
                
        elif event_type == "ChatGPT response generated":
            personality = data.get('personality', 'unknown').replace('_', ' ').title()
            response = data.get('response', '').strip()
            if response:  # Only log if there's a response
                message = f"{personality} Response ({timestamp}): {response}"
            else:
                return  # Skip empty responses
                
        elif event_type == "TTS generated successfully":
            voice = data.get('voice_name', 'unknown').replace('_', ' ').title()
            message = f"TTS Generated ({timestamp}): {voice}"
            if 'duration' in data:
                message += f" [Duration: {data['duration']:.2f}s]"
                
        elif event_type == "voice_switch_start":
            from_personality = data.get('from_personality', 'unknown').replace('_', ' ').title()
            to_personality = data.get('to_personality', 'unknown').replace('_', ' ').title()
            message = f"Voice Switch ({timestamp}): {from_personality} → {to_personality}"
            if 'time_since_last_switch' in data:
                message += f" [Time since last switch: {data['time_since_last_switch']}]"
                
        elif event_type == "voice_changed":
            voice = data.get('voice_name', 'unknown').replace('_', ' ').title()
            message = f"Voice Changed ({timestamp}): {voice}"
            
        elif event_type == "conversation_start":
            # Skip redundant conversation start logs
            return
            
        elif event_type == "conversation_complete":
            personality = data.get('personality', 'unknown').replace('_', ' ').title()
            latencies = data.get('latencies', {})
            message = f"Conversation Complete ({timestamp}):\n"
            message += f"Personality: {personality}\n"
            if 'user_input' in data:
                message += f"User: {data['user_input']}\n"
            if 'response' in data:
                message += f"AI: {data['response']}\n"
            if latencies:
                message += "\nPerformance Metrics:\n"
                for op, time in latencies.items():
                    if time > 0:  # Only show non-zero latencies
                        message += f"  {op.replace('_', ' ').title()}: {time:.3f}s\n"
            if 'cache_status' in data:
                message += f"\nCache Status: {data['cache_status']}"
                
        elif event_type == "error_occurred":
            # Skip speech recognition timeout errors
            if "listening timed out" in str(data.get('error_message', '')):
                return
                
            message = f"Error ({timestamp}):\n"
            message += f"Type: {data.get('error_type', 'Unknown')}\n"
            message += f"Message: {data.get('error_message', 'No message')}\n"
            if 'context' in data:
                message += "\nContext:\n"
                for key, value in data['context'].items():
                    if key != 'stack_trace':
                        message += f"  {key}: {value}\n"
                        
        elif event_type in ["tts_request", "tts_generation_start", "tts_generation_complete", 
                          "audio_playback_start", "audio_playback_complete", "tts_cache_hit"]:
            # Skip redundant TTS status messages
            return
            
        else:
            # For other events, create a simple formatted message
            message = f"{event_type} ({timestamp}): {dumps(data, indent=2)}"
        
        # Log with proper level
        enhanced_logger.log_structured_data(level, event_type, data)
            
    except Exception as e:
        enhanced_logger.log_error(e, {"event_type": event_type, "data": data}, "system")

def log_timing(func):
    """Decorator to log function execution time."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"{func.__name__} took {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{func.__name__} failed after {duration:.2f}s: {str(e)}")
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"{func.__name__} took {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{func.__name__} failed after {duration:.2f}s: {str(e)}")
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

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

# Export the cache instance and logging functions
__all__ = [
    'logger', 
    'log_timing', 
    'log_structured_data', 
    'log_interaction', 
    'log_error',
    'add_metric',
    'cache', 
    'get_cached_tts', 
    'set_cached_tts',
    'get_cached_response', 
    'set_cached_response',
    'get_cached_entertainment', 
    'set_cached_entertainment',
    'enhanced_logger'
] 