#!/usr/bin/env python3
from asyncio import run, sleep, CancelledError
from json import dumps
from signal import signal, SIGINT, SIGTERM
from typing import Optional

from local.src.config import config
from local.src.utils import logger, performance_stats
from local.src.speech import speech_recognizer
from local.src.coordinator import interaction_coordinator
from local.src.performance import performance_monitor, monitor_operation

class AIAssistant:
    def __init__(self):
        self.running = True
        self.idle_mode = False
        self.setup_signal_handlers()
    
    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal")
            performance_monitor.print_summary()
            self.running = False
        
        signal(SIGINT, signal_handler)
        signal(SIGTERM, signal_handler)
    
    @monitor_operation("handle_user_input")
    async def handle_user_input(self, user_input: str, user_id: Optional[str] = None) -> None:
        """Handle user input using the interaction coordinator."""
        await interaction_coordinator.handle_user_input(user_input, user_id)
    
    @monitor_operation("idle_loop")
    async def idle_loop(self) -> None:
        """Handle idle mode and wake word detection."""
        idle_check_interval = 0.5
        
        while self.running and self.idle_mode:
            try:
                if await speech_recognizer.listen_for_wake_word():
                    self.idle_mode = False
                    await interaction_coordinator.personality_manager.handle_wake_word()
                await sleep(idle_check_interval)
            except CancelledError:
                logger.info("Idle loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in idle loop: {e}")
                await sleep(1)
    
    @monitor_operation("main_loop")
    async def main_loop(self) -> None:
        """Main conversation loop."""
        logger.info("Starting assistant...")
        await interaction_coordinator.tts_manager.generate_tts(
            "Oh look who's back. Missed my sass already?",
            play=True
        )
        
        while self.running and not interaction_coordinator.should_exit:
            try:
                if self.idle_mode:
                    await self.idle_loop()
                    continue
                
                # Get user input
                user_input = await speech_recognizer.listen_for_input()
                if not user_input:
                    continue
                
                # Handle the input
                await self.handle_user_input(user_input)
                
                # Check if we should exit after handling input
                if interaction_coordinator.should_exit:
                    logger.info("Exit command received, shutting down...")
                    break
                
            except CancelledError:
                logger.info("Main loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await sleep(1)
        
        # Log final exit
        logger.info("Assistant shutting down gracefully...")
        performance_monitor.print_summary()
        self.running = False

    async def run(self) -> None:
        """Run the assistant application."""
        try:
            async with interaction_coordinator.tts_manager:
                # Print initial performance stats
                logger.info("Initial performance stats:")
                logger.info(dumps(performance_stats.get_stats(), indent=2))
                
                await self.main_loop()
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            logger.info("Shutting down assistant...")
            # Print final performance stats
            logger.info("Final performance stats:")
            logger.info(dumps(performance_stats.get_stats(), indent=2))
            performance_monitor.print_summary()
            self.running = False

if __name__ == "__main__":
    assistant = AIAssistant()
    run(assistant.run())