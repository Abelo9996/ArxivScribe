"""Web routes for ArxivScribe."""
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List
from pathlib import Path
import logging

from arxivscribe.storage.db import DatabaseManager
from arxivscribe.arxiv.fetcher import ArxivFetcher
from arxivscribe.llm.summarizer import Summarizer
from arxivscribe.bot.filters import KeywordFilter

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Dependencies injected at startup
_db: Optional[DatabaseManager] = None
_fetcher: Optional[ArxivFetcher] = None
_summarizer: Optional[Summarizer] = None
_categories: List[str] = []
_config: dict = {}


def set_app_deps(db, fetcher, summarizer, categories, config):
    global _db, _fetcher, _summarizer, _categories, _config
    _db, _fetcher, _summarizer, _categories, _config = db, fetcher, summarizer, categories, config


# --- Pages ---

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main dashboard."""
    papers = await _db.get_recent_papers(limit=50)
    subs = await _db.get_all_subscriptions()
    stats = await _db.get_global_stats()
    return templates.TemplateResponse("index.html", {
        "request": request, "papers": papers, "subscriptions": subs,
        "stats": stats, "categories": _categories,
        "has_summarizer": _summarizer is not None
    })


# --- API ---

@router.post("/api/subscribe")
async def subscribe(keyword: str = Query(..., min_length=1)):
    """Add a keyword subscription."""
    keyword = keyword.strip().lower()
    added = await _db.add_subscription(0, 0, keyword)  # guild/channel=0 for local
    if added:
        return {"status": "ok", "message": f"Subscribed to '{keyword}'"}
    return {"status": "exists", "message": f"Already subscribed to '{keyword}'"}


@router.delete("/api/subscribe")
async def unsubscribe(keyword: str = Query(...)):
    keyword = keyword.strip().lower()
    removed = await _db.remove_subscription(0, 0, keyword)
    if removed:
        return {"status": "ok", "message": f"Unsubscribed from '{keyword}'"}
    return {"status": "not_found", "message": f"Not subscribed to '{keyword}'"}


@router.get("/api/subscriptions")
async def get_subscriptions():
    subs = await _db.get_channel_subscriptions(0, 0)
    return {"subscriptions": subs}


@router.post("/api/fetch")
async def fetch_papers(
    summarize: bool = Query(True, description="Generate AI summaries"),
    use_keywords: bool = Query(True, description="Filter by subscribed keywords")
):
    """Fetch new papers from arXiv, optionally filter and summarize."""
    last_fetch = await _db.get_last_fetch_time()
    papers = await _fetcher.fetch_papers(categories=_categories, since=last_fetch)

    if not papers:
        return {"status": "ok", "count": 0, "message": "No new papers found"}

    # Filter by keywords if requested
    if use_keywords:
        keywords = await _db.get_channel_subscriptions(0, 0)
        if keywords:
            filtered = KeywordFilter.filter_papers_by_keywords(papers, keywords)
            papers = [p for p, _ in filtered]
            # Store matched keywords
            kw_map = {p['id']: list(kw) for p, kw in KeywordFilter.filter_papers_by_keywords(
                await _fetcher.fetch_papers(categories=_categories, since=last_fetch), keywords
            )}
        else:
            kw_map = {}
    else:
        kw_map = {}

    # Summarize
    if summarize and _summarizer and papers:
        papers = await _summarizer.batch_summarize(papers)

    # Store
    stored = 0
    for paper in papers:
        if not await _db.is_paper_stored(paper['id']):
            paper['matched_keywords'] = ','.join(kw_map.get(paper['id'], []))
            await _db.store_paper_local(paper)
            stored += 1

    await _db.update_last_fetch_time()

    return {"status": "ok", "fetched": len(papers), "new": stored}


@router.get("/api/papers")
async def get_papers(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    keyword: Optional[str] = None,
    sort: str = Query("date", pattern="^(date|votes|title)$")
):
    """Get stored papers."""
    papers = await _db.get_recent_papers(limit=limit, offset=offset, keyword=keyword, sort=sort)
    total = await _db.count_papers(keyword=keyword)
    return {"papers": papers, "total": total, "limit": limit, "offset": offset}


@router.get("/api/search")
async def search_arxiv(q: str = Query(..., min_length=2), count: int = Query(10, ge=1, le=25)):
    """Live search arXiv."""
    papers = await _fetcher.search_papers(q, max_results=count)
    if _summarizer:
        # Summarize the top results
        papers = await _summarizer.batch_summarize(papers[:count])
    return {"papers": papers, "count": len(papers)}


@router.post("/api/vote/{paper_id}")
async def vote(paper_id: str, vote_type: str = Query(..., pattern="^(up|down)$")):
    """Vote on a paper."""
    await _db.vote_paper(paper_id, 1 if vote_type == "up" else -1)
    score = await _db.get_paper_score(paper_id)
    return {"status": "ok", "score": score}


@router.get("/api/stats")
async def stats():
    return await _db.get_global_stats()
