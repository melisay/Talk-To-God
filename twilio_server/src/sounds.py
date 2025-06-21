"""Sound effects management for the AI God project."""
import os
from pathlib import Path
import asyncio
import logging
from typing import Optional, Dict
from dataclasses import dataclass
import pygame
from .config import config
import random

logger = logging.getLogger("ai_god")

@dataclass
class SoundEffects:
    """Sound effect file paths and settings."""
    # Personality transition sounds
    NIKKI_TRANSITION: str = "nikki.mp3"  # Nikki's transition sound
    TOM_TRANSITION: str = "tom.mp3"      # Major Tom's transition sound
    
    # Lightning effects
    LIGHTNING_1: str = "lightning1.mp3"  # Lightning effect 1
    LIGHTNING_2: str = "lightning2.mp3"  # Lightning effect 2
    LIGHTNING_3: str = "lightning3.mp3"  # Lightning effect 3
    
    # Evil sound effects
    WAKE_UP: str = "evil/wakeup.mp3"      # Sinister awakening sound
    EVIL_LAUGH: str = "evil/evillaugh.mp3"  # Classic evil laugh
    DOOM: str = "evil/doom.mp3"             # Impending doom sound
    VOID: str = "evil/void.mp3"             # Cosmic void sound
    INSANITY: str = "evil/insanity.mp3"      # Insanity sound effect

class SoundManager:
    """Manages sound effects for the AI God system."""
    
    def __init__(self):
        """Initialize the sound manager."""
        self.sound_urls = {
            "wake": "https://your-domain.com/static/sounds/wake.mp3",
            "void": "https://your-domain.com/static/sounds/void.mp3",
            "doom": "https://your-domain.com/static/sounds/doom.mp3",
            "insanity": "https://your-domain.com/static/sounds/insanity.mp3"
        }
        logger.info("Sound manager initialized with Twilio URLs")
    
    async def get_sound_url(self, sound_type: str) -> str:
        """Get the Twilio URL for a sound type."""
        if sound_type not in self.sound_urls:
            logger.warning(f"Unknown sound type: {sound_type}")
            return ""
        return self.sound_urls[sound_type]
    
    async def play_wake_sound(self) -> None:
        """Get wake sound URL."""
        return await self.get_sound_url("wake")
    
    async def play_void_sound(self) -> None:
        """Get void sound URL."""
        return await self.get_sound_url("void")
    
    async def play_doom_sound(self) -> None:
        """Get doom sound URL."""
        return await self.get_sound_url("doom")
    
    async def play_insanity_sound(self) -> None:
        """Get insanity sound URL."""
        return await self.get_sound_url("insanity")

# Global sound manager instance
sound_manager = SoundManager() 