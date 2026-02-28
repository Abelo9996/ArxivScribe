"""HuggingFace API provider for LLM summarization."""
import asyncio
import os
import logging
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)


class HuggingFaceProvider:
    """HuggingFace Inference API provider with retry."""

    API_URL_TEMPLATE = "https://api-inference.huggingface.co/models/{model}"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "facebook/bart-large-cnn",
        max_length: int = 150,
        min_length: int = 30
    ):
        self.api_key = api_key or os.getenv("HUGGINGFACE_API_KEY")
        if not self.api_key:
            raise ValueError("HuggingFace API key not provided. Set HUGGINGFACE_API_KEY env var.")

        self.model = model
        self.api_url = self.API_URL_TEMPLATE.format(model=model)
        self.max_length = max_length
        self.min_length = min_length

    async def generate(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_length": self.max_length,
                "min_length": self.min_length,
                "do_sample": False
            }
        }

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.api_url, json=payload, headers=headers,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        if response.status == 503:
                            logger.warning("HuggingFace model loading, waiting...")
                            await asyncio.sleep(20)
                            continue

                        if response.status != 200:
                            error_text = await response.text()
                            raise Exception(f"HuggingFace API {response.status}: {error_text[:200]}")

                        data = await response.json()
                        if isinstance(data, list) and data:
                            return (data[0].get("summary_text") or data[0].get("generated_text", "")).strip()
                        raise Exception(f"Unexpected HuggingFace response: {str(data)[:200]}")

            except aiohttp.ClientError as e:
                logger.warning(f"Network error (attempt {attempt + 1}/3): {e}")
                await asyncio.sleep(2 ** attempt)

        raise Exception("HuggingFace API failed after retries")
