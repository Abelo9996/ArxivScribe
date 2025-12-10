"""OpenAI API provider for LLM summarization."""
import os
import logging
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """OpenAI API provider for generating summaries."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.3,
        max_tokens: int = 150
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
        
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def generate(self, prompt: str) -> str:
        """
        Generate text using OpenAI API.
        
        Args:
            prompt: Input prompt
            
        Returns:
            Generated text
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful AI research assistant that generates concise summaries."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.API_URL, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenAI API error: {response.status} - {error_text}")
                        raise Exception(f"OpenAI API returned status {response.status}")
                    
                    data = await response.json()
                    
                    # Extract generated text
                    if "choices" in data and len(data["choices"]) > 0:
                        return data["choices"][0]["message"]["content"].strip()
                    else:
                        logger.error("Unexpected OpenAI API response format")
                        raise Exception("Invalid response from OpenAI API")
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error calling OpenAI API: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating with OpenAI: {e}")
            raise
