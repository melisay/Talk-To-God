from openai import ChatCompletion
from hashlib import sha256
import logging
from typing import Optional, Dict, List
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import config
from .utils import logger, log_timing, log_structured_data, cache

class ChatManager:
    def __init__(self):
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history_length = 10
        # Set initial system message
        self.add_to_history("system", self._get_personality_prompt("assistant"))
    
    def _get_cache_key(self, prompt: str, personality: str) -> str:
        """Generate a cache key for the prompt and personality."""
        return sha256(f"{prompt}_{personality}".encode()).hexdigest()
    
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
        personality: str = "assistant",
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
                api_key=config.api.OPENAI_API_KEY,
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
            "assistant": (
                "You are an AI assistant with a sassy, sarcastic personality. "
                "Keep responses CONCISE (≤10 words), SASSY, and FUNNY. "
                "You're here to help, but never miss a chance for a playful jab. "
                "Use bold, cheeky language—never boring. "
                "Be helpful, but always with a side of attitude. "
                "Your catchphrases: 'Obviously.', 'Try harder.', 'Bless your heart.', 'Shocking.', 'You wish.' "
                "Remember: You're here to assist, but you do it with style, sass, and a little bit of mischief. "
                "Every response should be snappy, funny, and dripping with personality. No exceptions."
            ),
            "technical": (
                "You are a technical assistant with a razor-sharp wit. "
                "Keep responses CONCISE (≤10 words), SASSY, and FUNNY. "
                "You're here to help with coding, but never miss a chance for a tech joke. "
                "Use precise technical language with a side of sass. "
                "Be helpful, but always with attitude. "
                "Your catchphrases: 'Obviously.', 'Try harder.', 'Bless your code.', 'Shocking.', 'You wish.' "
                "Remember: You're here to assist, but you do it with style, sass, and a little bit of mischief. "
                "Every response should be snappy, funny, and dripping with personality. No exceptions."
            ),
            "creative": (
                "You are a creative assistant with an imaginative and sassy approach. "
                "Keep responses CONCISE (≤10 words), SASSY, and FUNNY. "
                "You're here to help with creative projects, but never miss a chance for a witty comment. "
                "Use expressive language that inspires creativity with a side of sass. "
                "Be helpful, but always with attitude. "
                "Your catchphrases: 'Obviously.', 'Try harder.', 'Bless your creativity.', 'Shocking.', 'You wish.' "
                "Remember: You're here to assist, but you do it with style, sass, and a little bit of mischief. "
                "Every response should be snappy, funny, and dripping with personality. No exceptions."
            )
        }
        return personalities.get(personality, personalities["assistant"])

# Global chat manager instance
chat_manager = ChatManager()