"""ArxivScribe — Local web app for arXiv paper digests with AI summaries."""
import uvicorn
import yaml
import os
import logging
import webbrowser
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from arxivscribe.storage.db import DatabaseManager
from arxivscribe.arxiv.fetcher import ArxivFetcher
from arxivscribe.llm.summarizer import Summarizer
from arxivscribe.web.routes import router, set_app_deps

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('arxivscribe.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    config = load_config()

    # DB
    db_path = config.get('storage', {}).get('database_path', 'arxivscribe.db')
    db = DatabaseManager(db_path)
    await db.initialize()

    # Fetcher
    arxiv_cfg = config.get('arxiv', {})
    fetcher = ArxivFetcher(
        max_results_per_category=arxiv_cfg.get('max_results_per_category', 50),
        rate_limit_seconds=arxiv_cfg.get('rate_limit_seconds', 3.0)
    )

    # Summarizer
    llm_cfg = config.get('llm', {})
    provider = llm_cfg.get('provider', 'openai')
    api_key = os.getenv(f"{provider.upper()}_API_KEY") or os.getenv("OPENAI_API_KEY")
    summarizer = Summarizer(
        provider=provider,
        api_key=api_key,
        model=llm_cfg.get('model'),
        max_concurrent=llm_cfg.get('max_concurrent', 5)
    ) if api_key else None

    if not summarizer:
        logger.warning("No API key found — summaries disabled. Set OPENAI_API_KEY in .env")

    categories = arxiv_cfg.get('categories', ['cs.LG', 'cs.AI'])

    set_app_deps(db, fetcher, summarizer, categories, config)

    # Start digest scheduler if SMTP configured
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    digest_scheduler = None
    if smtp_user and smtp_pass:
        from arxivscribe.digest import DigestMailer, DigestScheduler
        mailer = DigestMailer(smtp_user=smtp_user, smtp_pass=smtp_pass)
        digest_scheduler = DigestScheduler(db, fetcher, summarizer, mailer, categories)
        digest_scheduler.start()
        logger.info("Digest email scheduler started")

    logger.info("ArxivScribe started at http://localhost:8000")

    yield

    if digest_scheduler:
        digest_scheduler.stop()
    await db.close()


app = FastAPI(title="ArxivScribe", lifespan=lifespan)

# Static files and templates
static_dir = Path(__file__).parent / "arxivscribe" / "web" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(router)


def main():
    config = load_config()
    host = config.get('server', {}).get('host', '127.0.0.1')
    port = config.get('server', {}).get('port', 8000)

    print(f"\n  ArxivScribe running at http://{host}:{port}\n")
    webbrowser.open(f"http://{host}:{port}")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
