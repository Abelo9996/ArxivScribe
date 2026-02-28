"""OpenAI API provider for LLM summarization."""
import os
import logging
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """OpenAI API provider with retry logic."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 200
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY env var.")

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def generate(self, prompt: str) -> str:
        """Generate text using OpenAI API with retry."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a concise AI research assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        last_error = None
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.API_URL, json=payload, headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            if "choices" in data and data["choices"]:
                                return data["choices"][0]["message"]["content"].strip()
                            raise Exception("Invalid response from OpenAI API")

                        if response.status == 429:
                            import asyncio
                            retry_after = float(response.headers.get("Retry-After", 2 ** (attempt + 1)))
                            logger.warning(f"Rate limited, waiting {retry_after}s")
                            await asyncio.sleep(retry_after)
                            continue

                        error_text = await response.text()
                        raise Exception(f"OpenAI API {response.status}: {error_text[:200]}")

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Network error (attempt {attempt + 1}/3): {e}")
                import asyncio
                await asyncio.sleep(2 ** attempt)

        raise last_error or Exception("OpenAI API failed after retries")
