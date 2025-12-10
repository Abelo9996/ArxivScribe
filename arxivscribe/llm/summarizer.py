"""LLM-based paper summarizer."""
import logging
from typing import Optional
from arxivscribe.llm.prompts import SUMMARY_PROMPT
from arxivscribe.llm.providers.openai_provider import OpenAIProvider
from arxivscribe.llm.providers.huggingface_provider import HuggingFaceProvider

logger = logging.getLogger(__name__)


class Summarizer:
    """Generates TLDR summaries of papers using LLMs."""

    def __init__(
        self,
        provider: str = "openai",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize summarizer.
        
        Args:
            provider: LLM provider ('openai' or 'huggingface')
            api_key: API key for the provider
            model: Model name (provider-specific)
            **kwargs: Additional provider-specific arguments
        """
        self.provider_name = provider.lower()
        
        if self.provider_name == "openai":
            self.provider = OpenAIProvider(
                api_key=api_key,
                model=model or "gpt-3.5-turbo",
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
        
        logger.info(f"Initialized summarizer with provider: {provider}")

    async def summarize(self, paper: dict) -> str:
        """
        Generate a TLDR summary for a paper.
        
        Args:
            paper: Paper dictionary with 'title' and 'abstract'
            
        Returns:
            TLDR summary string
        """
        title = paper.get('title', '')
        abstract = paper.get('abstract', '')
        
        if not title or not abstract:
            logger.warning(f"Missing title or abstract for paper {paper.get('id', 'unknown')}")
            return "Summary unavailable due to missing information."
        
        try:
            # Build prompt
            prompt = SUMMARY_PROMPT.format(title=title, abstract=abstract)
            
            # Get summary from provider
            summary = await self.provider.generate(prompt)
            
            # Validate and clean summary
            summary = self._clean_summary(summary)
            
            logger.debug(f"Generated summary for paper {paper.get('id', 'unknown')}")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary for {paper.get('id', 'unknown')}: {e}")
            return "Summary generation failed."

    def _clean_summary(self, summary: str) -> str:
        """
        Clean and validate the generated summary.
        
        Args:
            summary: Raw summary from LLM
            
        Returns:
            Cleaned summary
        """
        # Remove extra whitespace
        summary = " ".join(summary.split())
        
        # Ensure it's not too long (Discord embed description limit is 4096)
        if len(summary) > 500:
            summary = summary[:497] + "..."
        
        # Ensure it's not empty
        if not summary or summary.isspace():
            return "No summary available."
        
        return summary

    async def batch_summarize(self, papers: list) -> list:
        """
        Generate summaries for multiple papers.
        
        Args:
            papers: List of paper dictionaries
            
        Returns:
            List of paper dictionaries with 'summary' field added
        """
        summarized_papers = []
        
        for paper in papers:
            try:
                summary = await self.summarize(paper)
                paper['summary'] = summary
                summarized_papers.append(paper)
            except Exception as e:
                logger.error(f"Error in batch summarize for {paper.get('id')}: {e}")
                paper['summary'] = "Summary generation failed."
                summarized_papers.append(paper)
        
        return summarized_papers

    def set_provider(self, provider: str, api_key: Optional[str] = None, **kwargs):
        """
        Switch to a different LLM provider.
        
        Args:
            provider: Provider name
            api_key: API key
            **kwargs: Additional arguments
        """
        self.__init__(provider=provider, api_key=api_key, **kwargs)
