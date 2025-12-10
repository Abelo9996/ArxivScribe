"""Keyword filtering and matching for papers."""
import re
from typing import List, Set
import logging

logger = logging.getLogger(__name__)


class KeywordFilter:
    """Handles keyword matching and filtering for papers."""

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text for matching.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized lowercase text
        """
        return text.lower().strip()

    @staticmethod
    def matches_keyword(text: str, keyword: str, fuzzy: bool = False) -> bool:
        """
        Check if text matches a keyword.
        
        Args:
            text: Text to search in
            keyword: Keyword to search for
            fuzzy: If True, use fuzzy matching (word boundaries)
            
        Returns:
            True if keyword matches
        """
        text = KeywordFilter.normalize_text(text)
        keyword = KeywordFilter.normalize_text(keyword)
        
        if not fuzzy:
            # Exact substring match
            return keyword in text
        else:
            # Word boundary matching (fuzzy)
            pattern = r'\b' + re.escape(keyword) + r'\b'
            return bool(re.search(pattern, text, re.IGNORECASE))

    @staticmethod
    def paper_matches_keywords(
        paper: dict,
        keywords: List[str],
        fuzzy: bool = True
    ) -> Set[str]:
        """
        Check if a paper matches any of the given keywords.
        
        Args:
            paper: Paper dictionary with 'title', 'abstract', 'summary' fields
            keywords: List of keywords to match against
            fuzzy: Use fuzzy matching
            
        Returns:
            Set of matched keywords (empty if no matches)
        """
        matched_keywords = set()
        
        # Combine searchable text
        searchable_text = " ".join([
            paper.get('title', ''),
            paper.get('abstract', ''),
            paper.get('summary', ''),
            " ".join(paper.get('categories', []))
        ])
        
        for keyword in keywords:
            if KeywordFilter.matches_keyword(searchable_text, keyword, fuzzy=fuzzy):
                matched_keywords.add(keyword)
        
        return matched_keywords

    @staticmethod
    def filter_papers_by_keywords(
        papers: List[dict],
        keywords: List[str],
        fuzzy: bool = True
    ) -> List[tuple]:
        """
        Filter papers that match any of the keywords.
        
        Args:
            papers: List of paper dictionaries
            keywords: List of keywords to filter by
            fuzzy: Use fuzzy matching
            
        Returns:
            List of tuples (paper, matched_keywords)
        """
        filtered = []
        
        for paper in papers:
            matched = KeywordFilter.paper_matches_keywords(paper, keywords, fuzzy=fuzzy)
            if matched:
                filtered.append((paper, matched))
                logger.debug(
                    f"Paper '{paper.get('title', 'Unknown')}' matched keywords: {matched}"
                )
        
        return filtered

    @staticmethod
    def extract_keywords_from_text(text: str, min_length: int = 3) -> List[str]:
        """
        Extract potential keywords from text (simple implementation).
        
        Args:
            text: Text to extract keywords from
            min_length: Minimum keyword length
            
        Returns:
            List of extracted keywords
        """
        # Remove special characters and split
        words = re.findall(r'\b[a-z]+\b', text.lower())
        
        # Filter by length
        keywords = [w for w in words if len(w) >= min_length]
        
        # Remove common stop words
        stop_words = {
            'the', 'and', 'for', 'that', 'this', 'with', 'from', 'are',
            'was', 'were', 'been', 'have', 'has', 'had', 'will', 'would',
            'can', 'could', 'should', 'may', 'might', 'must', 'does', 'did'
        }
        
        keywords = [k for k in keywords if k not in stop_words]
        
        return list(set(keywords))
