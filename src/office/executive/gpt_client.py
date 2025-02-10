import os
import logging
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class GPTClient:
    """Client for interacting with ChatGPT API."""
    
    def __init__(self):
        """Initialize the GPT client."""
        load_dotenv()
        
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
            
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = "gpt-4-1106-preview"  # Using the latest GPT-4 model
        
    async def get_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Get a completion from ChatGPT.
        
        Args:
            prompt (str): The user's prompt
            system_prompt (Optional[str]): Optional system prompt for context
            temperature (float): Sampling temperature (0-1)
            
        Returns:
            Dict containing:
                - status: str ('success' or 'error')
                - content: Optional[str] - The response content
                - error: Optional[str] - Error message if status is 'error'
        """
        try:
            messages = []
            
            # Add system prompt if provided
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
                
            # Add user prompt
            messages.append({"role": "user", "content": prompt})
            
            # Get completion
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
            
            return {
                "status": "success",
                "content": response.choices[0].message.content,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error in GPT completion: {str(e)}")
            return {
                "status": "error",
                "content": None,
                "error": str(e)
            } 