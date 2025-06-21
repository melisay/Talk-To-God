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
    WAKE_UP: str = "wakeup.mp3"      # Sinister awakening sound
    DOOM: str = "doom.mp3"             # Impending doom sound
    VOID: str = "void.mp3"             # Cosmic void sound
    RIMSHOT: str = "rimshot.mp3"       # Comedy rimshot for jokes
    TOM: str = "tom.mp3"               # Major Tom voice switch sound
    NIKKI: str = "nikki.mp3"           # Nikki voice switch sound
    LIGHTNING: str = "lightning.mp3"   # Lightning effect
    INSANITY: str = "insanity.mp3"     # Insanity effect

class SoundManager:
    """Manages sound effects and audio feedback."""
    
    def __init__(self):
        """Initialize the sound manager."""
        self.sounds_dir = Path(__file__).parent.parent.parent / "shared" / "sounds"
        self.sounds_dir = Path(__file__).parent.parent / "sounds"
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self.current_volume = 0.5  # Reduced default volume
        self.is_muted = False
        self.last_sound_time = 0
        self.min_sound_interval = 15  # 15 seconds between sounds
        self.sound_count = 0  # Track total sounds played
        self.max_sounds_per_session = 3  # Only 3 sounds per session
        self.sound_skip_chance = 0.87  # 87% chance to skip any non-wake sound (13% play chance)
        self._initialize_sounds()
    
    def _initialize_sounds(self) -> None:
        """Initialize pygame mixer and load sound effects."""
        try:
            pygame.mixer.init()
            self._load_sounds()
            logger.info("Sound system initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize sound system: {e}")
    
    def _load_sounds(self) -> None:
        """Load all sound effects from the sounds directory."""
        if not self.sounds_dir.exists():
            self.sounds_dir.mkdir(exist_ok=True)
            logger.warning(f"Created sounds directory at {self.sounds_dir}")
            return
        
        # Load each sound effect
        for sound_name, sound_file in vars(SoundEffects).items():
            if not sound_name.startswith('_'):
                file_path = self.sounds_dir / sound_file
                if file_path.exists():
                    try:
                        self.sounds[sound_name] = pygame.mixer.Sound(str(file_path))
                        logger.debug(f"Loaded sound effect: {sound_name}")
                    except Exception as e:
                        logger.error(f"Failed to load sound {sound_name}: {e}")
                else:
                    logger.warning(f"Sound file not found: {sound_file}")
    
    async def _can_play_sound(self, force: bool = False) -> bool:
        """Check if a sound can be played based on various conditions."""
        # Wake-up sequence always plays
        if force:
            return True
            
        current_time = asyncio.get_event_loop().time()
        
        # Check if we've reached the maximum sounds for this session
        if self.sound_count >= self.max_sounds_per_session:
            logger.debug("Maximum sounds per session reached")
            return False
            
        # Check if enough time has passed since the last sound
        if current_time - self.last_sound_time < self.min_sound_interval:
            logger.debug("Minimum interval between sounds not met")
            return False
            
        # 87% chance to skip any non-wake sound (13% chance to play)
        if random.random() < self.sound_skip_chance:
            logger.debug("Sound skipped by random chance (87% skip rate)")
            return False
            
        self.last_sound_time = current_time
        self.sound_count += 1
        return True
    
    async def play_sound(self, sound_name: str, wait: bool = False, force: bool = False) -> None:
        """Play a sound effect if conditions are met.
        
        Args:
            sound_name: Name of the sound effect to play
            wait: Whether to wait for the sound to finish playing
            force: Whether to force play the sound (bypasses all checks except mute)
        """
        if (self.is_muted or 
            sound_name not in self.sounds or 
            not await self._can_play_sound(force)):
            return
            
        try:
            sound = self.sounds[sound_name]
            sound.set_volume(self.current_volume)
            sound.play()
            logger.info(f"Playing sound: {sound_name}")
            
            if wait:
                while pygame.mixer.get_busy():
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Error playing sound {sound_name}: {e}")
    
    def set_volume(self, volume: float) -> None:
        """Set the volume for all sounds."""
        self.current_volume = max(0.0, min(1.0, volume))
        for sound in self.sounds.values():
            sound.set_volume(self.current_volume)
    
    def mute(self) -> None:
        """Mute all sounds."""
        self.is_muted = True
        pygame.mixer.pause()
    
    def unmute(self) -> None:
        """Unmute all sounds."""
        self.is_muted = False
        pygame.mixer.unpause()
    
    async def play_wake_sound(self) -> None:
        """Play wake up sound effect - only on initial wake."""
        # Wake-up sequence is forced to play
        await self.play_sound("WAKE_UP", force=True)
        await asyncio.sleep(1)
    
    async def play_doom_sound(self) -> None:
        """Play doom sound effect - only for truly significant events."""
        await self.play_sound("DOOM")
    
    async def play_void_sound(self) -> None:
        """Play void sound effect - only for major personality changes."""
        await self.play_sound("VOID")
    
    async def play_rimshot(self) -> None:
        """Play rimshot sound effect - for jokes and comedy moments."""
        await self.play_sound("RIMSHOT")
    
    async def play_tom_sound(self) -> None:
        """Play Tom voice switch sound effect."""
        await self.play_sound("TOM", force=True)
    
    async def play_nikki_sound(self) -> None:
        """Play Nikki voice switch sound effect."""
        await self.play_sound("NIKKI", force=True)
    
    async def play_random_idle_sound(self) -> None:
        """Play a random idle sound effect (5% chance each)."""
        if random.random() < 0.05:  # 5% chance for lightning
            await self.play_sound("LIGHTNING")
        elif random.random() < 0.05:  # 5% chance for insanity
            await self.play_sound("INSANITY")

# Global sound manager instance
sound_manager = SoundManager() 