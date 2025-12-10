"""arXiv API fetcher for retrieving papers."""
import aiohttp
import logging
from typing import List, Optional
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

from arxivscribe.arxiv.parser import ArxivParser

logger = logging.getLogger(__name__)


class ArxivFetcher:
    """Fetches papers from arXiv API."""

    BASE_URL = "http://export.arxiv.org/api/query"
    MAX_RESULTS = 100  # Per request

    def __init__(self, max_results_per_category: int = 50):
        """
        Initialize arXiv fetcher.
        
        Args:
            max_results_per_category: Maximum papers to fetch per category
        """
        self.max_results_per_category = max_results_per_category
        self.parser = ArxivParser()

    async def fetch_papers(
        self,
        categories: List[str],
        since: Optional[datetime] = None,
        max_results: Optional[int] = None
    ) -> List[dict]:
        """
        Fetch papers from arXiv.
        
        Args:
            categories: List of arXiv categories (e.g., ['cs.LG', 'cs.AI'])
            since: Only fetch papers published after this datetime
            max_results: Maximum total results (overrides per-category limit)
            
        Returns:
            List of paper dictionaries
        """
        if since is None:
            # Default to last 24 hours
            since = datetime.now() - timedelta(days=1)
        
        max_per_cat = max_results or self.max_results_per_category
        
        all_papers = []
        seen_ids = set()
        
        for category in categories:
            try:
                papers = await self._fetch_category(category, since, max_per_cat)
                
                # Deduplicate across categories
                for paper in papers:
                    if paper['id'] not in seen_ids:
                        all_papers.append(paper)
                        seen_ids.add(paper['id'])
                
                logger.info(f"Fetched {len(papers)} papers from {category}")
            except Exception as e:
                logger.error(f"Error fetching category {category}: {e}")
        
        logger.info(f"Total unique papers fetched: {len(all_papers)}")
        return all_papers

    async def _fetch_category(
        self,
        category: str,
        since: datetime,
        max_results: int
    ) -> List[dict]:
        """
        Fetch papers from a specific category.
        
        Args:
            category: arXiv category
            since: Only papers after this date
            max_results: Maximum results
            
        Returns:
            List of paper dictionaries
        """
        # Build query
        # Format: cat:cs.LG AND submittedDate:[YYYYMMDD000000 TO YYYYMMDD235959]
        since_str = since.strftime("%Y%m%d%H%M%S")
        now_str = datetime.now().strftime("%Y%m%d%H%M%S")
        
        query = f"cat:{category} AND submittedDate:[{since_str} TO {now_str}]"
        
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.BASE_URL, params=params) as response:
                if response.status != 200:
                    logger.error(f"arXiv API returned status {response.status}")
                    return []
                
                xml_content = await response.text()
                return self.parser.parse_response(xml_content)

    async def fetch_paper_by_id(self, arxiv_id: str) -> Optional[dict]:
        """
        Fetch a specific paper by arXiv ID.
        
        Args:
            arxiv_id: arXiv paper ID
            
        Returns:
            Paper dictionary or None
        """
        params = {
            "id_list": arxiv_id,
            "max_results": 1
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL, params=params) as response:
                    if response.status != 200:
                        logger.error(f"arXiv API returned status {response.status}")
                        return None
                    
                    xml_content = await response.text()
                    papers = self.parser.parse_response(xml_content)
                    
                    return papers[0] if papers else None
        except Exception as e:
            logger.error(f"Error fetching paper {arxiv_id}: {e}")
            return None
