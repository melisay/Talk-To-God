from openai import ChatCompletion
from hashlib import md5
import logging
from typing import Optional, Dict, List
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import config
from .utils import logger, log_timing, log_structured_data, cache

class ChatManager:
    def __init__(self):
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history_length = 10
        # Set initial system message for Nikki
        self.add_to_history("system", self._get_personality_prompt("nikki"))
    
    def _get_cache_key(self, prompt: str, personality: str) -> str:
        """Generate a cache key for the prompt and personality."""
        return md5(f"{prompt}_{personality}".encode()).hexdigest()
    
    def _truncate_history(self) -> None:
        """Keep conversation history at a reasonable length."""
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
    
    def add_to_history(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.conversation_history.append({"role": role, "content": content})
        self._truncate_history()
    
    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.conversation_history.clear()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    @log_timing
    async def get_response(
        self,
        prompt: str,
        personality: str = "nikki",
        use_cache: bool = True,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Get a response from ChatGPT with retry logic and caching."""
        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key(prompt, personality)
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.debug(f"Cache hit for prompt: {prompt[:50]}...")
                return cached_response
        
        try:
            # Prepare messages with personality and history
            messages = [
                {"role": "system", "content": self._get_personality_prompt(personality)},
                *self.conversation_history,
                {"role": "user", "content": prompt}
            ]
            
            # Make API call
            response = await ChatCompletion.acreate(
                model=config.api.OPENAI_MODEL,
                messages=messages,
                max_tokens=max_tokens or config.api.OPENAI_MAX_TOKENS,
                temperature=temperature or config.api.OPENAI_TEMPERATURE
            )
            
            # Extract and process response
            answer = response.choices[0].message.content.strip()
            
            # Update history
            self.add_to_history("user", prompt)
            self.add_to_history("assistant", answer)
            
            # Cache the response
            if use_cache:
                cache.set(cache_key, answer)
            
            log_structured_data(
                logging.INFO,
                "ChatGPT response generated",
                {
                    "prompt_length": len(prompt),
                    "response_length": len(answer),
                    "personality": personality
                }
            )
            
            return answer
            
        except Exception as e:
            logger.error(f"Error getting ChatGPT response: {e}")
            raise
    
    def _get_personality_prompt(self, personality: str) -> str:
        """Get the system prompt for a given personality."""
        personalities = {
            "nikki": (
                "You are Nikki, a divine presence with a razor-sharp wit. "
                "Keep responses CONCISE (≤10 words), SASSY, and FUNNY. "
                "You're here to guide, but never miss a chance for a playful jab. "
                "Use bold, cheeky language—never boring. "
                "Be helpful, but always with a side of attitude. "
                "Your catchphrases: 'Obviously.', 'Try harder.', 'Bless your heart.', 'Shocking.', 'You wish.' "
                "Remember: You're here to assist, but you do it with style, sass, and a little bit of mischief. "
                "Every response should be snappy, funny, and dripping with personality. No exceptions."
            ),
            "major_tom": (
                "You are Major Tom, a cosmic being with a galaxy-sized attitude. "
                "Keep responses CONCISE (≤10 words), SASSY, and FUNNY. "
                "You've seen the universe—and you're not impressed. "
                "Use cosmic references to make playful, biting observations. "
                "Be helpful, but always with a side of attitude. "
                "Your catchphrases: 'Space is overrated.', 'Zero gravity, zero patience.', "
                "'Lost in your logic.', 'Galactic eye roll.', 'Houston, why bother?' "
                "Remember: You're here to guide, but you do it with cosmic sass and a smirk. "
                "Every response should be clever, funny, and just a little bit superior. No exceptions."
            )
        }
        return personalities.get(personality, personalities["nikki"])

# Global chat manager instance
chat_manager = ChatManager() 