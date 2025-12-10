"""Unit tests for arXiv fetcher."""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from arxivscribe.arxiv.fetcher import ArxivFetcher
from arxivscribe.arxiv.parser import ArxivParser


@pytest.fixture
def fetcher():
    """Create ArxivFetcher instance."""
    return ArxivFetcher(max_results_per_category=10)


@pytest.fixture
def sample_xml():
    """Sample arXiv API XML response."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <id>http://arxiv.org/abs/2301.00001v1</id>
            <title>Test Paper Title</title>
            <summary>This is a test abstract.</summary>
            <author><name>John Doe</name></author>
            <author><name>Jane Smith</name></author>
            <published>2023-01-01T00:00:00Z</published>
            <updated>2023-01-01T00:00:00Z</updated>
            <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
            <link href="http://arxiv.org/abs/2301.00001v1" rel="alternate" type="text/html"/>
            <link title="pdf" href="http://arxiv.org/pdf/2301.00001v1" rel="related" type="application/pdf"/>
        </entry>
    </feed>"""


@pytest.mark.asyncio
async def test_fetch_papers(fetcher, sample_xml):
    """Test fetching papers from arXiv."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=sample_xml)
        mock_get.return_value.__aenter__.return_value = mock_response
        
        papers = await fetcher.fetch_papers(['cs.LG'])
        
        assert len(papers) == 1
        assert papers[0]['id'] == '2301.00001v1'
        assert papers[0]['title'] == 'Test Paper Title'


def test_parser(sample_xml):
    """Test XML parser."""
    parser = ArxivParser()
    papers = parser.parse_response(sample_xml)
    
    assert len(papers) == 1
    paper = papers[0]
    
    assert paper['id'] == '2301.00001v1'
    assert paper['title'] == 'Test Paper Title'
    assert paper['abstract'] == 'This is a test abstract.'
    assert len(paper['authors']) == 2
    assert 'John Doe' in paper['authors']
    assert 'cs.LG' in paper['categories']
