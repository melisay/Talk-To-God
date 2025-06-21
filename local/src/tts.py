import asyncio
from hashlib import sha256
import time
from datetime import datetime, timezone
from pathlib import Path
import logging
import shlex
import subprocess
from typing import Optional, Tuple, Dict, Any
import httpx
import elevenlabs
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import config
from .utils import logger, log_timing, log_structured_data
import sys

class TTSManager:
    def __init__(self):
        # Use a persistent HTTP client with connection pooling
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        self.eleven_client = elevenlabs.ElevenLabs(
            api_key=config.api.ELEVENLABS_API_KEY,
            environment=elevenlabs.ElevenLabsEnvironment.PRODUCTION_US
        )
        self.current_voice = config.voice.VOICE_NIKKI
        self.voice_names = {
            config.voice.VOICE_NIKKI: "Nikki",
            config.voice.VOICE_TOM: "Tom"
        }
        self._available_voices = set()  # Track available voices
        self._initialize_voices()
        self.current_language = "en-US"  # Default language
        self._is_playing_audio = False
        self._audio_cache: Dict[str, Path] = {}  # Memory cache for faster lookups
        
        # Create cache directory if it doesn't exist
        config.paths.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()
    
    def _initialize_voices(self) -> None:
        """Initialize available voices from config."""
        self._available_voices = {
            config.voice.VOICE_NIKKI,
            config.voice.VOICE_TOM
        }
        logger.info(f"Initialized available voices: {self._available_voices}")
    
    def verify_voice(self, voice_id: str) -> bool:
        """Verify if a voice ID is valid and available."""
        if not voice_id:
            logger.warning("Empty voice ID provided")
            return False
            
        is_valid = voice_id in self._available_voices
        if not is_valid:
            logger.warning(f"Invalid voice ID: {voice_id}")
        return is_valid
    
    def get_voice_name(self, voice_id: str) -> str:
        """Get human-readable voice name from ID."""
        return self.voice_names.get(voice_id, "Unknown Voice")
    
    def set_voice(self, voice_id: str, skip_logging: bool = False) -> None:
        """Set the current voice with validation."""
        if not self.verify_voice(voice_id):
            raise ValueError(f"Invalid voice ID: {voice_id}")
            
        # Skip if voice hasn't changed
        if voice_id == self.current_voice:
            return
            
        self.current_voice = voice_id
        
        # Only log if not skipped
        if not skip_logging:
            voice_name = self.get_voice_name(voice_id)
            logger.info(f"Voice set to: {voice_name}")
            log_structured_data(
                logging.INFO,
                "voice_changed",
                {
                    "voice_id": voice_id,
                    "voice_name": voice_name,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                }
            )
    
    def set_language(self, language: str) -> None:
        """Set the current language for TTS."""
        valid_languages = ["en-US"]
        if language not in valid_languages:
            raise ValueError(f"Invalid language: {language}. Must be one of {valid_languages}")
        
        self.current_language = language
        logger.info(f"Language set to: {language}")
        log_structured_data(
            logging.INFO,
            "language_changed",
            {
                "language": language,
                "voice_id": self.current_voice,
                "voice_name": self.get_voice_name(self.current_voice),
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            }
        )
    
    def _get_cache_key(self, text: str) -> str:
        """Generate a secure cache key for a given text."""
        return sha256(f"{text}_{self.current_voice}_{self.current_language}".encode()).hexdigest()
    
    def _get_cache_path(self, text: str) -> Path:
        """Get the cache file path for a given text."""
        key = self._get_cache_key(text)
        return config.paths.CACHE_DIR / f"cached_{key}.mp3"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=5),  # Faster retry
        reraise=True
    )
    @log_timing
    async def _generate_tts(
        self,
        text: str,
        output_path: Path,
        play: bool = False
    ) -> Tuple[Optional[Path], float]:
        """Generate TTS with retry logic and language support."""
        url = config.api.ELEVENLABS_STREAM_URL.format(voice_id=self.current_voice)
        if config.api.ELEVENLABS_STREAM_URL:
            url += "?optimize_streaming_latency=4"  # Highest optimization level
        
        headers = {
            "xi-api-key": config.api.ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        
        # Always use monolingual model for English
        model_id = "eleven_monolingual_v1"
        
        data = {
            "text": text,
            "voice_settings": {
                "stability": config.voice.STABILITY,
                "similarity_boost": config.voice.SIMILARITY_BOOST
            },
            "model_id": model_id
        }
        
        try:
            start_time = time.time()
            resp = await self.http_client.post(url, json=data, headers=headers)
            resp.raise_for_status()
            
            # Use async file writing
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)
            
            duration = time.time() - start_time
            
            # Add to memory cache
            self._audio_cache[self._get_cache_key(text)] = output_path
            
            log_structured_data(
                logging.DEBUG,
                "TTS generation successful",
                {
                    "duration": duration,
                    "text_length": len(text),
                    "language": self.current_language,
                    "model": model_id,
                    "voice": self.get_voice_name(self.current_voice)
                }
            )
            
            if play:
                await self._play_audio(output_path)
            
            return output_path, duration
            
        except httpx.HTTPError as e:
            logger.error(f"TTS HTTP error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"TTS generation error: {str(e)}")
            raise
    
    async def _play_audio(self, file_path: Path) -> None:
        """Play audio file with enhanced security and logging."""
        voice_name = self.get_voice_name(self.current_voice)
        
        # Set playing state
        self._is_playing_audio = True
        
        try:
            log_structured_data(
                logging.INFO,
                "audio_playback_start",
                {
                    "voice_name": voice_name,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                }
            )
            
            # Validate file path to prevent path traversal
            safe_path = file_path.resolve()
            if not safe_path.is_file() or not str(safe_path).startswith(str(config.paths.CACHE_DIR.resolve())):
                raise ValueError(f"Invalid audio file path: {file_path}")
            
            # Play audio using appropriate method with proper argument handling
            if sys.platform == "darwin":  # macOS
                process = await asyncio.create_subprocess_exec(
                    "afplay", str(safe_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.wait()
            else:  # Linux/Windows
                process = await asyncio.create_subprocess_exec(
                    "mpg123", str(safe_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.wait()
            
            log_structured_data(
                logging.INFO,
                "audio_playback_complete",
                {
                    "voice_name": voice_name,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                }
            )
            
        except Exception as e:
            log_structured_data(
                logging.ERROR,
                "audio_playback_error",
                {
                    "error": str(e),
                    "voice_name": voice_name,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                }
            )
            raise
            
        finally:
            self._is_playing_audio = False
    
    @log_timing
    async def generate_tts(
        self,
        text: str,
        play: bool = True,
        force_regenerate: bool = False
    ) -> Optional[Path]:
        """Generate or retrieve TTS for given text with optimized caching."""
        if not text:
            log_structured_data(
                logging.WARNING,
                "tts_empty_text",
                {"timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}
            )
            return None
            
        cache_key = self._get_cache_key(text)
        cache_path = self._get_cache_path(text)
        voice_name = self.get_voice_name(self.current_voice)
        
        # Sanitize text for logging
        sanitized_text = text.replace('\n', ' ').replace('\r', ' ')
        
        log_structured_data(
            logging.INFO,
            "tts_request",
            {
                "message": "Assistant Said",
                "voice_name": voice_name,
                "text_length": len(text),
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            }
        )
        
        # Check memory cache first (fastest)
        if not force_regenerate and cache_key in self._audio_cache:
            cached_path = self._audio_cache[cache_key]
            if cached_path.exists():
                log_structured_data(
                    logging.INFO,
                    "tts_memory_cache_hit",
                    {
                        "message": "Assistant Said (memory cached)",
                        "voice_name": voice_name,
                        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    }
                )
                if play:
                    try:
                        await self._play_audio(cached_path)
                    except Exception as e:
                        logger.error(f"Audio playback error: {e}")
                return cached_path
        
        # Check disk cache next
        if not force_regenerate and cache_path.exists():
            # Add to memory cache for future lookups
            self._audio_cache[cache_key] = cache_path
            
            log_structured_data(
                logging.INFO,
                "tts_disk_cache_hit",
                {
                    "message": "Assistant Said (disk cached)",
                    "voice_name": voice_name,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                }
            )
            if play:
                try:
                    await self._play_audio(cache_path)
                except Exception as e:
                    logger.error(f"Audio playback error: {e}")
                    return None
            return cache_path
        
        # Generate new TTS
        try:
            log_structured_data(
                logging.INFO,
                "tts_generation_start",
                {
                    "message": "Assistant Said (generating)",
                    "voice_name": voice_name,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                }
            )
            
            # Use existing HTTP client for better connection reuse
            result, duration = await self._generate_tts(text, cache_path, play)
            
            log_structured_data(
                logging.INFO,
                "tts_generation_complete",
                {
                    "message": "Assistant Said (generated)",
                    "duration": duration,
                    "voice_name": voice_name,
                    "text_length": len(text),
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                }
            )
            return result
        except Exception as e:
            log_structured_data(
                logging.ERROR,
                "tts_generation_error",
                {
                    "error": str(e),
                    "message": "Assistant Said (generation failed)",
                    "voice_name": voice_name,
                    "text_length": len(text),
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                }
            )
            return None

# Global TTS manager instance
tts_manager = TTSManager()