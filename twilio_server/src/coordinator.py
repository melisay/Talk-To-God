import logging
import time
import random
import traceback
import asyncio
import re
from typing import Optional, Dict, Any
from .config import config
from .utils import logger, log_timing, log_structured_data, cache, performance_stats
from .chat import ChatManager, chat_manager
from .tts import TTSManager, tts_manager
from .personality import PersonalityManager, personality_manager
from .user import UserManager, user_manager
from .sounds import sound_manager
from .entertainment import entertainment_manager

class InteractionCoordinator:
    """Coordinates interactions between different components of the AI God system."""
    
    def __init__(
        self,
        chat_manager: ChatManager,
        tts_manager: TTSManager,
        personality_manager: PersonalityManager,
        user_manager: UserManager
    ):
        """Initialize the coordinator with all required components."""
        self.chat_manager = chat_manager
        self.tts_manager = tts_manager
        self.personality_manager = personality_manager
        self.user_manager = user_manager
        self.interaction_metrics: Dict[str, Any] = {}
        self.is_first_interaction = True
        self.performance_stats = performance_stats  # Use global performance stats
        
        # Track voice and language switch state
        self._voice_switch_in_progress = False
        self._last_voice_switch_time = 0.0
        self.current_language = "en-US"  # Default language
        
        # Initialize with Nikki personality (this will also set the voice)
        self.personality_manager.set_personality("nikki")
        # No need to set voice here as set_personality already does it
        logger.info("Coordinator initialized with Nikki personality")
        
        # Log initial state
        log_structured_data(
            logging.INFO,
            "coordinator_initialized",
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "personality": self.personality_manager.current_personality,
                "voice": self.tts_manager.get_voice_name(self.tts_manager.current_voice),
                "components": {
                    "chat_manager": "initialized",
                    "tts_manager": "initialized",
                    "personality_manager": "initialized",
                    "user_manager": "initialized"
                }
            }
        )
    
    @log_timing
    async def handle_user_input(self, user_input: str, user_id: Optional[str] = None) -> None:
        """Handle user input and coordinate between components."""
        try:
            start_time = time.time()
            input_lower = user_input.lower()
            
            # Track metrics for this interaction
            self.interaction_metrics = {
                "start_time": start_time,
                "user_input": user_input,
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
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "user_said": user_input,
                    "personality": self.personality_manager.current_personality
                }
            )
            
            # Skip processing if input is too short or confidence is too low
            if len(input_lower.strip()) < 2:
                logger.info("Input too short, skipping processing")
                return
                
            # Check for wake words
            if any(w in input_lower for w in ["hey god", "hey tom", "hey nikki", "god please"]):
                await self.personality_manager.handle_wake_word()
                self.personality_manager.last_interaction_time = time.time()
                return
            
            # Check for idle timeout
            if time.time() - self.personality_manager.last_interaction_time > self.personality_manager.idle_timeout:
                await self.personality_manager.handle_idle()
                self.personality_manager.last_interaction_time = time.time()
                return
            
            # Check for motivation request
            if "motivation" in input_lower or "motivate me" in input_lower:
                response = await self.personality_manager.handle_motivation()
                if response:
                    await self._handle_special_response(response, "motivation")
                    self.personality_manager.last_interaction_time = time.time()
                    return
            
            # Check for easter eggs
            easter_egg = self.personality_manager.check_easter_egg(input_lower)
            if easter_egg:
                # Print easter egg to terminal
                print(f"\n🥚 EASTER EGG TRIGGERED")
                print(f"You: {user_input}")
                print(f"AI: {easter_egg}")
                print("-" * 50)
                
                await self._handle_easter_egg(easter_egg)
                self.personality_manager.last_interaction_time = time.time()
                return
            
            # Handle special requests with regex patterns
            if re.search(r'\b(impression|do an impression)\b', input_lower):
                response = await self.personality_manager.handle_impression()
                if response:
                    await self._handle_special_response(response, "impression")
                    self.personality_manager.last_interaction_time = time.time()
                    return
            
            if re.search(r'\b(sing a song|sing|song)\b', input_lower):
                response = await self.personality_manager.handle_song_request()
                if response:
                    await self._handle_special_response(response, "song")
                    self.personality_manager.last_interaction_time = time.time()
                    return
            
            # Check for compliment request
            if "compliment" in input_lower:
                response = await self.personality_manager.handle_compliment()
                if response:
                    await self._handle_special_response(response, "compliment")
                    self.personality_manager.last_interaction_time = time.time()
                    return
            
            # Handle special commands
            if await self._handle_special_command(input_lower):
                self.personality_manager.last_interaction_time = time.time()
                return
            
            # Handle voice switching
            switch_phrases = ["switch to", "switched to", "change to", "changed to", "become", "became", "be", "is"]
            if any(phrase in input_lower for phrase in switch_phrases):
                tom_triggers = ["major tom", "majortom", "tom", "major-tom"]
                nikki_triggers = ["nikki", "nikkunt", "nikki-god"]
                
                if any(trigger in input_lower for trigger in tom_triggers):
                    await self._handle_voice_switch("major tom")
                    self.personality_manager.last_interaction_time = time.time()
                    return
                elif any(trigger in input_lower for trigger in nikki_triggers):
                    await self._handle_voice_switch("nikki")
                    self.personality_manager.last_interaction_time = time.time()
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
            
            # Handle normal conversation
            await self._handle_normal_conversation(user_input)
            self.personality_manager.last_interaction_time = time.time()
            
        except Exception as e:
            await self._handle_error(e)
    
    async def _handle_voice_switch(self, target_voice: str) -> None:
        """Handle voice switching requests with proper state management and performance tracking."""
        # Get current voice name helper function
        def get_voice_name(voice_id: str) -> str:
            return "Nikki" if voice_id == config.voice.VOICE_NIKKI else "Major Tom"
        
        if self._voice_switch_in_progress:
            current_voice_name = get_voice_name(self.tts_manager.current_voice)
            log_structured_data(
                logging.WARNING,
                "voice_switch_skipped",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "reason": "switch_already_in_progress",
                    "target_voice": target_voice,
                    "current_voice": current_voice_name
                }
            )
            return

        try:
            self._voice_switch_in_progress = True
            switch_start = time.time()
            
            # Normalize target voice name
            target_voice = target_voice.lower().strip()
            if "major" in target_voice or "tom" in target_voice:
                target_personality = "major_tom"
                target_voice_id = config.voice.VOICE_TOM
                target_voice_name = "Major Tom"
                response = "The path of wisdom awaits. I am here to guide you."
            elif "nikki" in target_voice:
                target_personality = "nikki"
                target_voice_id = config.voice.VOICE_NIKKI
                target_voice_name = "Nikki"
                response = "Oh look who's back. Missed my sass already?"
            else:
                raise ValueError(f"Unknown personality: {target_voice}")
            
            # Get current voice name
            current_voice_name = get_voice_name(self.tts_manager.current_voice)
            
            # Log the voice switch start with full context
            log_structured_data(
                logging.INFO,
                "voice_switch_start",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "from_personality": self.personality_manager.current_personality,
                    "to_personality": target_personality,
                    "from_voice": current_voice_name,
                    "to_voice": target_voice_name,
                    "user_said": self.interaction_metrics["user_input"],
                    "time_since_last_switch": f"{time.time() - self._last_voice_switch_time:.2f}s"
                }
            )
            
            # Store old state for rollback
            old_personality = self.personality_manager.current_personality
            old_voice = self.tts_manager.current_voice
            old_voice_name = current_voice_name
            
            try:
                # Set personality and voice atomically
                self.personality_manager.set_personality(target_personality)
                self.tts_manager.set_voice(target_voice_id)
                
                # Log personality switch
                log_structured_data(
                    logging.INFO,
                    "personality_switch",
                    {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "from_personality": old_personality,
                        "to_personality": target_personality,
                        "from_voice": old_voice_name,
                        "to_voice": target_voice_name,
                        "personality_name": target_voice_name
                    }
                )
                
                # Verify voice switch was successful
                if self.tts_manager.current_voice != target_voice_id:
                    raise RuntimeError(f"Voice switch failed - expected {target_voice_name}, got {current_voice_name}")
                if self.personality_manager.current_personality != target_personality:
                    raise RuntimeError(f"Personality switch failed - expected {target_personality}, got {self.personality_manager.current_personality}")
                
                personality_switch_time = time.time() - switch_start
                self.performance_stats.add_timing("personality_switch", personality_switch_time)
                
                # Generate TTS with performance tracking
                tts_start = time.time()
                filename = await self.tts_manager.generate_tts(response, play=False)
                tts_latency = time.time() - tts_start
                self.performance_stats.add_timing("tts_generation", tts_latency)
                
                # Log AI speaking start
                log_structured_data(
                    logging.INFO,
                    "ai_speaking_start",
                    {
                        "timestamp": time.strftime("%H:%M:%S"),
                        "text": response,
                        "voice": target_voice_name,
                        "personality": target_personality
                    }
                )
                
                # Update metrics with detailed timing
                total_latency = time.time() - switch_start
                self.interaction_metrics.update({
                    "response_file": filename,
                    "ai_response": response,
                    "latencies": {
                        "personality_switch": personality_switch_time,
                        "tts": tts_latency,
                        "total": total_latency
                    },
                    "voice_switch": {
                        "from_voice": old_voice_name,
                        "to_voice": target_voice_name,
                        "from_personality": old_personality,
                        "to_personality": target_personality
                    }
                })
                
                # Log the voice switch completion with performance metrics
                log_structured_data(
                    logging.INFO,
                    "voice_switch_complete",
                    {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "user_said": self.interaction_metrics["user_input"],
                        "god_said": response,
                        "from_personality": old_personality,
                        "to_personality": target_personality,
                        "from_voice": old_voice_name,
                        "to_voice": target_voice_name,
                        "cached_file": filename,
                        "latencies": {
                            "personality_switch_s": f"{personality_switch_time:.2f}",
                            "tts_latency_s": f"{tts_latency:.2f}",
                            "total_latency_s": f"{total_latency:.2f}"
                        },
                        "performance_stats": self.performance_stats.get_stats()
                    }
                )
                
                # Print detailed personality switch info to terminal
                print(f"\n🎭 PERSONALITY SWITCH")
                print(f"From: {old_personality.replace('_', ' ').title()}")
                print(f"To: {target_personality.replace('_', ' ').title()}")
                print(f"You: {self.interaction_metrics['user_input']}")
                print(f"AI: {response}")
                print(f"Personality Switch: {personality_switch_time:.2f}s | TTS: {tts_latency:.2f}s | Total: {total_latency:.2f}s")
                print("-" * 50)
                
                self._last_voice_switch_time = time.time()
                
            except Exception as e:
                # Rollback on failure
                self.personality_manager.set_personality(old_personality)
                self.tts_manager.set_voice(old_voice)
                raise
                
        except Exception as e:
            error_duration = time.time() - switch_start
            log_structured_data(
                logging.ERROR,
                "voice_switch_error",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "target_voice": target_voice,
                    "current_voice": current_voice_name,
                    "error_duration_s": f"{error_duration:.2f}",
                    "stack_trace": traceback.format_exc()
                }
            )
            # Use personality-specific error message
            if self.personality_manager.current_personality == "major_tom":
                error_msg = "The path of wisdom is temporarily blocked. Try again when you're worthy."
            else:
                error_msg = "I apologize for the inconvenience. Let me try that again."
            await self.tts_manager.generate_tts(error_msg, play=True)
            raise
            
        finally:
            self._voice_switch_in_progress = False
    
    async def _handle_user_recognition(self, recognized_name: str) -> None:
        """Handle user recognition and greeting."""
        user = self.user_manager.get_or_create_user(recognized_name)
        
        # Play wake sound on first interaction
        if self.is_first_interaction:
            await sound_manager.play_wake_sound()
            self.is_first_interaction = False
        
        if self.user_manager.current_user != user:
            if user.first_seen == user.last_seen:
                await self.tts_manager.generate_tts(
                    f"Back so soon, {user.name}? I was just about to take a nap.",
                    play=True
                )
            else:
                recent_topics = self.user_manager.get_recent_topics()
                if recent_topics:
                    topics_str = ", ".join(recent_topics)
                    # Welcome back with context
                    if topics_str:
                        response = f"Look who's back, {user.name}! We were talking about {topics_str}. Try to keep up."
                    else:
                        response = f"Oh great, {user.name} is back. What do you need now?"
                    await self.tts_manager.generate_tts(response, play=True)
                else:
                    await self.tts_manager.generate_tts(
                        f"Welcome back, {user.name}! How can I help you today?",
                        play=True
                    )
            
            # Set personality based on user preference
            preferred_personality = user.get_personality_preference()
            if preferred_personality != self.personality_manager.current_personality:
                # Play void sound for personality transition
                await sound_manager.play_void_sound()
                self.personality_manager.set_personality(preferred_personality)
                self.tts_manager.set_voice(
                    config.voice.VOICE_TOM if preferred_personality == "major_tom"
                    else config.voice.VOICE_NIKKI
                )
    
    async def _handle_exit_command(self) -> None:
        """Handle exit command with culturally appropriate messages."""
        # Log the exit command with timing
        start_time = time.time()
        log_structured_data(
            logging.INFO,
            "exit_command_start",
            {
                "timestamp": time.strftime("%H:%M:%S"),
                "user": self.user_manager.current_user.name if self.user_manager.current_user else None,
                "personality": self.personality_manager.current_personality
            }
        )
        
        # Get personality-specific exit message
        if self.user_manager.current_user:
            response = f"Finally leaving, {self.user_manager.current_user.name}? Don't let the door hit you on the way out."
        else:
            response = "Goodbye! Try not to miss me too much."
        
        # Generate TTS and store the filename
        tts_start = time.time()
        filename = await self.tts_manager.generate_tts(response, play=False)
        tts_latency = time.time() - tts_start
        self.interaction_metrics["response_file"] = filename
        
        # Calculate total exit handling time
        total_latency = time.time() - start_time
        
        # Log the complete exit sequence
        log_structured_data(
            logging.INFO,
            "exit_command_complete",
            {
                "timestamp": time.strftime("%H:%M:%S"),
                "response": response,
                "response_file": filename,
                "tts_latency": f"{tts_latency:.2f}s",
                "total_latency": f"{total_latency:.2f}s",
                "user": self.user_manager.current_user.name if self.user_manager.current_user else None,
                "personality": self.personality_manager.current_personality,
                "exit_type": "graceful"
            }
        )
    
    async def _handle_easter_egg(self, easter_egg: str) -> None:
        """Handle easter egg responses."""
        try:
            # Log the easter egg attempt
            log_structured_data(
                logging.INFO,
                "easter_egg_triggered",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "response": easter_egg,
                    "personality": self.personality_manager.current_personality
                }
            )

            # Check if this is an Arabic easter egg based on the input text
            input_text = self.interaction_metrics["user_input"].lower()
            old_language = self.tts_manager.current_language  # Use TTS manager's current language

            try:
                # Generate TTS with a reasonable timeout
                try:
                    await asyncio.wait_for(
                        self.tts_manager.generate_tts(easter_egg, play=True),
                        timeout=10.0
                    )
                except Exception as e:
                    logger.error(f"TTS generation failed for easter egg: {str(e)}")
                    # If TTS fails, just log it and continue
                    log_structured_data(
                        logging.ERROR,
                        "easter_egg_tts_failure",
                        {
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "original": easter_egg,
                            "error": str(e)
                        }
                    )

                # Add to history if successful
                if self.user_manager.current_user:
                    self.user_manager.add_to_history("assistant", easter_egg)

            except Exception as e:
                logger.error(f"Error handling easter egg: {str(e)}")
                log_structured_data(
                    logging.ERROR,
                    "easter_egg_error",
                    {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "error": str(e)
                    }
                )

        except Exception as e:
            logger.error(f"Error handling easter egg: {str(e)}")
            log_structured_data(
                logging.ERROR,
                "easter_egg_error",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "error": str(e)
                }
            )
    
    async def _handle_special_response(self, response: str, response_type: str) -> None:
        """Handle special responses (impressions, songs) with proper TTS and metrics."""
        try:
            # Generate TTS and store the filename
            tts_start = time.time()
            filename = await self.tts_manager.generate_tts(response, play=False)
            tts_latency = time.time() - tts_start
            
            # Update metrics
            self.interaction_metrics.update({
                "operations": {
                    response_type: time.time() - self.interaction_metrics["start_time"],
                    "tts_generation": tts_latency
                },
                "latencies": {
                    "tts": tts_latency
                },
                "response_file": filename,
                "ai_response": response
            })
            
            # Add to history if we have a current user
            if self.user_manager.current_user:
                self.user_manager.add_to_history("assistant", response)
            
            # Log the special response
            log_structured_data(
                logging.INFO,
                f"{response_type}_response",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "response": response,
                    "response_file": filename,
                    "tts_latency": f"{tts_latency:.2f}s",
                    "personality": self.personality_manager.current_personality
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling {response_type} response: {str(e)}")
            log_structured_data(
                logging.ERROR,
                f"{response_type}_error",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "error": str(e),
                    "response_type": response_type
                }
            )
            raise
    
    async def _handle_special_command(self, text: str) -> bool:
        """Handle special commands with enhanced logging."""
        text = text.lower().strip()
        
        # Exit command
        if text in ["exit", "quit", "goodbye", "bye"]:
            await self._handle_exit_command()
            # Signal to stop the conversation loop
            self.should_exit = True
            return True
            
        # Language switching commands
        # ... existing code ...

    async def _handle_normal_conversation(self, user_input: str) -> None:
        """Handle normal conversation flow."""
        try:
            # Check for new answer request
            if any(phrase in user_input.lower() for phrase in ["new answer", "different answer", "try again", "another answer"]):
                # Clear the last response from cache to force a new one
                if self.user_manager.current_user and self.user_manager.current_user.conversation_history:
                    last_user_input = next(
                        (msg["content"] for msg in reversed(self.user_manager.current_user.conversation_history)
                         if msg["role"] == "user"),
                        None
                    )
                    if last_user_input:
                        cache_key = f"response_{self.personality_manager.current_personality}_{hash(last_user_input)}"
                        cache.clear()  # Clear the entire cache to ensure we get a new response
                        log_structured_data(
                            logging.INFO,
                            "new_answer_request",
                            {
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "original_input": last_user_input,
                                "personality": self.personality_manager.current_personality
                            }
                        )
                        user_input = last_user_input  # Use the last user input for new response
            
            # Get ChatGPT response
            log_structured_data(
                logging.INFO,
                "chatgpt_request_start",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "input": user_input,
                    "personality": self.personality_manager.current_personality
                }
            )
            
            chat_start = time.time()
            response = await self.chat_manager.get_response(
                user_input,
                personality=self.personality_manager.current_personality,
                use_cache=not any(phrase in user_input.lower() for phrase in ["new answer", "different answer", "try again", "another answer"])
            )
            chat_latency = time.time() - chat_start
            
            # Print conversation to terminal with latency
            print(f"\nYou: {user_input}")
            print(f"AI: {response}")
            print(f"Latency: {chat_latency:.2f}s")
            print("-" * 50)
            
            if not response:
                log_structured_data(
                    logging.ERROR,
                    "chatgpt_response_empty",
                    {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "input": user_input,
                        "personality": self.personality_manager.current_personality
                    }
                )
                raise ValueError("Empty response from ChatGPT")
            
            self.interaction_metrics["operations"]["chatgpt_response"] = chat_latency
            self.interaction_metrics["latencies"]["chatgpt"] = chat_latency
            self.interaction_metrics["ai_response"] = response
            
            # Log the response
            log_structured_data(
                logging.INFO,
                "chat_response",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "personality": self.personality_manager.current_personality,
                    "response": response,
                    "latency": f"{chat_latency:.2f}s"
                }
            )
            
            # Generate TTS and store the filename
            log_structured_data(
                logging.INFO,
                "tts_generation_start",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "text": response,
                    "voice": self.tts_manager.current_voice,
                    "personality": self.personality_manager.current_personality
                }
            )
            
            tts_start = time.time()
            filename = await self.tts_manager.generate_tts(response, play=False)
            tts_latency = time.time() - tts_start
            
            if not filename:
                log_structured_data(
                    logging.ERROR,
                    "tts_generation_failed",
                    {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "text": response,
                        "voice": self.tts_manager.current_voice,
                        "personality": self.personality_manager.current_personality
                    }
                )
                raise ValueError("TTS generation failed - no filename returned")
            
            self.interaction_metrics["operations"]["tts_generation"] = tts_latency
            self.interaction_metrics["latencies"]["tts"] = tts_latency
            self.interaction_metrics["response_file"] = filename
            
            log_structured_data(
                logging.INFO,
                "tts_generation_complete",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "filename": filename,
                    "latency": f"{tts_latency:.2f}s",
                    "voice": self.tts_manager.current_voice,
                    "personality": self.personality_manager.current_personality
                }
            )
            
            # Update conversation history
            if self.user_manager.current_user:
                self.user_manager.add_to_history("user", user_input)
                self.user_manager.add_to_history("assistant", response)
                
        except Exception as e:
            log_structured_data(
                logging.ERROR,
                "normal_conversation_error",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "input": user_input,
                    "personality": self.personality_manager.current_personality
                }
            )
            raise
    
    async def _handle_error(self, error: Exception) -> None:
        """Handle errors with personality-specific responses and proper logging."""
        error_type = type(error).__name__
        error_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Log detailed error information
        log_structured_data(
            logging.ERROR,
            "interaction_error",
            {
                "timestamp": error_time,
                "error": str(error),
                "error_type": error_type,
                "personality": self.personality_manager.current_personality,
                "user_input": self.interaction_metrics.get("user_input", "unknown"),
                "stack_trace": traceback.format_exc(),
                "performance_stats": self.performance_stats.get_stats()
            }
        )
        
        # Get personality-specific error message
        if self.personality_manager.current_personality == "major_tom":
            if "timeout" in error_type.lower():
                error_msg = "A moment of patience, please. Let me try again."
            elif "api" in error_type.lower():
                error_msg = "The API is having a moment. Typical."
            elif "tts" in error_type.lower():
                error_msg = "My voice is broken. How convenient."
            elif "network" in error_type.lower():
                error_msg = "Network issues. What else is new?"
            elif "timeout" in error_type.lower():
                error_msg = "Timed out. Your fault or mine? Probably yours."
            else:
                error_msg = "Something went wrong. Shocking, I know."
        else:
            if "timeout" in error_type.lower():
                error_msg = "Oops, my bad. Let me try again, but don't hold your breath."
            elif "api" in error_type.lower():
                error_msg = "A moment of patience, please. Let me resolve this."
            elif "tts" in error_type.lower():
                error_msg = "My voice is broken. How convenient."
            elif "network" in error_type.lower():
                error_msg = "Network issues. What else is new?"
            elif "timeout" in error_type.lower():
                error_msg = "Timed out. Your fault or mine? Probably yours."
            else:
                error_msg = "Something went wrong. Shocking, I know."
        
        # Generate error response with performance tracking
        tts_start = time.time()
        await self.tts_manager.generate_tts(error_msg, play=True)
        tts_latency = time.time() - tts_start
        self.performance_stats.add_timing("error_tts", tts_latency)
        
        # Log error recovery
        log_structured_data(
            logging.INFO,
            "error_recovery",
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error_type": error_type,
                "recovery_message": error_msg,
                "tts_latency_s": f"{tts_latency:.2f}",
                "personality": self.personality_manager.current_personality
            }
        )

    async def handle_welcome(self) -> str:
        """Handle initial greeting when a call starts."""
        try:
            # Get welcome response based on current personality
            personality = self.personality_manager.get_current_personality()
            welcome_response = self.personality_manager._get_random_response("wake", personality.wake_responses)
            
            # Generate TTS and get filename
            filename = await self.tts_manager.generate_tts(welcome_response)
            
            # Log the welcome
            log_structured_data(
                logging.INFO,
                "welcome_response",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "personality": self.personality_manager.current_personality,
                    "response": welcome_response,
                    "voice_id": personality.voice_id
                }
            )
            
            return filename
            
        except Exception as e:
            logger.error(f"Error in handle_welcome: {str(e)}")
            # Fallback to a simple welcome message
            fallback = "Welcome to AI God. How may I assist you today?"
            filename = await self.tts_manager.generate_tts(fallback)
            return filename

    async def handle_fallback(self) -> str:
        """Handle fallback response when no input is received."""
        try:
            # Only generate fallback if we haven't just responded
            if time.time() - self.personality_manager.last_interaction_time > 2.0:  # 2 second cooldown
                personality = self.personality_manager.get_current_personality()
                fallback_response = "I didn't catch that. Try speaking clearly, maybe?"
                filename = await self.tts_manager.generate_tts(fallback_response)
                self.personality_manager.last_interaction_time = time.time()
                return filename
            return None
        except Exception as e:
            logger.error(f"Error in handle_fallback: {str(e)}")
            return None

# Global coordinator instance
interaction_coordinator = InteractionCoordinator(
    chat_manager=chat_manager,
    tts_manager=tts_manager,
    personality_manager=personality_manager,
    user_manager=user_manager
) 