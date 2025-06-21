import asyncio
import logging
import os
import sys
import time
from asyncio import to_thread
from contextlib import contextmanager
from typing import Optional, Tuple

# Third-party imports
import speech_recognition as sr
import sounddevice

from .config import config
from .utils import logger, log_timing, log_structured_data
from .performance import monitor_operation, performance_monitor

class SpeechRecognizer:
    def __init__(self):
        """Initialize speech recognizer with proper microphone setup."""
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.current_language = "en-US"  # Default language
        
        # Set initial values
        self.recognizer.energy_threshold = config.speech.ENERGY_THRESHOLD
        self.recognizer.dynamic_energy_threshold = config.speech.DYNAMIC_ENERGY_THRESHOLD
        self.recognizer.dynamic_energy_adjustment_damping = config.speech.DYNAMIC_ENERGY_ADJUSTMENT_DAMPING
        self.recognizer.dynamic_energy_ratio = config.speech.DYNAMIC_ENERGY_RATIO
        self.recognizer.pause_threshold = config.speech.PAUSE_THRESHOLD
        
        # Set up microphone once
        self._setup_microphone()
    
    def _setup_microphone(self):
        """Set up microphone with proper error handling."""
        try:
            # Create a single microphone instance
            self.microphone = sr.Microphone()
            # Test the microphone
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(
                    source,
                    duration=config.speech.ADJUST_FOR_AMBIENT_NOISE_DURATION
                )
            logger.info("Microphone setup complete")
        except Exception as e:
            logger.error(f"Error setting up microphone: {str(e)}")
            self.microphone = None
    
    def _adjust_for_ambient_noise(self):
        """Adjust for ambient noise with improved calibration."""
        if not self.microphone or not config.speech.ADJUST_FOR_AMBIENT_NOISE:
            return
            
        try:
            # Create a new microphone instance for noise adjustment
            with sr.Microphone() as noise_source:
                logger.info("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(
                    noise_source,
                    duration=config.speech.ADJUST_FOR_AMBIENT_NOISE_DURATION
                )
                logger.info(f"Adjusted energy threshold to: {self.recognizer.energy_threshold}")
        except Exception as e:
            logger.error(f"Error adjusting for ambient noise: {e}")
            # Don't raise the error, just log it and continue with current settings
    
    def set_language(self, language: str) -> None:
        """Set the language for speech recognition.
        
        Args:
            language: The language code to use (e.g., 'en-US')
        """
        valid_languages = ["en-US"]
        if language not in valid_languages:
            raise ValueError(f"Unsupported language: {language}")
        
        self.current_language = language
        logger.info(f"Speech recognition language set to: {language}")
        log_structured_data(
            logging.INFO,
            "speech_language_changed",
            {
                "language": language,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        )

    @monitor_operation("initial_wake_word_detection")
    async def listen_for_initial_wake_word(self) -> bool:
        """Listen specifically for initial wake word with minimal processing."""
        if not self.microphone:
            return False
            
        try:
            # Set ultra-aggressive settings for initial detection
            self.recognizer.energy_threshold = 50  # Fixed low threshold
            self.recognizer.dynamic_energy_threshold = False
            self.recognizer.pause_threshold = 0.3  # Shorter pause threshold
            
            with self.microphone as source:
                # Skip ambient noise adjustment for initial detection
                audio = await asyncio.to_thread(
                    self.recognizer.listen,
                    source,
                    timeout=1,
                    phrase_time_limit=1
                )
                
                if not audio:
                    return False
                    
                # Quick check for audio data
                if not audio.get_raw_data():
                    return False
                
                # Fast recognition with minimal processing
                text = await asyncio.to_thread(
                    self.recognizer.recognize_google,
                    audio,
                    language="en-US"
                )
                
                # Quick text normalization and wake word check
                text = text.lower().strip()
                if any(wake_word == text for wake_word in config.speech.WAKE_UP_WORDS):
                    # Sanitize user input before logging to prevent log injection
                    sanitized_text = text.replace('\n', ' ').replace('\r', ' ')
                    log_structured_data(
                        logging.INFO,
                        "Initial wake word detected",
                        {"text": sanitized_text, "latency": "initial_detection"}
                    )
                    return True
                
                return False
                
        except (sr.UnknownValueError, sr.RequestError):
            return False
        except Exception as e:
            logger.error(f"Error in initial wake word detection: {e}")
            return False
        finally:
            # Restore normal settings
            self.recognizer.energy_threshold = config.speech.ENERGY_THRESHOLD
            self.recognizer.dynamic_energy_threshold = config.speech.DYNAMIC_ENERGY_THRESHOLD
            self.recognizer.pause_threshold = config.speech.PAUSE_THRESHOLD

    @monitor_operation("wake_word_detection")
    async def listen_for_wake_word(self) -> bool:
        """Listen specifically for wake words during conversation."""
        try:
            # Use medium timeouts for ongoing wake word detection
            text, confidence = await self.listen(timeout=5, phrase_time_limit=3)
            if not text:
                return False
                
            # Normalize text for comparison
            text = text.lower().strip()
            
            # Check for exact matches first
            if any(wake_word == text for wake_word in config.speech.WAKE_UP_WORDS):
                # Sanitize user input before logging
                sanitized_text = text.replace('\n', ' ').replace('\r', ' ')
                log_structured_data(
                    logging.INFO,
                    "Wake word detected (exact match)",
                    {
                        "text": sanitized_text,
                        "confidence": confidence,
                        "wake_word": sanitized_text
                    }
                )
                return True
                
            # Then check for partial matches
            for wake_word in config.speech.WAKE_UP_WORDS:
                if wake_word in text:
                    # Additional validation for partial matches
                    words = text.split()
                    if len(words) <= 3:  # Only accept short phrases
                        # Sanitize user input before logging
                        sanitized_text = text.replace('\n', ' ').replace('\r', ' ')
                        log_structured_data(
                            logging.INFO,
                            "Wake word detected (partial match)",
                            {
                                "text": sanitized_text,
                                "confidence": confidence,
                                "wake_word": wake_word
                            }
                        )
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in wake word detection: {e}")
            return False

    @monitor_operation("speech_recognition")
    async def listen(self, timeout: Optional[int] = None, phrase_time_limit: Optional[int] = None) -> Tuple[str, float]:
        """Listen for speech with optimized processing and language support."""
        if not self.microphone:
            return "", 0.0
            
        timeout = timeout or config.speech.TIMEOUT
        phrase_time_limit = phrase_time_limit or config.speech.PHRASE_TIME_LIMIT
        
        try:
            with self.microphone as source:
                if timeout > 1:
                    self._adjust_for_ambient_noise()
                
                # Use shorter timeouts for better responsiveness
                audio = await asyncio.to_thread(
                    self.recognizer.listen,
                    source,
                    timeout=min(timeout, 5),  # Cap timeout at 5 seconds
                    phrase_time_limit=min(phrase_time_limit, 5)  # Cap phrase time at 5 seconds
                )
                
                if not audio or not audio.get_raw_data():
                    return "", 0.0
                
                # Try recognition with current language
                try:
                    text = await asyncio.to_thread(
                        self.recognizer.recognize_google,
                        audio,
                        language=self.current_language
                    )
                    confidence = 1.0
                except sr.UnknownValueError:
                    return "", 0.0
                
                # Calculate minimal metrics
                audio_level = max(abs(int.from_bytes(audio.get_raw_data()[i:i+2], 'little', signed=True)) 
                                for i in range(0, len(audio.get_raw_data()), 2))
                audio_duration = len(audio.get_raw_data()) / (audio.sample_rate * audio.sample_width)
                
                # Sanitize user input before logging
                sanitized_text = text.replace('\n', ' ').replace('\r', ' ')
                
                # Log with language information
                log_structured_data(
                    logging.INFO,
                    "speech_recognized",
                    {
                        "text": sanitized_text,
                        "confidence": confidence,
                        "audio_level": audio_level,
                        "duration": audio_duration,
                        "threshold": self.recognizer.energy_threshold,
                        "language": self.current_language,
                    }
                )
                
                return text, confidence
                
        except sr.UnknownValueError:
            return "", 0.0
        except sr.RequestError as e:
            logger.error(f"Network error during recognition: {e}")
            return "", 0.0
        except Exception as e:
            logger.error(f"Error during speech recognition: {e}")
            return "", 0.0
    
    @log_timing
    async def listen_for_interruption(self) -> bool:
        """Listen specifically for interruption keywords."""
        text, confidence = await self.listen()
        if not text:
            return False
        
        interruption_detected = any(
            keyword in text
            for keyword in config.speech.INTERRUPT_KEYWORDS
        )
        
        if interruption_detected:
            # Sanitize user input before logging
            sanitized_text = text.replace('\n', ' ').replace('\r', ' ')
            logger.info(f"Interruption detected: {sanitized_text}")
        
        return interruption_detected

    @monitor_operation("speech_input")
    async def listen_for_input(self) -> Optional[str]:
        """Listen for user input with proper microphone handling."""
        if not self.microphone:
            logger.error("No microphone available")
            return None
            
        try:
            # Use the existing microphone instance
            with self.microphone as source:
                # Use normal settings for better reliability
                audio = await asyncio.to_thread(
                    self.recognizer.listen,
                    source,
                    timeout=config.speech.TIMEOUT,
                    phrase_time_limit=config.speech.PHRASE_TIME_LIMIT
                )
                
                if not audio or not audio.get_raw_data():
                    return None
                
                # Fast recognition with minimal processing
                text = await asyncio.to_thread(
                    self.recognizer.recognize_google,
                    audio,
                    language="en-US"
                )
                
                # Quick text normalization
                text = text.lower().strip()
                
                # Sanitize user input before logging
                sanitized_text = text.replace('\n', ' ').replace('\r', ' ')
                
                # Log successful recognition
                log_structured_data(
                    logging.INFO,
                    "speech_recognized",
                    {
                        "text": sanitized_text,
                        "threshold": self.recognizer.energy_threshold
                    }
                )
                
                return text
                
        except (sr.UnknownValueError, sr.RequestError):
            return None
        except Exception as e:
            logger.error(f"Error in listen_for_input: {str(e)}")
            return None

# Global speech recognizer instance
speech_recognizer = SpeechRecognizer()