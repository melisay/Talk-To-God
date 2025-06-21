import asyncio
import httpx
from hashlib import md5
import time
import logging
from pathlib import Path
from typing import Optional, Tuple
import elevenlabs
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import config
from .utils import logger, log_timing, log_structured_data

class TTSManager:
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.eleven_client = elevenlabs.ElevenLabs(
            api_key=config.api.ELEVENLABS_API_KEY,
            environment=elevenlabs.ElevenLabsEnvironment.PRODUCTION_US
        )
        self.current_voice = config.voice.VOICE_NIKKI
        self.voice_names = {
            config.voice.VOICE_NIKKI: "Nikki",
            config.voice.VOICE_TOM: "Major Tom"
        }
        self.current_language = "en-US"  # Default language
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()
    
    def get_voice_name(self, voice_id: str) -> str:
        """Get human-readable voice name from ID."""
        return self.voice_names.get(voice_id, "Unknown Voice")
    
    def set_voice(self, voice_id: str) -> None:
        """Set the current voice."""
        if not self.verify_voice(voice_id):
            raise ValueError(f"Invalid voice ID: {voice_id}")
        self.current_voice = voice_id
        voice_name = self.get_voice_name(voice_id)
        logger.info(f"Voice set to: {voice_name}")
    
    def set_language(self, language: str) -> None:
        """Set the current language for TTS."""
        if language not in ["en-US"]:
            raise ValueError(f"Unsupported language: {language}")
        self.current_language = language
        logger.info(f"Language set to: {language}")
    
    def _get_cache_path(self, text: str) -> Path:
        """Get the cache file path for a given text."""
        key = md5(f"{text}_{self.current_voice}_{self.current_language}".encode()).hexdigest()
        # Save to twilio_server/static/cached_responses instead of project root's static/cached_responses
        static_dir = Path(__file__).parent.parent / "static"
        cached_responses_dir = static_dir / "cached_responses"
        cached_responses_dir.mkdir(exist_ok=True)
        return cached_responses_dir / f"cached_{key}.mp3"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    @log_timing
    async def _generate_tts(
        self,
        text: str,
        output_path: Path,
        play: bool = False
    ) -> Tuple[Optional[Path], float]:
        """Generate TTS with retry logic."""
        url = config.api.ELEVENLABS_STREAM_URL.format(voice_id=self.current_voice)
        if config.api.ELEVENLABS_STREAM_URL:
            url += "?optimize_streaming_latency=3"
        
        headers = {
            "xi-api-key": config.api.ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        
        data = {
            "text": text,
            "voice_settings": {
                "stability": config.voice.STABILITY,
                "similarity_boost": config.voice.SIMILARITY_BOOST
            },
            "model_id": "eleven_monolingual_v1"
        }
        
        try:
            start_time = time.time()
            resp = await self.http_client.post(url, json=data, headers=headers)
            resp.raise_for_status()
            
            with open(output_path, "wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)
            
            duration = time.time() - start_time
            log_structured_data(
                logging.DEBUG,
                "TTS generation successful",
                {"duration": duration, "text_length": len(text)}
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
        """Play audio file using afplay (macOS native player) with proper cleanup."""
        try:
            play_start = time.time()
            log_structured_data(
                logging.INFO,
                "audio_playback_start",
                {
                    "timestamp": time.strftime("%H:%M:%S"),
                    "file": file_path.name
                }
            )
            
            if not file_path.exists():
                logger.error(f"Audio file does not exist: {file_path}")
                raise FileNotFoundError(f"Audio file not found: {file_path}")
                
            # Create new process with timeout
            proc = await asyncio.create_subprocess_shell(
                f"afplay {file_path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                # Wait for process with timeout
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
                playback_duration = time.time() - play_start
                
                if stderr:
                    logger.error(f"Audio playback stderr: {stderr.decode()}")
                if proc.returncode != 0:
                    logger.error(f"Audio playback failed with return code: {proc.returncode}")
                    raise RuntimeError(f"Audio playback failed: {stderr.decode() if stderr else 'Unknown error'}")
                
                log_structured_data(
                    logging.INFO,
                    "audio_playback_complete",
                    {
                        "timestamp": time.strftime("%H:%M:%S"),
                        "file": file_path.name,
                        "playback_duration": f"{playback_duration:.2f}s"
                    }
                )
                
            except asyncio.TimeoutError:
                error_duration = time.time() - play_start
                log_structured_data(
                    logging.ERROR,
                    "audio_playback_timeout",
                    {
                        "timestamp": time.strftime("%H:%M:%S"),
                        "file": file_path.name,
                        "error_duration": f"{error_duration:.2f}s"
                    }
                )
                proc.kill()
                await proc.wait()
                raise
            except Exception as e:
                error_duration = time.time() - play_start
                log_structured_data(
                    logging.ERROR,
                    "audio_playback_error",
                    {
                        "timestamp": time.strftime("%H:%M:%S"),
                        "file": file_path.name,
                        "error": str(e),
                        "error_duration": f"{error_duration:.2f}s"
                    }
                )
                proc.kill()
                await proc.wait()
                raise
                
        except Exception as e:
            log_structured_data(
                logging.ERROR,
                "audio_playback_fatal_error",
                {
                    "timestamp": time.strftime("%H:%M:%S"),
                    "file": file_path.name,
                    "error": str(e)
                }
            )
            raise
    
    @log_timing
    async def generate_tts(
        self,
        text: str,
        play: bool = False,
        force_regenerate: bool = False
    ) -> Optional[str]:
        """Generate or retrieve TTS for given text."""
        if not text:
            logger.warning("Empty text provided to generate_tts")
            return None
            
        start_time = time.time()
        cache_path = self._get_cache_path(text)
        
        # Log AI speaking start
        log_structured_data(
            logging.INFO,
            "ai_speaking_start",
            {
                "timestamp": time.strftime("%H:%M:%S"),
                "text": text,
                "voice": self.get_voice_name(self.current_voice),
                "personality": "major_tom" if self.current_voice == config.voice.VOICE_TOM else "nikki"
            }
        )
        
        # Check cache first
        if not force_regenerate and cache_path.exists():
            cache_hit_time = time.time() - start_time
            log_structured_data(
                logging.INFO,
                "tts_cache_hit",
                {
                    "timestamp": time.strftime("%H:%M:%S"),
                    "cache_file": cache_path.name,
                    "voice": self.get_voice_name(self.current_voice),
                    "cache_latency": f"{cache_hit_time:.2f}s"
                }
            )
            return cache_path.name
        
        # Generate new TTS
        try:
            generation_start = time.time()
            log_structured_data(
                logging.INFO,
                "tts_generation_start",
                {
                    "timestamp": time.strftime("%H:%M:%S"),
                    "text_length": len(text),
                    "voice": self.get_voice_name(self.current_voice)
                }
            )
            
            # Create new HTTP client for each request to avoid hanging
            async with httpx.AsyncClient(timeout=30.0) as client:
                self.http_client = client
                result, generation_duration = await self._generate_tts(text, cache_path, play=False)
                total_duration = time.time() - start_time
                
                log_structured_data(
                    logging.INFO,
                    "tts_generation_complete",
                    {
                        "timestamp": time.strftime("%H:%M:%S"),
                        "generation_duration": f"{generation_duration:.2f}s",
                        "total_duration": f"{total_duration:.2f}s",
                        "cache_file": cache_path.name,
                        "text_length": len(text),
                        "voice": self.get_voice_name(self.current_voice)
                    }
                )
                return cache_path.name
        except Exception as e:
            error_duration = time.time() - start_time
            log_structured_data(
                logging.ERROR,
                "tts_generation_error",
                {
                    "timestamp": time.strftime("%H:%M:%S"),
                    "error": str(e),
                    "text_length": len(text),
                    "voice": self.get_voice_name(self.current_voice),
                    "error_duration": f"{error_duration:.2f}s"
                }
            )
            return None

    def verify_voice(self, voice_id: str) -> bool:
        """Verify if a voice ID is valid and available."""
        if not voice_id:
            logger.warning("Empty voice ID provided")
            return False
            
        is_valid = voice_id in [config.voice.VOICE_NIKKI, config.voice.VOICE_TOM]
        if not is_valid:
            logger.warning(f"Invalid voice ID: {voice_id}")
        return is_valid

# Global TTS manager instance
tts_manager = TTSManager() 