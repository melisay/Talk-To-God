#!/usr/bin/env python3
"""
Performance optimization script for the local AI Assistant.
This script pre-caches common responses and optimizes the runtime environment.
"""

import asyncio
import os
import sys
from pathlib import Path
import logging
import time
import json

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import local components
from local.src.config import config
from local.src.utils import logger
from local.src.tts import tts_manager
from local.src.chat import chat_manager

# Common phrases to pre-cache
COMMON_PHRASES = [
    "Hello, how can I help you today?",
    "I'm sorry, I didn't understand that. Could you please repeat?",
    "Let me think about that for a moment.",
    "Is there anything else you'd like to know?",
    "Thank you for your question.",
    "I'm processing your request.",
    "Oh great, another question.",
    "Let me process this... if I must.",
    "Oh look who's back. Missed my sass already?",
    "I'm here to help, but don't expect miracles.",
    "Details? How about you be more specific?",
    "Could you provide more details about your question?",
    "Let me find that information for you."
]

# Personalities to cache for
PERSONALITIES = ["assistant", "technical", "creative"]

async def pre_cache_responses():
    """Pre-cache common TTS responses for faster interaction."""
    logger.info("Starting pre-cache process...")
    start_time = time.time()
    
    # Create cache directory if it doesn't exist
    config.paths.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Track cache statistics
    stats = {
        "total_phrases": len(COMMON_PHRASES) * len(PERSONALITIES),
        "cached": 0,
        "errors": 0,
        "duration": 0
    }
    
    # Process each personality
    for personality in PERSONALITIES:
        logger.info(f"Pre-caching for personality: {personality}")
        
        # Set the voice for this personality
        if personality == "technical":
            tts_manager.set_voice(config.voice.VOICE_TECHNICAL)
        elif personality == "creative":
            tts_manager.set_voice(config.voice.VOICE_CREATIVE)
        else:
            tts_manager.set_voice(config.voice.VOICE_DEFAULT)
        
        # Process phrases in batches to avoid overloading the API
        batch_size = 3
        for i in range(0, len(COMMON_PHRASES), batch_size):
            batch = COMMON_PHRASES[i:i+batch_size]
            tasks = []
            
            # Create tasks for each phrase
            for phrase in batch:
                tasks.append(tts_manager.generate_tts(phrase, play=False))
            
            # Run tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error caching phrase: {result}")
                    stats["errors"] += 1
                elif result:
                    stats["cached"] += 1
            
            # Avoid rate limiting
            await asyncio.sleep(1)
    
    stats["duration"] = time.time() - start_time
    logger.info(f"Pre-cache complete. Stats: {json.dumps(stats)}")
    return stats

async def optimize_environment():
    """Optimize the runtime environment for better performance."""
    logger.info("Optimizing runtime environment...")
    
    # Ensure all necessary directories exist
    os.makedirs(config.paths.CACHE_DIR, exist_ok=True)
    os.makedirs(Path("logs"), exist_ok=True)
    
    # Set process priority if possible
    try:
        if sys.platform == "win32":
            import psutil
            p = psutil.Process(os.getpid())
            p.nice(psutil.HIGH_PRIORITY_CLASS)
        elif sys.platform in ["linux", "linux2"]:
            os.nice(-10)  # Higher priority on Linux
        logger.info("Process priority increased")
    except Exception as e:
        logger.warning(f"Could not set process priority: {e}")
    
    # Optimize Python GC for responsiveness
    try:
        import gc
        gc.disable()  # Disable automatic garbage collection
        logger.info("Garbage collection optimized")
    except Exception as e:
        logger.warning(f"Could not optimize garbage collection: {e}")
    
    logger.info("Environment optimization complete")

async def main():
    """Main optimization function."""
    logger.info("Starting performance optimization...")
    
    try:
        # Run optimizations
        await optimize_environment()
        stats = await pre_cache_responses()
        
        logger.info(f"Performance optimization complete in {stats['duration']:.2f} seconds")
        logger.info(f"Cached {stats['cached']}/{stats['total_phrases']} phrases with {stats['errors']} errors")
        
        return True
    except Exception as e:
        logger.error(f"Performance optimization failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(main())