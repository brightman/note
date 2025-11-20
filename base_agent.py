"""
Base agent class for the multi-agent system
"""
from anthropic import Anthropic
from typing import List, Dict, Any


class BaseAgent:
    """Base class for all agents in the system"""

    def __init__(self, api_key: str, name: str, system_prompt: str):
        self.client = Anthropic(api_key=api_key)
        self.name = name
        self.system_prompt = system_prompt
        self.conversation_history: List[Dict[str, Any]] = []

    def send_message(self, message: str, max_tokens: int = 4096) -> str:
        """Send a message to Claude and get a response"""
        self.conversation_history.append({
            "role": "user",
            "content": message
        })

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=self.system_prompt,
            messages=self.conversation_history
        )

        assistant_message = response.content[0].text

        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        return assistant_message

    def reset_conversation(self):
        """Reset the conversation history"""
        self.conversation_history = []
