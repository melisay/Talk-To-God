import logging
from time import time, strftime
import re
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from .config import config
from .utils import (
    logger, log_timing, log_structured_data, log_interaction, 
    log_error, add_metric, cache, get_cached_response
)
from .chat import ChatManager, chat_manager
from .tts import TTSManager, tts_manager
from .personality import PersonalityManager, personality_manager
from .user import UserManager, user_manager
from .speech import speech_recognizer
from asyncio import sleep, CancelledError, wait_for
from .entertainment import entertainment_manager
from .sounds import sound_manager
import random

class InteractionCoordinator:
    """Coordinates interactions between different components of the AI Assistant system."""
    
    def __init__(
        self,
        chat_manager: ChatManager,
        tts_manager: TTSManager,
        personality_manager: PersonalityManager,
        user_manager: UserManager,
        speech_recognizer=None
    ):
        """Initialize the coordinator with all required components."""
        self.chat_manager = chat_manager
        self.tts_manager = tts_manager
        self.personality_manager = personality_manager
        self.user_manager = user_manager
        self.speech_recognizer = speech_recognizer or speech_recognizer
        self.interaction_metrics: Dict[str, Any] = {}
        self.should_exit = False  # Add flag for graceful exit
        
        # Track voice and language switch state
        self._voice_switch_in_progress = False
        self._last_voice_switch_time = 0.0
        self.current_language = "en-US"  # Default language
        
        # Initialize with default personality
        self.personality_manager.set_personality("nikki")
        self.tts_manager.set_voice(config.voice.VOICE_NIKKI)
        
        # Log initial state
        log_structured_data(
            logging.INFO,
            "coordinator_initialized",
            {
                "timestamp": self._get_timestamp(),
                "personality": self.personality_manager.current_personality,
                "voice": self.tts_manager.get_voice_name(self.tts_manager.current_voice),
                "language": self.current_language
            }
        )
    
    def _get_timestamp(self) -> str:
        """Get a timezone-aware timestamp."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    def _sanitize_input(self, text: str) -> str:
        """Sanitize user input for logging."""
        return text.replace('\n', ' ').replace('\r', ' ')
    
    async def _handle_special_command(self, text: str) -> bool:
        """Handle special commands with enhanced logging."""
        text = text.lower().strip()
        
        # Exit command
        if text in ["exit", "quit", "goodbye", "bye"]:
            personality = self.personality_manager.get_current_personality()
            if self.user_manager.current_user:
                farewell = f"Finally leaving, {self.user_manager.current_user.name}? Don't let the door hit you on the way out."
            else:
                farewell = "Goodbye! Try not to miss me too much."
            
            await self.tts_manager.generate_tts(farewell, play=True)
            log_structured_data(
                logging.INFO,
                "exit_command",
                {
                    "timestamp": self._get_timestamp(),
                    "personality": self.personality_manager.current_personality,
                    "user": self.user_manager.current_user.name if self.user_manager.current_user else None
                }
            )
            # Signal to stop the conversation loop
            self.should_exit = True
            return True
            
        # Language switching commands
        if text in ["switch to english", "english"]:
            await self.set_language("en-US")
            return True
            
        # Personality switching commands
        elif text in ["switch to nikki", "nikki", "become nikki"]:
            await self.set_personality("nikki")
            return True
        elif text in ["switch to major tom", "major tom", "tom", "become major tom", "become tom"]:
            await self.set_personality("major_tom")
            return True
            
        return False

    async def set_personality(self, personality: str) -> None:
        """Set the personality and corresponding voice."""
        valid_personalities = ["nikki", "major_tom"]
        if personality not in valid_personalities:
            raise ValueError(f"Invalid personality: {personality}")
            
        old_personality = self.personality_manager.current_personality
        self.personality_manager.set_personality(personality)
        
        # Set the appropriate voice
        if personality == "major_tom":
            self.tts_manager.set_voice(config.voice.VOICE_TOM)
        else:  # nikki
            self.tts_manager.set_voice(config.voice.VOICE_NIKKI)
        
        # Announce personality change
        response = f"Switching to {personality} mode. Brace yourself."
        await self.tts_manager.generate_tts(response, play=True)
        
        # Print detailed personality switch info to terminal
        print(f"\n🎭 PERSONALITY SWITCH")
        print(f"From: {old_personality.replace('_', ' ').title()}")
        print(f"To: {personality.replace('_', ' ').title()}")
        print(f"AI: {response}")
        print("-" * 50)
            
        log_structured_data(
            logging.INFO,
            "personality_changed",
            {
                "personality": personality,
                "timestamp": self._get_timestamp()
            }
        )

    async def set_language(self, language: str) -> None:
        """Set the language for both speech recognition and TTS."""
        valid_languages = ["en-US"]
        if language not in valid_languages:
            raise ValueError(f"Invalid language: {language}")
            
        self.current_language = language
        self.speech_recognizer.set_language(language)
        self.tts_manager.set_language(language)
        
        # Announce language change in the new language
        await self.tts_manager.generate_tts("English it is. At least you're consistent.")
            
        log_structured_data(
            logging.INFO,
            "language_changed",
            {
                "language": language,
                "timestamp": self._get_timestamp()
            }
        )
    
    def _validate_user_authorization(self, user_id: Optional[str]) -> bool:
        """Validate user authorization with secure comparison."""
        if not user_id:
            return True  # Allow anonymous users
            
        # Get user from database
        user = self.user_manager.get_user(user_id)
        if not user:
            return False
            
        # Check if user is authorized
        return user.is_authorized
    
    @log_timing
    async def handle_user_input(self, user_input: str, user_id: Optional[str] = None) -> None:
        """Handle user input and coordinate between components."""
        # Validate user authorization
        if not self._validate_user_authorization(user_id):
            logger.warning(f"Unauthorized access attempt with user_id: {user_id}")
            return
            
        try:
            start_time = time()
            sanitized_input = self._sanitize_input(user_input)
            input_lower = sanitized_input.lower().strip()
            
            # Track metrics for this interaction
            self.interaction_metrics = {
                "start_time": start_time,
                "user_input": sanitized_input,
                "operations": {},
                "response_file": None,
                "ai_response": None,
                "latencies": {
                    "chatgpt": 0.0,
                    "tts": 0.0,
                    "playback": 0.0,
                    "total": 0.0
                }
            }
            
            # Log the interaction start
            log_structured_data(
                logging.INFO,
                "conversation_start",
                {
                    "timestamp": self._get_timestamp(),
                    "user_said": sanitized_input,
                    "personality": self.personality_manager.current_personality
                }
            )
            
            # Check for wake words
            if any(w in input_lower for w in ["hey assistant", "hello assistant"]):
                await self.personality_manager.handle_wake_word()
                self.personality_manager.last_interaction_time = time()
                return
            
            # Check for idle timeout
            if time() - self.personality_manager.last_interaction_time > self.personality_manager.idle_timeout:
                await self.personality_manager.handle_idle()
                self.personality_manager.last_interaction_time = time()
                return
            
            # Handle special commands
            if await self._handle_special_command(input_lower):
                return
            
            # Personality-specific command handlers
            if "compliment" in input_lower:
                response = await self.personality_manager.handle_compliment()
                if response:
                    await self.tts_manager.generate_tts(response, play=True)
                    self.personality_manager.last_interaction_time = time()
                    return
            
            if "motivation" in input_lower or "motivate me" in input_lower:
                response = await self.personality_manager.handle_motivation()
                if response:
                    await self.tts_manager.generate_tts(response, play=True)
                    self.personality_manager.last_interaction_time = time()
                    return
            
            if "impression" in input_lower or "do an impression" in input_lower:
                response = await self.personality_manager.handle_impression()
                if response:
                    await self.tts_manager.generate_tts(response, play=True)
                    self.personality_manager.last_interaction_time = time()
                    return
            
            if "sing" in input_lower or "song" in input_lower:
                response = await self.personality_manager.handle_song_request()
                if response:
                    await self.tts_manager.generate_tts(response, play=True)
                    self.personality_manager.last_interaction_time = time()
                    return
            
            # Check for easter eggs
            easter_egg = self.personality_manager.check_easter_egg(input_lower)
            if easter_egg:
                # Print easter egg to terminal
                print(f"\n🥚 EASTER EGG TRIGGERED")
                print(f"You: {sanitized_input}")
                print(f"AI: {easter_egg}")
                print("-" * 50)
                
                await self.tts_manager.generate_tts(easter_egg, play=True)
                self.personality_manager.last_interaction_time = time()
                return
            
            # Entertainment triggers
            if input_lower == "tell me a joke":
                joke = entertainment_manager.get_joke()
                await self.tts_manager.generate_tts(joke['setup'], play=True)
                await self.tts_manager.generate_tts(joke['punchline'], play=True)
                # 20% chance to play rimshot
                if random.random() < 0.2:
                    await sound_manager.play_rimshot()
                # 5% chance to play a random effect
                if random.random() < 0.05:
                    await sound_manager.play_sound(random.choice(["LIGHTNING", "DOOM", "VOID", "INSANITY"]))
                return
            if input_lower == "tell me a riddle":
                riddle = entertainment_manager.get_riddle()
                await self.tts_manager.generate_tts(riddle['riddle'], play=True)
                await self.tts_manager.generate_tts(f"Drumroll please... {riddle['answer']}", play=True)
                if random.random() < 0.05:
                    await sound_manager.play_sound(random.choice(["LIGHTNING", "DOOM", "VOID", "INSANITY"]))
                return
            if input_lower == "tell me a story":
                story = entertainment_manager.get_story()
                await self.tts_manager.generate_tts(story['title'], play=True)
                await self.tts_manager.generate_tts(story['content'], play=True)
                if random.random() < 0.05:
                    await sound_manager.play_sound(random.choice(["LIGHTNING", "DOOM", "VOID", "INSANITY"]))
                return
            if input_lower == "tell me a fact":
                fact = entertainment_manager.get_fact()
                await self.tts_manager.generate_tts(fact, play=True)
                if random.random() < 0.05:
                    await sound_manager.play_sound(random.choice(["LIGHTNING", "DOOM", "VOID", "INSANITY"]))
                return
            
            # Update interaction time
            self.personality_manager.update_interaction_time()
            
            # Get response and play it
            response = await self.chat_manager.get_response(
                sanitized_input,
                personality=self.personality_manager.current_personality
            )
            
            # Log total latency
            total_latency = time() - start_time
            self.interaction_metrics["latencies"]["total"] = total_latency
            
            # Get latency breakdown
            tts_latency = self.interaction_metrics["latencies"].get("tts", 0.0)
            chat_latency = self.interaction_metrics["latencies"].get("chatgpt", 0.0)
            
            # Print conversation to terminal with detailed latency
            print(f"\nYou: {sanitized_input}")
            print(f"AI: {response}")
            print(f"TTS Latency: {tts_latency:.2f}s | Total Latency: {total_latency:.2f}s")
            print("-" * 50)
            
            # Generate and play TTS
            await self.tts_manager.generate_tts(response, play=True)
            
            # Log the complete conversation
            log_structured_data(
                logging.INFO,
                "conversation_complete",
                {
                    "timestamp": self._get_timestamp(),
                    "user_said": sanitized_input,
                    "assistant_said": response,
                    "personality": self.personality_manager.current_personality,
                    "total_latency_s": f"{total_latency:.2f}"
                }
            )
            
        except Exception as e:
            logger.error(f"Error in handle_user_input: {e}")
            await self._handle_error(e)

    async def _handle_error(self, error: Exception) -> None:
        """Handle errors with appropriate responses."""
        logger.error(f"Error in handle_user_input: {str(error)}")
        error_msg = "Oops, my bad. Let me try again, but don't hold your breath."
        await self.tts_manager.generate_tts(error_msg, play=True)

    async def start(self):
        """Start immediately in conversation mode."""
        try:
            # Start conversation loop directly
            await self.conversation_loop()
        except Exception as e:
            logger.error(f"Error in AI Assistant system: {e}")
            raise

    async def conversation_loop(self):
        """Main conversation loop."""
        while not self.should_exit:  # Check should_exit flag
            try:
                # Get user input using instance speech recognizer
                user_input = await self.speech_recognizer.listen_for_input()
                if not user_input:
                    continue
                
                # Handle input directly
                await self.handle_user_input(user_input)
                
                # Check if we should exit after handling input
                if self.should_exit:
                    break
                
            except CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in conversation loop: {e}")
                await sleep(0.1)
        
        # Log final exit
        log_structured_data(
            logging.INFO,
            "conversation_loop_exit",
            {
                "timestamp": self._get_timestamp(),
                "personality": self.personality_manager.current_personality,
                "user": self.user_manager.current_user.name if self.user_manager.current_user else None,
                "exit_type": "graceful"
            }
        )

# Global coordinator instance with speech recognizer
interaction_coordinator = InteractionCoordinator(
    chat_manager=chat_manager,
    tts_manager=tts_manager,
    personality_manager=personality_manager,
    user_manager=user_manager,
    speech_recognizer=speech_recognizer
)