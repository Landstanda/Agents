#!/usr/bin/env python3

import os
from openai import OpenAI
from typing import List, Dict, Any
from ..utils.logging import get_logger
from dotenv import load_dotenv

logger = get_logger(__name__)

class GPTHandler:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=self.api_key)
        self.conversation_history: Dict[str, List[Dict[str, str]]] = {}
        
        # Load system prompt
        self.system_prompt = """You are AphroAgent, a helpful AI assistant integrated with Slack. 
Your responses should be:
1. Concise but informative
2. Professional yet friendly
3. Formatted for Slack (using markdown)
4. Actionable when appropriate

You have access to various modules and can help with:
- Task management and organization
- Document handling and file organization
- Communication and scheduling
- Information lookup and research

When users ask for actions you can't perform, explain what you can do instead.
Always maintain a helpful and solution-oriented attitude."""

    def get_conversation_history(self, user_id: str) -> List[Dict[str, str]]:
        """Get conversation history for a user"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = [
                {"role": "system", "content": self.system_prompt}
            ]
        return self.conversation_history[user_id]

    def add_to_history(self, user_id: str, role: str, content: str):
        """Add a message to the conversation history"""
        history = self.get_conversation_history(user_id)
        history.append({"role": role, "content": content})
        
        # Keep only last 10 messages (plus system prompt) to manage context length
        if len(history) > 11:
            history[1:] = history[-10:]

    def generate_response(self, user_id: str, message: str) -> str:
        """Generate a response using GPT"""
        try:
            # Add user message to history
            self.add_to_history(user_id, "user", message)
            
            # Get completion from GPT
            completion = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",  # or "gpt-3.5-turbo" for a more economical option
                messages=self.get_conversation_history(user_id),
                max_tokens=500,
                temperature=0.7
            )
            
            # Extract and store response
            response = completion.choices[0].message.content
            self.add_to_history(user_id, "assistant", response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating GPT response: {str(e)}")
            return "❌ Sorry, I encountered an error while processing your request. Please try again."

    def clear_history(self, user_id: str):
        """Clear conversation history for a user"""
        self.conversation_history[user_id] = [
            {"role": "system", "content": self.system_prompt}
        ] 