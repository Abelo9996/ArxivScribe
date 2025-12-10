"""HuggingFace API provider for LLM summarization."""
import os
import logging
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)


class HuggingFaceProvider:
    """HuggingFace Inference API provider for generating summaries."""

    API_URL_TEMPLATE = "https://api-inference.huggingface.co/models/{model}"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "facebook/bart-large-cnn",
        max_length: int = 150,
        min_length: int = 30
    ):
        """
        Initialize HuggingFace provider.
        
        Args:
            api_key: HuggingFace API key
            model: Model name on HuggingFace Hub
            max_length: Maximum length of summary
            min_length: Minimum length of summary
        """
        self.api_key = api_key or os.getenv("HUGGINGFACE_API_KEY")
        if not self.api_key:
            raise ValueError("HuggingFace API key not provided")
        
        self.model = model
        self.api_url = self.API_URL_TEMPLATE.format(model=model)
        self.max_length = max_length
        self.min_length = min_length

    async def generate(self, prompt: str) -> str:
        """
        Generate text using HuggingFace Inference API.
        
        Args:
            prompt: Input prompt (for summarization models, this is the text to summarize)
            
        Returns:
            Generated text
        """
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
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status == 503:
                        # Model is loading, wait and retry
                        logger.warning("HuggingFace model is loading, retrying...")
                        await asyncio.sleep(20)
                        return await self.generate(prompt)
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"HuggingFace API error: {response.status} - {error_text}")
                        raise Exception(f"HuggingFace API returned status {response.status}")
                    
                    data = await response.json()
                    
                    # Extract generated text
                    if isinstance(data, list) and len(data) > 0:
                        if "summary_text" in data[0]:
                            return data[0]["summary_text"].strip()
                        elif "generated_text" in data[0]:
                            return data[0]["generated_text"].strip()
                    
                    logger.error(f"Unexpected HuggingFace API response: {data}")
                    raise Exception("Invalid response from HuggingFace API")
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error calling HuggingFace API: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating with HuggingFace: {e}")
            raise


# Import asyncio for sleep
import asyncio
