"""Unit tests for database operations."""
import pytest
import os
from arxivscribe.storage.db import DatabaseManager


@pytest.fixture
async def db():
    """Create test database."""
    db_path = "test_arxivscribe.db"
    db = DatabaseManager(db_path)
    await db.initialize()
    yield db
    await db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_add_subscription(db):
    result = await db.add_subscription(123, 456, "attention")
    assert result is True
    # Duplicate
    result = await db.add_subscription(123, 456, "attention")
    assert result is False


@pytest.mark.asyncio
async def test_get_subscriptions(db):
    await db.add_subscription(123, 456, "attention")
    await db.add_subscription(123, 456, "transformer")
    keywords = await db.get_channel_subscriptions(123, 456)
    assert len(keywords) == 2
    assert "attention" in keywords
    assert "transformer" in keywords


@pytest.mark.asyncio
async def test_remove_subscription(db):
    await db.add_subscription(123, 456, "attention")
    result = await db.remove_subscription(123, 456, "attention")
    assert result is True
    keywords = await db.get_channel_subscriptions(123, 456)
    assert len(keywords) == 0


@pytest.mark.asyncio
async def test_store_and_check_paper(db):
    paper = {
        'id': '2301.00001', 'title': 'Test Paper',
        'abstract': 'Test abstract', 'authors': ['John Doe'],
        'published': '2023-01-01', 'categories': ['cs.LG'],
        'url': 'http://arxiv.org/abs/2301.00001',
        'pdf_url': 'http://arxiv.org/pdf/2301.00001',
        'summary': 'Test summary'
    }
    await db.store_paper(paper, 123, 456, 789)
    assert await db.is_paper_posted('2301.00001', 123, 456) is True
    assert await db.is_paper_posted('2301.00001', 123, 999) is False


@pytest.mark.asyncio
async def test_votes(db):
    paper = {
        'id': '2301.00001', 'title': 'Test Paper',
        'authors': [], 'url': 'http://test.com'
    }
    await db.store_paper(paper, 123, 456, 789)
    await db.add_vote('2301.00001', 111, 123, 456, 'upvote')
    await db.add_vote('2301.00001', 222, 123, 456, 'upvote')
    await db.add_vote('2301.00001', 333, 123, 456, 'downvote')

    summary = await db.get_vote_summary('2301.00001')
    assert summary['upvotes'] == 2
    assert summary['downvotes'] == 1
    assert summary['maybe'] == 0


@pytest.mark.asyncio
async def test_stats(db):
    await db.add_subscription(123, 456, "attention")
    paper = {
        'id': '2301.00001', 'title': 'Test',
        'authors': [], 'url': 'http://test.com'
    }
    await db.store_paper(paper, 123, 456, 789)
    stats = await db.get_stats(123, 456)
    assert stats['subscriptions'] == 1
    assert stats['papers_posted'] == 1
