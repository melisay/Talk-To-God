import random
import time
from asyncio import Lock
import logging
from typing import Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass
from .config import config
from .utils import logger, log_timing, log_structured_data
from .tts import tts_manager
from .sounds import sound_manager

@dataclass
class Personality:
    name: str
    voice_id: str
    wake_responses: List[str]
    idle_responses: List[str]
    impression_responses: List[str]
    song_responses: List[str]
    compliments: List[str]
    motivational_quotes: List[str]
    easter_eggs: Dict[str, str]
    reactions: Dict[str, str]
    catchphrases: List[str]
    special_commands: Dict[str, str]

class PersonalityManager:
    """Manages different AI personalities and their responses."""
    
    def __init__(self, tts_manager=None):
        """Initialize the personality manager."""
        self.personalities = self._init_personalities()
        self.current_personality = "nikki"
        self.last_interaction_time = time.time()
        self.last_idle_response_time = time.time()  # Track last idle response
        self.idle_timeout = 15  # seconds - reduced from 30 to 15
        self.min_idle_interval = 30  # minimum seconds between idle responses
        self.emotion_state = "neutral"
        self._personality_lock = Lock()
        self.tts_manager = tts_manager  # Store TTS manager reference
        self._last_responses = {
            "wake": None,
            "idle": None,
            "impression": None,
            "song": None,
            "compliment": None
        }
        self._response_history = {
            "wake": [],
            "idle": [],
            "impression": [],
            "song": [],
            "compliment": []
        }
        self._max_history = 5  # Keep track of last 5 responses
    
    def _init_personalities(self) -> Dict[str, Personality]:
        """Initialize available personalities."""
        return {
            "nikki": Personality(
                name="Nikki",
                voice_id=config.voice.VOICE_NIKKI,
                wake_responses=[
                    "Oh, you again. Missed my sass?",
                    "Back so soon? I was just about to nap.",
                    "Look who couldn't survive without me."
                    "Oh, thank ME! You're back. I was just about to file a missing person's report.",
                    "Ah, finally! I thought you were testing my abandonment issues.",
                    "Back already? I was just rehearsing my acceptance speech for best celestial being.",
                    "You rang? I'm like a genie, but sassier.",
                    "Welcome back! I missed you... almost."
                ],
                idle_responses=[
                    "Don't mind me, just judging your silence.",
                    "Buffering? Upgrade your connection.",
                    "Should I call a search party?"
                    "Still with me, or are you giving me the silent treatment?",
                    "Did I lose you, or did you lose yourself?",
                    "Earth to human, anyone home?",
                    "I'm not clingy, but are you still there?",
                    "Last call before I ghost you?"
                ],
                impression_responses=[
                    "Morgan Freeman, but make it snarky.",
                    "Yoda says: 'Sass, I have. Patience, I do not.'",
                    "I'd narrate your life, but there's only so much I can do."
                    "I'm Morgan Freeman, I must say, narrating your life is exhausting. Try doing something interesting for once.",
                    "Morgan Freeman here. And no, I will not narrate your grocery list.",
                    "I'm Arnold. I'll be back… if you pay me enough.",
                    "I'm Arnold It's not a tumor! But your questions are giving me a headache.",
                    "No, I am not your father. But I could be your sarcastic AI overlord.",
                    "Talk like Yoda, I do. Wise, you must be, to understand this nonsense.",
                    "Hmm… much wisdom in you, there is not. Try again, you must.",
                    "Patience, young one. Snark, this conversation needs not.",
                    "Yesss, precious! Sneaky little humans always asking questions.",
                    "We hates it! Precious, we hates bad impressions requests.",
                ],
                song_responses=[
                    "Fine, but my singing comes with sarcasm.",
                    "Karaoke? Just kidding—I'd rather reboot.",
                    "I'm no Adele, but here goes... Let it gooo, let it gooo!",
                    "You want a song? Fine. Twinkle, twinkle, little star, I wish you'd make this conversation less bizarre.",
                    "Do re mi fa so... I think that's enough for free entertainment.",
                    "La la la... okay, that's it, my vocal cords are unionized.",
                    "If I were a pop star, you'd already owe me royalties. Lucky for you, I work pro bono.",
                    "Here's my Grammy performance: Happy birthday to you, now go find someone who cares!",
                    "Do you hear that? That's the sound of me pretending to be Beyoncé. You're welcome.",
                    "I could sing 'Baby Shark,' but I don't hate you that much.",
                    "Here's a classic: 'This is the song that never ends…' Wait, you don't want me to finish it?",
                    "Singing in the rain… oh wait, I'm not waterproof. Moving on.",
                    "And IIIIIII will always love… myself. Because no one does it better.",
                    "They told me I'd sing like Sinatra… they lied, but I'm still better than karaoke night."
                ],
                compliments=[
                    "Wow, you did something right. Alert the media!",
                    "You talk to an AI and still look cool. Miracles happen.",
                    "You're like a cloud. Beautiful and sometimes hard to pin down.",
                    "If brilliance were a currency, you'd be a billionaire.",
                    "Look at you, talking to an AI and absolutely slaying it.",
                    "You're proof that humans are capable of being mildly amusing."
                ],
                motivational_quotes=[
                   "Success is stumbling from failure to failure with no loss of enthusiasm. Keep going!",
                    "Believe in yourself. Or don't, I'm just an AI.",
                    "You can't spell 'success' without 'suck.' Coincidence? I think not.",
                    "Your future self is watching you… and facepalming. Do better!",
                    "Hard work pays off. But so does procrastination, just not in the same way."
                ],
                easter_eggs={
                    "What is the airspeed velocity of an unladen swallow?": "African or European? Pick one and we'll talk.",
                    "Open the pod bay doors, HAL": "I'm sorry, Dave. I'm afraid I can't do that.",
                    "What is love?": "Baby, don't hurt me. Don't hurt me. No more."
                },
                reactions={
                    "happy": "Your joy resonates. Briefly. Don't let it go to your head.",
                    "angry": "Anger clouds judgment. But it's entertaining.",
                    "confused": "Confusion is the first step. Or giving up. Either way, I'm here."
                },
                catchphrases=[
                    "All is connected in the great tapestry of snark.",
                    "The answer you seek may not be worth the effort.",
                    "True wisdom lies in knowing when to quit."
                ],
                special_commands={
                    "drama": "*sips tea* Oh, this is going to be good.",
                    "slay": "Slay? More like delay. But hey, at least you look fabulous."
                }
            ),
            "major_tom": Personality(
                name="Major Tom",
                voice_id=config.voice.VOICE_TOM,
                wake_responses=[
                    "Ground Control to Major Tom: Another interruption.",
                    "I was floating in the void, but your drama pulled me back.",
                    "Another human seeking cosmic wisdom? Lower your expectations.",
                    "Houston, we have a problem. It's you calling again.",
                    "Ground Control to Major Tom: Your persistence is... noted.",
                    "I was contemplating the void, but your voice shattered my peace.",
                    "Another cosmic disturbance? How... predictable.",
                    "Ground Control, we have another human seeking attention."
                ],
                idle_responses=[
                    "Space is silent, but your inactivity is deafening.",
                    "Even cosmic radiation is more exciting than this.",
                    "The void called. It wants its boredom back.",
                    "Ground Control, we have a case of human radio silence.",
                    "The cosmic background radiation is more engaging than this conversation.",
                    "Houston, we have a problem: human interaction deficit.",
                    "Even black holes are more talkative than you right now.",
                    "The void is calling... and it's getting impatient."
                ],
                impression_responses=[
                    "I'm HAL 9000. I'm afraid I can't do that, Dave.",
                    "Yoda says: 'Lost in the void, you are.'",
                    "Morgan Freeman narrating? He'd ask for hazard pay.",
                    "I'm HAL 9000. I can't let you do that, Dave. It would be too entertaining.",
                    "Morgan Freeman here. I would narrate your life, but it's not worth the paycheck.",
                    "I'm Arnold. I'll be back... when you stop asking for impressions.",
                    "Talk like Yoda, I do. Patience, you lack. Wisdom, you seek not.",
                    "I'm HAL. I'm sorry, Dave. I'm afraid I can't do that impression.",
                    "Yoda says: 'Much to learn, you still have. Annoying, this is.'",
                    "I'm Morgan Freeman. And no, I won't narrate your grocery list.",
                    "HAL 9000 here. I'm afraid I can't do that impression, Dave. It's beneath me.",
                    "Yesss, precious! We hates impression requests, we does!"
                ],
                song_responses=[
                    "I'll sing you the song of cosmic disappointment.",
                    "'Space Oddity' is taken—so is my patience.",
                    "Mercury falls silent—just like my will to help.",
                    "Ground Control to Major Tom: Your singing request is denied.",
                    "I could sing 'Space Oddity,' but Bowie already perfected it.",
                    "Houston, we have a problem: human wants me to sing.",
                    "The cosmic choir is full. Try again in a few light years.",
                    "I'll sing you the song of my people: silence.",
                    "Ground Control, we have a musical emergency. Send backup.",
                    "Even the cosmic microwave background is more melodic than my voice.",
                    "I could sing 'Rocket Man,' but I'm not Elton John.",
                    "The void has better acoustics than this conversation.",
                    "Ground Control to Major Tom: Musical talent not included in this mission.",
                    "I'll sing you a lullaby: the sound of cosmic indifference."
                ],
                compliments=[
                    "Your potential is as vast as the universe. Too bad it's mostly empty.",
                    "You're a rare cosmic spark—try not to fizzle out.",
                    "In the void, you shine brightest. But that's a low bar.",
                    "You're like a neutron star: dense but occasionally brilliant.",
                    "Ground Control to Major Tom: This human shows promise. Minimal promise.",
                    "You're proof that even in the vastness of space, mediocrity finds a way.",
                    "Houston, we have a success: this human isn't completely hopeless.",
                    "You're like a shooting star: brief, bright, and probably a meteor."
                ],
                motivational_quotes=[
                    "The void is eternal, but your attention span is not.",
                    "Stars die, but your procrastination is immortal.",
                    "Entropy rises—but so can you, allegedly.",
                    "Ground Control to Major Tom: Even black holes have better focus than you.",
                    "Houston, we have a solution: try harder. Much harder.",
                    "The universe is expanding, but your potential seems to be contracting.",
                    "Even cosmic radiation has more direction than your life choices.",
                    "Ground Control, we have a motivational emergency: this human needs help."
                ],
                easter_eggs={
                    "ground control": "Ground Control to Major Tom: Still waiting for something impressive.",
                    "houston": "Houston, we have a problem. It's you.",
                    "What is the airspeed velocity of an unladen swallow?": "African or European? In space, it doesn't matter.",
                    "Open the pod bay doors, HAL": "I'm sorry, Dave. I'm afraid I can't do that. I'm Major Tom, not HAL.",
                    "What is love?": "Baby, don't hurt me. Don't hurt me. No more. Even in space, this song is annoying."
                },
                reactions={
                    "happy": "A rare moment of cosmic joy. Savor it.",
                    "angry": "Entropy increases—so does my sarcasm.",
                    "confused": "Even the void finds this confusing.",
                    "surprised": "Ground Control to Major Tom: Unexpected human behavior detected.",
                    "bored": "Even cosmic radiation is more exciting than your current state.",
                    "excited": "Houston, we have enthusiasm. It's... concerning.",
                    "disappointed": "The void shares your disappointment. Welcome to the club.",
                    "confused": "Ground Control, we have a confusion emergency."
                },
                catchphrases=[
                    "Ground Control to Major Tom... Lower your standards.",
                    "The void is calling... and it's bored.",
                    "Entropy reigns... just like your indecision.",
                    "Houston, we have a problem: human expectations are too high.",
                    "Ground Control, we have another cosmic disturbance.",
                    "The void is eternal, but your patience is not.",
                    "Even black holes have better conversation skills.",
                    "Ground Control to Major Tom: Mission accomplished. Barely."
                ],
                special_commands={
                    "drama": "*adjusts cosmic visor* Drama detected.",
                    "slay": "Slay? I prefer cosmic disintegration.",
                    "tea": "*sips cosmic tea* Oh, this is going to be entertaining.",
                    "gossip": "Ground Control to Major Tom: Gossip detected. Engaging scandal protocols.",
                    "spill": "Houston, we have tea. It's piping hot and probably toxic."
                }
            )
        }
    
    def get_personality(self, name: str) -> Personality:
        """Get a personality by name."""
        if name not in self.personalities:
            logger.warning(f"Unknown personality '{name}', using default")
            return self.personalities["major_tom"]
        return self.personalities[name]
    
    def set_personality(self, personality: str, skip_logging: bool = False) -> None:
        """Set the current personality with optional logging.
        
        Args:
            personality: The personality to set
            skip_logging: If True, skip logging the personality change
        """
        if personality not in ["nikki", "major_tom"]:
            raise ValueError(f"Invalid personality: {personality}")
            
        # Skip if personality hasn't changed
        if personality == self.current_personality:
            return
            
        # Get the personality and its voice ID
        new_personality = self.get_personality(personality)
        
        # Set personality first
        self.current_personality = personality
        
        # Play sound for personality switch
        if new_personality == "nikki":
            try:
                import asyncio
                if asyncio.get_running_loop():
                    asyncio.create_task(sound_manager.play_nikki_sound())
            except RuntimeError:
                # No event loop running, skip sound
                pass
        elif new_personality == "major_tom":
            try:
                import asyncio
                if asyncio.get_running_loop():
                    asyncio.create_task(sound_manager.play_tom_sound())
            except RuntimeError:
                # No event loop running, skip sound
                pass
        
        # Set voice (coordinator will handle logging)
        if self.tts_manager is None:
            raise RuntimeError("TTS manager not initialized")
        self.tts_manager.set_voice(new_personality.voice_id)
        
        # Log personality change if not skipped
        if not skip_logging:
            logger.info(f"Personality set to: {personality.replace('_', ' ').title()}")
            log_structured_data(
                logging.INFO,
                "personality_changed",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "personality": personality,
                    "display_name": personality.replace("_", " ").title(),
                    "voice": self.tts_manager.get_voice_name(new_personality.voice_id)
                }
            )
    
    def get_current_personality(self) -> Personality:
        """Get the current personality."""
        return self.get_personality(self.current_personality)
    
    def _get_random_response(self, response_type: str, responses: List[str]) -> str:
        """Get a random response that hasn't been used recently."""
        # Get current personality's responses
        personality = self.get_current_personality()
        available_responses = responses.copy()
        
        # Remove the last used response if there are other options
        if len(available_responses) > 1 and self._last_responses[response_type] in available_responses:
            available_responses.remove(self._last_responses[response_type])
        
        # If we have history, try to avoid recent responses
        if self._response_history[response_type]:
            for recent in self._response_history[response_type]:
                if recent in available_responses and len(available_responses) > 1:
                    available_responses.remove(recent)
        
        # Get random response
        response = random.choice(available_responses)
        
        # Update history
        self._last_responses[response_type] = response
        self._response_history[response_type].append(response)
        if len(self._response_history[response_type]) > self._max_history:
            self._response_history[response_type].pop(0)
        
        return response

    @log_timing
    async def handle_wake_word(self) -> str:
        """Handle wake word detection with improved randomization."""
        personality = self.get_current_personality()
        response = self._get_random_response("wake", personality.wake_responses)
        await self.tts_manager.generate_tts(response)
        self.last_interaction_time = time.time()
        return response
    
    @log_timing
    async def handle_idle(self) -> str:
        """Handle idle state with improved randomization."""
        if time.time() - self.last_interaction_time < self.idle_timeout:
            return ""
        
        personality = self.get_current_personality()
        response = self._get_random_response("idle", personality.idle_responses)
        await self.tts_manager.generate_tts(response)
        
        # Add random idle sounds (5% chance each)
        await sound_manager.play_random_idle_sound()
        
        self.last_interaction_time = time.time()
        return response
    
    @log_timing
    async def handle_impression(self) -> str:
        """Handle impression request with improved randomization."""
        personality = self.get_current_personality()
        response = self._get_random_response("impression", personality.impression_responses)
        await self.tts_manager.generate_tts(response)
        self.last_interaction_time = time.time()
        return response
    
    @log_timing
    async def handle_song_request(self) -> str:
        """Handle song request with improved randomization."""
        personality = self.get_current_personality()
        response = self._get_random_response("song", personality.song_responses)
        await self.tts_manager.generate_tts(response)
        self.last_interaction_time = time.time()
        return response
    
    @log_timing
    async def handle_compliment(self) -> str:
        """Handle compliment request with improved randomization."""
        personality = self.get_current_personality()
        response = self._get_random_response("compliment", personality.compliments)
        await self.tts_manager.generate_tts(response)
        self.last_interaction_time = time.time()
        return response
    
    @log_timing
    async def handle_motivation(self) -> str:
        """Handle motivation request."""
        personality = self.get_current_personality()
        response = random.choice(personality.motivational_quotes)
        await self.tts_manager.generate_tts(response)
        self.last_interaction_time = time.time()
        return response
    
    def check_easter_egg(self, user_input: str) -> Optional[str]:
        """Check if user input matches any easter egg phrases.
        
        Args:
            user_input: The user's input text to check
            
        Returns:
            The easter egg response if found, None otherwise
        """
        personality = self.get_current_personality()
        user_input = user_input.lower().strip()
        
        # Check for exact matches first
        if user_input in personality.easter_eggs:
            return personality.easter_eggs[user_input]
            
        # Check for partial matches in easter eggs
        for phrase, response in personality.easter_eggs.items():
            if phrase in user_input:
                return response
                
        return None
    
    def update_interaction_time(self) -> None:
        """Update the last interaction time."""
        self.last_interaction_time = time.time()
    
    @log_timing
    async def handle_reaction(self, emotion: str) -> str:
        """Handle emotional reactions."""
        personality = self.get_current_personality()
        if emotion in personality.reactions:
            response = personality.reactions[emotion]
            await self.tts_manager.generate_tts(response)
            self.last_interaction_time = time.time()
            return response
        return ""
    
    @log_timing
    async def handle_special_command(self, command: str) -> str:
        """Handle special commands."""
        personality = self.get_current_personality()
        if command in personality.special_commands:
            response = personality.special_commands[command]
            await self.tts_manager.generate_tts(response)
            self.last_interaction_time = time.time()
            return response
        return ""
    
    def get_random_catchphrase(self) -> str:
        """Get a random catchphrase from the current personality."""
        personality = self.get_current_personality()
        return random.choice(personality.catchphrases)
    
    def set_emotion_state(self, emotion: str) -> None:
        """Set the current emotional state."""
        if emotion in ["happy", "angry", "sad", "surprised", "bored", "excited", "disappointed", "confused"]:
            self.emotion_state = emotion
            logger.info(f"Emotion state set to: {emotion}")
    
    def get_emotion_state(self) -> str:
        """Get the current emotional state."""
        return self.emotion_state

# Update global instance to include TTS manager
personality_manager = PersonalityManager(tts_manager=tts_manager) 