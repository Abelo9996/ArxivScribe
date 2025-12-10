"""Unit tests for keyword filtering."""
import pytest
from arxivscribe.bot.filters import KeywordFilter


@pytest.fixture
def sample_paper():
    """Sample paper dictionary."""
    return {
        'id': '2301.00001',
        'title': 'Attention Mechanisms in Neural Networks',
        'abstract': 'This paper explores attention mechanisms in deep learning models.',
        'summary': 'A comprehensive study of attention in transformers.',
        'categories': ['cs.LG', 'cs.AI']
    }


def test_exact_keyword_match(sample_paper):
    """Test exact keyword matching."""
    matched = KeywordFilter.paper_matches_keywords(
        sample_paper,
        ['attention'],
        fuzzy=False
    )
    
    assert 'attention' in matched


def test_fuzzy_keyword_match(sample_paper):
    """Test fuzzy keyword matching."""
    matched = KeywordFilter.paper_matches_keywords(
        sample_paper,
        ['attention'],
        fuzzy=True
    )
    
    assert 'attention' in matched


def test_case_insensitive_match(sample_paper):
    """Test case-insensitive matching."""
    matched = KeywordFilter.paper_matches_keywords(
        sample_paper,
        ['ATTENTION', 'Attention'],
        fuzzy=False
    )
    
    assert len(matched) == 2


def test_no_match(sample_paper):
    """Test when keywords don't match."""
    matched = KeywordFilter.paper_matches_keywords(
        sample_paper,
        ['quantum', 'robotics'],
        fuzzy=False
    )
    
    assert len(matched) == 0


def test_filter_papers_by_keywords():
    """Test filtering multiple papers."""
    papers = [
        {'title': 'Attention in Transformers', 'abstract': 'Study of attention'},
        {'title': 'Quantum Computing', 'abstract': 'Quantum algorithms'},
        {'title': 'Graph Neural Networks', 'abstract': 'GNN architectures'}
    ]
    
    filtered = KeywordFilter.filter_papers_by_keywords(
        papers,
        ['attention', 'graph'],
        fuzzy=False
    )
    
    assert len(filtered) == 2
    assert filtered[0][0]['title'] == 'Attention in Transformers'
    assert filtered[1][0]['title'] == 'Graph Neural Networks'
