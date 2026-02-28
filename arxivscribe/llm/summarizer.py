"""LLM-based paper summarizer with concurrent processing."""
import asyncio
import logging
from typing import Optional, List

from arxivscribe.llm.prompts import SUMMARY_PROMPT, KEYWORD_EXTRACTION_PROMPT
from arxivscribe.llm.providers.openai_provider import OpenAIProvider
from arxivscribe.llm.providers.huggingface_provider import HuggingFaceProvider

logger = logging.getLogger(__name__)


class Summarizer:
    """Generates TLDR summaries with concurrency control."""

    def __init__(
        self,
        provider: str = "openai",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_concurrent: int = 5,
        **kwargs
    ):
        self.provider_name = provider.lower()
        self._semaphore = asyncio.Semaphore(max_concurrent)

        if self.provider_name == "openai":
            self.provider = OpenAIProvider(
                api_key=api_key,
                model=model or "gpt-4o-mini",
                **kwargs
            )
        elif self.provider_name == "huggingface":
            self.provider = HuggingFaceProvider(
                api_key=api_key,
                model=model or "facebook/bart-large-cnn",
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        logger.info(f"Initialized summarizer: provider={provider}, model={self.provider.model}")

    async def summarize(self, paper: dict) -> str:
        """Generate a TLDR summary for a paper."""
        title = paper.get('title', '')
        abstract = paper.get('abstract', '')

        if not title or not abstract:
            return "Summary unavailable — missing title or abstract."

        try:
            async with self._semaphore:
                prompt = SUMMARY_PROMPT.format(title=title, abstract=abstract)
                summary = await self.provider.generate(prompt)
                return self._clean_summary(summary)
        except Exception as e:
            logger.error(f"Summary failed for {paper.get('id', '?')}: {e}")
            return "Summary generation failed."

    async def extract_keywords(self, paper: dict) -> List[str]:
        """Extract keywords from a paper using LLM."""
        title = paper.get('title', '')
        abstract = paper.get('abstract', '')
        if not abstract:
            return []
        try:
            async with self._semaphore:
                prompt = KEYWORD_EXTRACTION_PROMPT.format(title=title, abstract=abstract)
                result = await self.provider.generate(prompt)
                return [k.strip().lower() for k in result.split(",") if k.strip()]
        except Exception as e:
            logger.error(f"Keyword extraction failed for {paper.get('id', '?')}: {e}")
            return []

    def _clean_summary(self, summary: str) -> str:
        summary = " ".join(summary.split())
        # Remove common LLM prefixes
        for prefix in ["TLDR:", "TL;DR:", "Summary:"]:
            if summary.upper().startswith(prefix.upper()):
                summary = summary[len(prefix):].strip()
        if len(summary) > 500:
            summary = summary[:497] + "..."
        return summary or "No summary available."

    async def batch_summarize(self, papers: list) -> list:
        """Summarize multiple papers concurrently."""
        tasks = [self._summarize_one(p) for p in papers]
        return await asyncio.gather(*tasks)

    async def _summarize_one(self, paper: dict) -> dict:
        paper['summary'] = await self.summarize(paper)
        return paper
