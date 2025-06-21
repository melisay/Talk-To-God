from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import os
import time
from datetime import datetime
from .utils import logger, log_structured_data
from .performance import monitor_operation

@dataclass
class UserProfile:
    """User profile with conversation history and preferences."""
    name: str
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    personality_preference: str = "default"  # default or major_tom
    topics_of_interest: List[str] = field(default_factory=list)
    favorite_quotes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert profile to dictionary for storage."""
        return {
            "name": self.name,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "conversation_history": self.conversation_history[-10:],  # Keep last 10 interactions
            "personality_preference": self.personality_preference,
            "topics_of_interest": self.topics_of_interest,
            "favorite_quotes": self.favorite_quotes
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserProfile':
        """Create profile from dictionary."""
        return cls(
            name=data["name"],
            first_seen=datetime.fromisoformat(data["first_seen"]),
            last_seen=datetime.fromisoformat(data["last_seen"]),
            conversation_history=data["conversation_history"],
            personality_preference=data["personality_preference"],
            topics_of_interest=data["topics_of_interest"],
            favorite_quotes=data["favorite_quotes"]
        )

class UserManager:
    def __init__(self):
        self.users: Dict[str, UserProfile] = {}
        self.current_user: Optional[UserProfile] = None
        self.storage_file = "data/users.json"
        self._load_users()
    
    def _load_users(self) -> None:
        """Load user profiles from storage."""
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    self.users = {
                        name: UserProfile.from_dict(profile_data)
                        for name, profile_data in data.items()
                    }
                logger.info(f"Loaded {len(self.users)} user profiles")
        except Exception as e:
            logger.error(f"Error loading user profiles: {e}")
    
    def _save_users(self) -> None:
        """Save user profiles to storage."""
        try:
            data = {
                name: profile.to_dict()
                for name, profile in self.users.items()
            }
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("Saved user profiles")
        except Exception as e:
            logger.error(f"Error saving user profiles: {e}")
    
    @monitor_operation("user_recognition")
    def recognize_user(self, text: str) -> Optional[str]:
        """Try to recognize a user from the input text."""
        # Look for name mentions
        for name in self.users:
            if name.lower() in text.lower():
                return name
        
        # Look for "I am" or "my name is" patterns
        import re
        name_patterns = [
            r"i am (\w+)",
            r"my name is (\w+)",
            r"call me (\w+)",
            r"this is (\w+)"
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text.lower())
            if match:
                name = match.group(1).capitalize()
                return name
        
        return None
    
    @monitor_operation("user_management")
    def get_or_create_user(self, name: str) -> UserProfile:
        """Get existing user or create new one."""
        name = name.capitalize()
        if name not in self.users:
            self.users[name] = UserProfile(name=name)
            logger.info(f"Created new user profile for {name}")
            self._save_users()
        else:
            self.users[name].last_seen = datetime.now()
        
        self.current_user = self.users[name]
        return self.current_user
    
    def add_to_history(self, role: str, content: str) -> None:
        """Add a message to the current user's conversation history."""
        if self.current_user:
            self.current_user.conversation_history.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
            self._save_users()
    
    def get_recent_topics(self, limit: int = 3) -> List[str]:
        """Get recent topics from conversation history."""
        if not self.current_user:
            return []
        
        # Extract topics from recent conversations
        topics = []
        for msg in reversed(self.current_user.conversation_history):
            if msg["role"] == "user":
                # Simple topic extraction (can be enhanced with NLP)
                words = msg["content"].lower().split()
                if len(words) > 2:  # Only consider phrases
                    topics.append(" ".join(words[:3]))
                if len(topics) >= limit:
                    break
        
        return topics
    
    def update_personality_preference(self, personality: str) -> None:
        """Update user's personality preference."""
        if self.current_user:
            self.current_user.personality_preference = personality
            self._save_users()
    
    def get_personality_preference(self) -> str:
        """Get user's preferred personality."""
        if self.current_user:
            return self.current_user.personality_preference
        return "default"

# Global user manager instance
user_manager = UserManager() 