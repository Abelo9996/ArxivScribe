"""Ollama local LLM provider — free, no API key needed."""
import logging
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)


class OllamaProvider:
    """Local Ollama provider for generating summaries — zero cost."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.3,
        **kwargs
    ):
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.temperature = temperature

    async def generate(self, prompt: str) -> str:
        """Generate text using local Ollama."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": 200
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status != 200:
                        error = await response.text()
                        raise Exception(f"Ollama API {response.status}: {error[:200]}")

                    data = await response.json()
                    return data.get("response", "").strip()

        except aiohttp.ClientConnectionError:
            raise Exception(
                "Cannot connect to Ollama. Is it running? "
                "Install: https://ollama.com | Start: 'ollama serve' | Pull model: 'ollama pull llama3.2'"
            )
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise

    @staticmethod
    async def check_available(base_url: str = "http://localhost:11434") -> bool:
        """Check if Ollama is running."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as r:
                    return r.status == 200
        except Exception:
            return False

    @staticmethod
    async def list_models(base_url: str = "http://localhost:11434") -> list:
        """List available Ollama models."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status == 200:
                        data = await r.json()
                        return [m['name'] for m in data.get('models', [])]
        except Exception:
            pass
        return []
