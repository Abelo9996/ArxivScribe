"""Web routes for ArxivScribe."""
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List
from pathlib import Path
import logging
import os

from arxivscribe.storage.db import DatabaseManager
from arxivscribe.arxiv.fetcher import ArxivFetcher
from arxivscribe.llm.summarizer import Summarizer
from arxivscribe.bot.filters import KeywordFilter
from arxivscribe.similarity import PaperSimilarity
from arxivscribe.export import export_bibtex, export_markdown, export_csv, export_json

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

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
    papers = await _db.get_recent_papers(limit=20)
    subs = await _db.get_all_subscriptions()
    stats = await _db.get_global_stats()
    collections = await _db.get_collections()
    distinct_cats = await _db.get_distinct_categories()
    digests = await _db.get_digest_configs(enabled_only=False)
    return templates.TemplateResponse("index.html", {
        "request": request, "papers": papers, "subscriptions": subs,
        "stats": stats, "categories": _categories, "distinct_categories": distinct_cats,
        "has_summarizer": _summarizer is not None,
        "collections": collections, "digests": digests,
        "smtp_configured": bool(os.getenv("SMTP_USER")),
    })


# --- Subscriptions ---

@router.post("/api/subscribe")
async def subscribe(keyword: str = Query(..., min_length=1)):
    keyword = keyword.strip().lower()
    added = await _db.add_subscription(0, 0, keyword)
    return {"status": "ok" if added else "exists"}


@router.delete("/api/subscribe")
async def unsubscribe(keyword: str = Query(...)):
    removed = await _db.remove_subscription(0, 0, keyword.strip().lower())
    return {"status": "ok" if removed else "not_found"}


@router.get("/api/subscriptions")
async def get_subscriptions():
    return {"subscriptions": await _db.get_channel_subscriptions(0, 0)}


# --- Papers (with pagination + date filters) ---

@router.post("/api/fetch")
async def fetch_papers(summarize: bool = Query(True), use_keywords: bool = Query(True)):
    papers = await _fetcher.fetch_papers(categories=_categories)
    if not papers:
        return {"status": "ok", "fetched": 0, "new": 0, "message": "No papers found"}

    matched_kw_map = {}
    if use_keywords:
        keywords = await _db.get_channel_subscriptions(0, 0)
        if keywords:
            filtered = KeywordFilter.filter_papers_by_keywords(papers, keywords)
            matched_kw_map = {p['id']: list(kw) for p, kw in filtered}
            papers = [p for p, _ in filtered]

    if not papers:
        return {"status": "ok", "fetched": 0, "new": 0, "message": "No papers matched keywords"}

    if summarize and _summarizer:
        papers = await _summarizer.batch_summarize(papers)

    stored = 0
    for paper in papers:
        if not await _db.is_paper_stored(paper['id']):
            paper['matched_keywords'] = ','.join(matched_kw_map.get(paper['id'], []))
            await _db.store_paper_local(paper)
            stored += 1

    await _db.update_last_fetch_time()
    return {"status": "ok", "fetched": len(papers), "new": stored}


@router.get("/api/papers")
async def get_papers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    sort: str = Query("date", pattern="^(date|votes|title)$"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    category: Optional[str] = None,
):
    offset = (page - 1) * per_page
    papers = await _db.get_recent_papers(
        limit=per_page, offset=offset, keyword=keyword, sort=sort,
        date_from=date_from, date_to=date_to, category=category
    )
    total = await _db.count_papers(
        keyword=keyword, date_from=date_from, date_to=date_to, category=category
    )
    total_pages = max(1, -(-total // per_page))  # ceil division
    return {
        "papers": papers, "total": total,
        "page": page, "per_page": per_page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.get("/api/search")
async def search_arxiv(q: str = Query(..., min_length=2), count: int = Query(10, ge=1, le=25)):
    papers = await _fetcher.search_papers(q, max_results=count)
    if _summarizer:
        papers = await _summarizer.batch_summarize(papers[:count])
    return {"papers": papers, "count": len(papers)}


# --- Voting ---

@router.post("/api/vote/{paper_id}")
async def vote(paper_id: str, vote_type: str = Query(..., pattern="^(up|down)$")):
    await _db.vote_paper(paper_id, 1 if vote_type == "up" else -1)
    score = await _db.get_paper_score(paper_id)
    return {"status": "ok", "score": score}


# --- Bookmarks ---

@router.post("/api/bookmark/{paper_id}")
async def add_bookmark(paper_id: str, collection: str = Query("Reading List"), notes: str = Query("")):
    added = await _db.add_bookmark(paper_id, collection, notes)
    return {"status": "ok" if added else "exists"}


@router.delete("/api/bookmark/{paper_id}")
async def remove_bookmark(paper_id: str, collection: str = Query("Reading List")):
    removed = await _db.remove_bookmark(paper_id, collection)
    return {"status": "ok" if removed else "not_found"}


@router.get("/api/bookmarks")
async def get_bookmarks(collection: Optional[str] = None):
    bookmarks = await _db.get_bookmarks(collection)
    collections = await _db.get_collections()
    return {"bookmarks": bookmarks, "collections": collections}


@router.get("/api/collections")
async def get_collections():
    return {"collections": await _db.get_collections()}


# --- Similar papers ---

@router.get("/api/similar/{paper_id}")
async def similar_papers(paper_id: str, count: int = Query(5, ge=1, le=20)):
    target = await _db.get_paper_by_id(paper_id)
    if not target:
        return {"error": "Paper not found", "papers": []}
    all_papers = await _db.get_all_papers_for_similarity()
    similar = PaperSimilarity.find_similar(target, all_papers, top_k=count)
    return {"papers": [{"paper": p, "score": round(s, 3)} for p, s in similar]}


# --- Export ---

@router.get("/api/export")
async def export_papers(
    fmt: str = Query("bibtex", pattern="^(bibtex|markdown|csv|json)$"),
    limit: int = Query(100, ge=1, le=1000),
    keyword: Optional[str] = None,
    collection: Optional[str] = None,
):
    papers = await _db.get_bookmarks(collection) if collection else await _db.get_recent_papers(limit=limit, keyword=keyword)
    if not papers:
        return PlainTextResponse("No papers to export", status_code=404)
    exporters = {
        'bibtex': (export_bibtex, 'application/x-bibtex', 'papers.bib'),
        'markdown': (export_markdown, 'text/markdown', 'papers.md'),
        'csv': (export_csv, 'text/csv', 'papers.csv'),
        'json': (export_json, 'application/json', 'papers.json'),
    }
    func, content_type, filename = exporters[fmt]
    return PlainTextResponse(func(papers), media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# --- Digest config ---

@router.get("/api/digests")
async def get_digests():
    return {"digests": await _db.get_digest_configs(enabled_only=False)}


@router.post("/api/digests")
async def create_digest(
    email: str = Query(...),
    keywords: str = Query(""),
    categories: str = Query(""),
    schedule: str = Query("daily", pattern="^(daily|weekly)$"),
    send_hour: int = Query(9, ge=0, le=23),
):
    digest_id = await _db.add_digest_config(
        digest_type="email", target=email, keywords=keywords,
        categories=categories, schedule=schedule, send_hour=send_hour
    )
    return {"status": "ok", "id": digest_id}


@router.delete("/api/digests/{digest_id}")
async def delete_digest(digest_id: int):
    removed = await _db.remove_digest_config(digest_id)
    return {"status": "ok" if removed else "not_found"}


@router.post("/api/digests/{digest_id}/toggle")
async def toggle_digest(digest_id: int, enabled: bool = Query(...)):
    toggled = await _db.toggle_digest_config(digest_id, enabled)
    return {"status": "ok" if toggled else "not_found"}


@router.post("/api/digests/test")
async def test_digest(email: str = Query(...)):
    """Send a test digest email."""
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    if not smtp_user or not smtp_pass:
        return {"status": "error", "message": "SMTP not configured. Set SMTP_USER and SMTP_PASS in .env"}

    from arxivscribe.digest import DigestMailer
    mailer = DigestMailer(smtp_user=smtp_user, smtp_pass=smtp_pass)

    papers = await _db.get_recent_papers(limit=5)
    if not papers:
        return {"status": "error", "message": "No papers in DB to send"}

    success = await mailer.send_digest(email, papers, subject="ArxivScribe Test Digest")
    return {"status": "ok" if success else "error", "message": "Test digest sent!" if success else "Failed to send"}


# --- Categories ---

@router.get("/api/categories")
async def get_categories():
    return {"configured": _categories, "found": await _db.get_distinct_categories()}


# --- Stats ---

@router.get("/api/stats")
async def stats():
    return await _db.get_global_stats()
