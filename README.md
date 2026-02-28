# ArxivScribe

[![GitHub stars](https://img.shields.io/github/stars/Abelo9996/ArxivScribe?style=social)](https://github.com/Abelo9996/ArxivScribe)

**AI-powered arXiv paper digests — fetch, summarize, search, and organize research papers.**

ArxivScribe is a local-first research tool that monitors arXiv, generates AI summaries, and helps you stay on top of the papers that matter. Runs as a web app on your machine or from the CLI. No account needed, your data stays local.

## Features

- **Keyword subscriptions** — subscribe to topics like "attention", "diffusion", "RLHF"
- **AI summaries** — 2-3 sentence TLDRs via OpenAI, HuggingFace, or **Ollama** (free/local)
- **Pagination & filters** — date range, category, keyword, sort by date/votes/title
- **Reading list & bookmarks** — save papers to custom collections
- **Similar papers** — TF-IDF "more like this" recommendations
- **Export** — BibTeX, Markdown, CSV, JSON
- **Daily email digests** — scheduled email with new papers matching your interests
- **Community voting** — upvote/downvote to surface the best papers
- **Live search** — query arXiv directly from the UI
- **CLI** — `arxivscribe fetch`, `arxivscribe search`, `arxivscribe export`
- **Dark/light theme** — looks good on desktop and mobile
- **Zero-config mode** — works without any API key (summaries optional)

## Quick Start

### Option 1: pip install (recommended)

```bash
pip install arxivscribe
arxivscribe serve
```

### Option 2: From source

```bash
git clone https://github.com/Abelo9996/ArxivScribe.git
cd ArxivScribe
pip install -r requirements.txt
python main.py
```

Opens automatically at **http://localhost:8000**

### Option 3: Docker

```bash
docker-compose up -d
```

## Configuration

### API Keys (optional)

Create a `.env` file:

```bash
# AI summaries (pick one — or skip for no summaries)
OPENAI_API_KEY=sk-...          # OpenAI (gpt-4o-mini, fast + cheap)
HUGGINGFACE_API_KEY=hf_...     # HuggingFace (free tier available)

# Or use Ollama for free local summaries:
# Set provider to "ollama" in config.yaml, then:
# ollama serve && ollama pull llama3.2

# Email digests (optional)
SMTP_USER=your@gmail.com
SMTP_PASS=your-app-password    # Gmail: use App Password
```

### `config.yaml`

```yaml
arxiv:
  categories: [cs.LG, cs.AI, cs.CL, cs.CV, stat.ML, cs.IR]
  max_results_per_category: 50

llm:
  provider: openai    # openai | huggingface | ollama
  model: gpt-4o-mini  # or llama3.2 for ollama

server:
  host: 127.0.0.1
  port: 8000
```

## CLI Usage

```bash
# Fetch papers with keyword filtering
arxivscribe fetch --keywords "transformer,attention"

# Search arXiv
arxivscribe search "multi-agent reinforcement learning"

# List stored papers
arxivscribe list --sort votes --limit 20

# Export to BibTeX
arxivscribe export --format bibtex --output papers.bib

# Manage subscriptions
arxivscribe subscribe "diffusion,RLHF"
arxivscribe subscriptions

# Start web UI
arxivscribe serve --port 8000

# Show stats
arxivscribe stats
```

## Email Digests

Set up automatic email digests from the **Email Digests** tab in the web UI:

1. Configure SMTP in `.env` (Gmail App Password works great)
2. Enter your email, keywords, and schedule (daily/weekly)
3. ArxivScribe fetches new papers and emails you a digest

## Architecture

```
ArxivScribe/
├── main.py                          # FastAPI web app entry point
├── config.yaml                      # Configuration
├── arxivscribe/
│   ├── cli.py                       # Click CLI interface
│   ├── export.py                    # BibTeX/Markdown/CSV/JSON export
│   ├── similarity.py                # TF-IDF paper recommendations
│   ├── digest.py                    # Email digest scheduler + mailer
│   ├── arxiv/
│   │   ├── fetcher.py               # arXiv API (rate-limited, retry)
│   │   └── parser.py                # XML parser
│   ├── bot/
│   │   └── filters.py               # Keyword matching
│   ├── llm/
│   │   ├── summarizer.py            # Multi-provider LLM orchestrator
│   │   ├── prompts.py               # Prompt templates
│   │   └── providers/
│   │       ├── openai_provider.py
│   │       ├── huggingface_provider.py
│   │       └── ollama_provider.py   # Free local LLM
│   ├── storage/
│   │   └── db.py                    # Async SQLite
│   └── web/
│       ├── routes.py                # FastAPI routes
│       ├── templates/               # Jinja2 HTML
│       └── static/                  # CSS + JS
└── tests/
```

## Tech Stack

- **FastAPI + Uvicorn** — async web server
- **aiohttp** — async HTTP for arXiv + LLM APIs
- **aiosqlite** — async SQLite (your data stays local)
- **Click + Rich** — beautiful CLI
- **Vanilla JS** — zero frontend dependencies

## Why ArxivScribe?

| Feature | ArxivScribe | arxiv-sanity | Semantic Scholar |
|---------|:-----------:|:------------:|:----------------:|
| Self-hosted / local | ✅ | ❌ | ❌ |
| AI summaries | ✅ | ❌ | ❌ |
| Free (Ollama) | ✅ | ✅ | ✅ |
| CLI | ✅ | ❌ | ❌ |
| Email digests | ✅ | ❌ | ✅ |
| BibTeX export | ✅ | ❌ | ✅ |
| Custom keyword filters | ✅ | ✅ | ❌ |
| Similar papers | ✅ | ✅ | ✅ |
| Voting | ✅ | ❌ | ❌ |
| No account needed | ✅ | ✅ | ❌ |

## License

MIT

## Author

**Abel Yagubyan** — [GitHub](https://github.com/Abelo9996)
