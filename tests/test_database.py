"""Unit tests for database operations."""
import pytest
import os
from arxivscribe.storage.db import DatabaseManager


@pytest.fixture
def db():
    """Create test database."""
    db_path = "test_arxivscribe.db"
    db = DatabaseManager(db_path)
    yield db
    db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_add_subscription(db):
    """Test adding subscriptions."""
    result = db.add_subscription(123, 456, "attention")
    assert result is True
    
    # Try adding duplicate
    result = db.add_subscription(123, 456, "attention")
    assert result is False


def test_get_subscriptions(db):
    """Test retrieving subscriptions."""
    db.add_subscription(123, 456, "attention")
    db.add_subscription(123, 456, "transformer")
    
    keywords = db.get_channel_subscriptions(123, 456)
    
    assert len(keywords) == 2
    assert "attention" in keywords
    assert "transformer" in keywords


def test_remove_subscription(db):
    """Test removing subscriptions."""
    db.add_subscription(123, 456, "attention")
    
    result = db.remove_subscription(123, 456, "attention")
    assert result is True
    
    keywords = db.get_channel_subscriptions(123, 456)
    assert len(keywords) == 0


def test_store_and_check_paper(db):
    """Test storing and checking papers."""
    paper = {
        'id': '2301.00001',
        'title': 'Test Paper',
        'abstract': 'Test abstract',
        'authors': ['John Doe'],
        'published': '2023-01-01',
        'categories': ['cs.LG'],
        'url': 'http://arxiv.org/abs/2301.00001',
        'pdf_url': 'http://arxiv.org/pdf/2301.00001',
        'summary': 'Test summary'
    }
    
    db.store_paper(paper, 123, 456, 789)
    
    is_posted = db.is_paper_posted('2301.00001', 123, 456)
    assert is_posted is True
    
    is_posted_other = db.is_paper_posted('2301.00001', 123, 999)
    assert is_posted_other is False


def test_votes(db):
    """Test voting operations."""
    # Store a paper first
    paper = {
        'id': '2301.00001',
        'title': 'Test Paper',
        'authors': [],
        'url': 'http://test.com'
    }
    db.store_paper(paper, 123, 456, 789)
    
    # Add votes
    db.add_vote('2301.00001', 111, 123, 456, 'upvote')
    db.add_vote('2301.00001', 222, 123, 456, 'upvote')
    db.add_vote('2301.00001', 333, 123, 456, 'downvote')
    
    summary = db.get_vote_summary('2301.00001')
    
    assert summary['upvotes'] == 2
    assert summary['downvotes'] == 1
    assert summary['maybe'] == 0
