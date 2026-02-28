"""arXiv API fetcher with rate limiting and retry logic."""
import aiohttp
import asyncio
import logging
from typing import List, Optional
from datetime import datetime, timedelta

from arxivscribe.arxiv.parser import ArxivParser

logger = logging.getLogger(__name__)


class ArxivFetcher:
    """Fetches papers from arXiv API with rate limiting."""

    BASE_URL = "http://export.arxiv.org/api/query"

    def __init__(self, max_results_per_category: int = 50, rate_limit_seconds: float = 3.0):
        self.max_results_per_category = max_results_per_category
        self.rate_limit_seconds = rate_limit_seconds
        self.parser = ArxivParser()
        self._last_request_time: Optional[float] = None

    async def _rate_limit(self):
        """Respect arXiv's rate limit (they ask for 3s between requests)."""
        if self._last_request_time is not None:
            elapsed = asyncio.get_event_loop().time() - self._last_request_time
            if elapsed < self.rate_limit_seconds:
                await asyncio.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _request_with_retry(self, session: aiohttp.ClientSession, url: str, params: dict, retries: int = 3) -> Optional[str]:
        """Make HTTP request with exponential backoff retry."""
        for attempt in range(retries):
            await self._rate_limit()
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 503:
                        wait = 2 ** (attempt + 2)
                        logger.warning(f"arXiv 503, retrying in {wait}s (attempt {attempt + 1}/{retries})")
                        await asyncio.sleep(wait)
                    else:
                        logger.error(f"arXiv API returned status {response.status}")
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"arXiv request timed out (attempt {attempt + 1}/{retries})")
                await asyncio.sleep(2 ** attempt)
            except aiohttp.ClientError as e:
                logger.error(f"Network error fetching from arXiv: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
        return None

    async def fetch_papers(
        self,
        categories: List[str],
        since: Optional[datetime] = None,
        max_results: Optional[int] = None
    ) -> List[dict]:
        """
        Fetch papers from arXiv for given categories.

        Note: arXiv's submittedDate query is unreliable, so we fetch recent papers
        and filter by date post-fetch.
        """
        if since is None:
            since = datetime.utcnow() - timedelta(days=1)

        max_per_cat = max_results or self.max_results_per_category
        all_papers = []
        seen_ids = set()

        async with aiohttp.ClientSession() as session:
            for category in categories:
                try:
                    papers = await self._fetch_category(session, category, max_per_cat)
                    for paper in papers:
                        if paper['id'] not in seen_ids:
                            # Filter by date if published info available
                            if paper.get('published'):
                                try:
                                    pub_dt = datetime.fromisoformat(
                                        paper['published'].replace("Z", "+00:00")
                                    ).replace(tzinfo=None)
                                    if pub_dt < since:
                                        continue
                                except (ValueError, TypeError):
                                    pass  # If we can't parse, include it
                            all_papers.append(paper)
                            seen_ids.add(paper['id'])
                    logger.info(f"Fetched {len(papers)} papers from {category}")
                except Exception as e:
                    logger.error(f"Error fetching category {category}: {e}")

        logger.info(f"Total unique papers fetched: {len(all_papers)}")
        return all_papers

    async def _fetch_category(
        self,
        session: aiohttp.ClientSession,
        category: str,
        max_results: int
    ) -> List[dict]:
        """Fetch papers from a specific category using simple category search."""
        # Use simple category query — submittedDate range is unreliable in arXiv API
        params = {
            "search_query": f"cat:{category}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }

        xml_content = await self._request_with_retry(session, self.BASE_URL, params)
        if xml_content:
            return self.parser.parse_response(xml_content)
        return []

    async def fetch_paper_by_id(self, arxiv_id: str) -> Optional[dict]:
        """Fetch a specific paper by arXiv ID."""
        params = {"id_list": arxiv_id, "max_results": 1}
        try:
            async with aiohttp.ClientSession() as session:
                xml_content = await self._request_with_retry(session, self.BASE_URL, params)
                if xml_content:
                    papers = self.parser.parse_response(xml_content)
                    return papers[0] if papers else None
        except Exception as e:
            logger.error(f"Error fetching paper {arxiv_id}: {e}")
        return None

    async def search_papers(self, query: str, max_results: int = 10) -> List[dict]:
        """Search arXiv with a free-text query."""
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        try:
            async with aiohttp.ClientSession() as session:
                xml_content = await self._request_with_retry(session, self.BASE_URL, params)
                if xml_content:
                    return self.parser.parse_response(xml_content)
        except Exception as e:
            logger.error(f"Error searching arXiv for '{query}': {e}")
        return []
