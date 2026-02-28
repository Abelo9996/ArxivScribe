"""
AI Configuration Manager for ArxivScribe
Handles runtime LLM configuration.
Supports: OpenAI, Anthropic, Groq, Ollama, HuggingFace.
Stores config in a JSON file, keys are masked in responses.
"""

import os
import json
from typing import Optional, Dict, List

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "ai_config.json")

AVAILABLE_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4", "gpt-3.5-turbo"],
        "default_model": "gpt-3.5-turbo",
        "env_key": "OPENAI_API_KEY",
    },
    "anthropic": {
        "name": "Anthropic",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
        "default_model": "claude-sonnet-4-20250514",
        "env_key": "ANTHROPIC_API_KEY",
    },
    "groq": {
        "name": "Groq",
        "models": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "default_model": "llama-3.1-70b-versatile",
        "env_key": "GROQ_API_KEY",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "models": ["llama3.1", "llama3.2", "mistral", "phi3"],
        "default_model": "llama3.1",
        "env_key": "",
    },
    "huggingface": {
        "name": "HuggingFace",
        "models": ["facebook/bart-large-cnn"],
        "default_model": "facebook/bart-large-cnn",
        "env_key": "HUGGINGFACE_API_KEY",
    },
}


class AIConfigManager:
    """Manages AI configuration at runtime."""

    def __init__(self):
        self._config = self._load()

    def _load(self) -> dict:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        return {
            "provider": os.getenv("LLM_PROVIDER", "openai"),
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "model": os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
            "base_url": None,
        }

    def _save(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._config, f, indent=2)

    def get_api_key(self) -> str:
        return self._config.get("api_key", "")

    def get_model(self) -> str:
        return self._config.get("model", "gpt-3.5-turbo")

    def get_provider(self) -> str:
        return self._config.get("provider", "openai")

    def get_base_url(self) -> Optional[str]:
        return self._config.get("base_url")

    def is_configured(self) -> bool:
        provider = self.get_provider()
        if provider == "ollama":
            return True
        return bool(self.get_api_key())

    def _mask_key(self, key: str) -> str:
        if not key:
            return "(not set)"
        if len(key) <= 8:
            return "****"
        return key[:4] + "•" * min(len(key) - 8, 20) + key[-4:]

    def get_status_text(self) -> str:
        """Get a Discord-friendly status string."""
        provider = self.get_provider()
        model = self.get_model()
        key = self.get_api_key()
        providers_list = ", ".join(AVAILABLE_PROVIDERS.keys())
        return (
            f"**Provider:** {provider}\n"
            f"**Model:** {model}\n"
            f"**API Key:** `{self._mask_key(key)}`\n"
            f"**Status:** {'✅ Configured' if self.is_configured() else '⚠️ Not configured'}\n"
            f"**Available providers:** {providers_list}"
        )

    def update(self, provider: Optional[str] = None, api_key: Optional[str] = None,
               model: Optional[str] = None, base_url: Optional[str] = None) -> str:
        if provider is not None:
            if provider not in AVAILABLE_PROVIDERS:
                return f"❌ Unknown provider `{provider}`. Available: {', '.join(AVAILABLE_PROVIDERS.keys())}"
            self._config["provider"] = provider
            if model is None:
                self._config["model"] = AVAILABLE_PROVIDERS[provider]["default_model"]
        if api_key is not None:
            self._config["api_key"] = api_key
        if model is not None:
            self._config["model"] = model
        if base_url is not None:
            self._config["base_url"] = base_url
        self._save()
        # Update env for current process
        env_key = AVAILABLE_PROVIDERS.get(self.get_provider(), {}).get("env_key", "")
        if env_key:
            os.environ[env_key] = self._config.get("api_key", "")
        return "✅ Configuration updated!"

    async def test_connection(self) -> str:
        """Test the current API key."""
        key = self.get_api_key()
        provider = self.get_provider()
        model = self.get_model()
        base_url = self.get_base_url()

        if provider == "ollama":
            try:
                import httpx
                url = base_url or "http://localhost:11434"
                async with httpx.AsyncClient() as client:
                    r = await client.post(
                        f"{url}/api/chat",
                        json={"model": model, "messages": [{"role": "user", "content": "Say ok"}], "stream": False},
                        timeout=15,
                    )
                    if r.status_code == 200:
                        content = r.json().get("message", {}).get("content", "")
                        return f"✅ Ollama connected! Response: `{content.strip()}`"
                    return f"❌ Ollama returned {r.status_code}"
            except Exception as e:
                return f"❌ Ollama connection failed: {e}"

        if not key:
            return "❌ No API key configured. Use `/config set_key <key>` first."

        try:
            if provider == "openai":
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=key)
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Say 'ok'"}],
                    max_tokens=5,
                )
                return f"✅ OpenAI connected! Response: `{resp.choices[0].message.content.strip()}`"

            elif provider == "anthropic":
                import httpx
                async with httpx.AsyncClient() as client:
                    r = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                        json={"model": model, "max_tokens": 10, "messages": [{"role": "user", "content": "Say ok"}]},
                        timeout=15,
                    )
                    if r.status_code == 200:
                        return f"✅ Anthropic connected! Response: `{r.json()['content'][0]['text'].strip()}`"
                    return f"❌ Anthropic returned {r.status_code}: {r.text[:200]}"

            elif provider == "groq":
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Say 'ok'"}],
                    max_tokens=5,
                )
                return f"✅ Groq connected! Response: `{resp.choices[0].message.content.strip()}`"

            elif provider == "huggingface":
                import httpx
                async with httpx.AsyncClient() as client:
                    r = await client.post(
                        f"https://api-inference.huggingface.co/models/{model}",
                        headers={"Authorization": f"Bearer {key}"},
                        json={"inputs": "Test connection"},
                        timeout=15,
                    )
                    if r.status_code == 200:
                        return "✅ HuggingFace connected!"
                    return f"❌ HuggingFace returned {r.status_code}: {r.text[:200]}"

            else:
                return f"❌ Unsupported provider: {provider}"
        except Exception as e:
            return f"❌ Connection failed: {str(e)}"

    def get_chat_client(self):
        """Returns an async chat function that works across all providers."""
        provider = self.get_provider()
        key = self.get_api_key()
        model = self.get_model()
        base_url = self.get_base_url()

        if provider == "openai":
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=key) if key else None

            async def chat(system_prompt: str, user_prompt: str) -> str:
                if not client:
                    return ""
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    max_tokens=1024, temperature=0.7,
                )
                return resp.choices[0].message.content.strip()
            return chat

        elif provider == "anthropic":
            import httpx

            async def chat(system_prompt: str, user_prompt: str) -> str:
                if not key:
                    return ""
                async with httpx.AsyncClient() as client:
                    r = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                        json={"model": model, "max_tokens": 1024, "system": system_prompt,
                              "messages": [{"role": "user", "content": user_prompt}]},
                        timeout=60,
                    )
                    if r.status_code == 200:
                        return r.json()["content"][0]["text"].strip()
                    raise Exception(f"Anthropic error {r.status_code}")
            return chat

        elif provider == "groq":
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=key, base_url="https://api.groq.com/openai/v1") if key else None

            async def chat(system_prompt: str, user_prompt: str) -> str:
                if not client:
                    return ""
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    max_tokens=1024, temperature=0.7,
                )
                return resp.choices[0].message.content.strip()
            return chat

        elif provider == "ollama":
            import httpx
            url = base_url or "http://localhost:11434"

            async def chat(system_prompt: str, user_prompt: str) -> str:
                async with httpx.AsyncClient() as client:
                    r = await client.post(
                        f"{url}/api/chat",
                        json={"model": model, "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ], "stream": False},
                        timeout=120,
                    )
                    if r.status_code == 200:
                        return r.json().get("message", {}).get("content", "").strip()
                    raise Exception(f"Ollama error {r.status_code}")
            return chat

        else:
            async def chat(system_prompt: str, user_prompt: str) -> str:
                return ""
            return chat


ai_config = AIConfigManager()
