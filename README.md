# ArxivScribe 📚

**Your daily arXiv paper digest bot for Discord — with AI-powered summaries and community voting.**

ArxivScribe monitors arXiv categories, filters papers by your keywords, generates concise TLDR summaries using LLMs, and posts them to your Discord channels. Your community votes on papers to surface the best ones.

## Features

- 🔍 **Keyword subscriptions** — subscribe channels to topics like "attention", "diffusion", "RLHF"
- 🤖 **AI summaries** — each paper gets a 2-3 sentence TLDR (OpenAI or HuggingFace)
- ⏰ **Daily digests** — automated daily paper posting at your configured time
- 👍 **Community voting** — upvote/downvote papers with emoji reactions
- 🏆 **Leaderboard** — `/top` shows the highest-rated papers
- 🔎 **Live search** — `/search` queries arXiv directly from Discord
- 📊 **Stats** — track subscriptions, papers posted, and votes
- 🐳 **Docker ready** — one-command deployment

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Abelo9996/ArxivScribe.git
cd ArxivScribe
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your tokens:
#   DISCORD_BOT_TOKEN=...
#   OPENAI_API_KEY=...
```

Edit `config.yaml` to customize categories, schedule, and model.

### 3. Run

```bash
python main.py
```

Or with Docker:

```bash
docker-compose up -d
```

## Commands

| Command | Description |
|---------|-------------|
| `/subscribe <keywords>` | Subscribe to paper topics (comma-separated) |
| `/unsubscribe <keywords>` | Remove keyword subscriptions |
| `/subscriptions` | View active subscriptions |
| `/search <query>` | Search arXiv directly |
| `/digest` | Force a digest now (admin only) |
| `/top [days]` | Show highest-voted papers |
| `/stats` | Channel statistics |
| `/ping` | Check bot latency |
| `/help` | Show help |

## How It Works

1. **Subscribe** — Use `/subscribe attention, transformer` to set up keyword filters
2. **Fetch** — Daily (or on-demand), ArxivScribe pulls new papers from arXiv's API
3. **Filter** — Papers are matched against your keywords using fuzzy word-boundary matching
4. **Summarize** — Matched papers get AI-generated TLDR summaries
5. **Post** — Rich embeds with title, authors, summary, categories, and links
6. **Vote** — Community reacts with 👍 🤔 👎 to rank papers
7. **Review** — Use `/top` to see the community's favorite papers

## Architecture

```
ArxivScribe/
├── main.py                          # Entry point
├── config.yaml                      # Configuration
├── arxivscribe/
│   ├── arxiv/
│   │   ├── fetcher.py               # arXiv API client (rate-limited, retry)
│   │   └── parser.py                # XML response parser
│   ├── bot/
│   │   ├── commands.py              # Slash commands
│   │   ├── digest_manager.py        # Fetch → filter → summarize → post pipeline
│   │   ├── filters.py               # Keyword matching
│   │   ├── scheduler.py             # Daily digest scheduler
│   │   └── voting.py                # Emoji voting system
│   ├── llm/
│   │   ├── summarizer.py            # LLM orchestrator (concurrent)
│   │   ├── prompts.py               # Prompt templates
│   │   └── providers/
│   │       ├── openai_provider.py   # OpenAI API (with retry + rate limit handling)
│   │       └── huggingface_provider.py
│   └── storage/
│       └── db.py                    # Async SQLite (aiosqlite)
└── tests/
```

## Configuration

### `config.yaml`

- **arxiv.categories** — arXiv categories to monitor (e.g., `cs.LG`, `cs.AI`)
- **arxiv.max_results_per_category** — papers to fetch per category per run
- **llm.provider** — `openai` or `huggingface`
- **llm.model** — model name (default: `gpt-4o-mini`)
- **schedule.hour/minute** — daily digest time (UTC)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ | Discord bot token |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `HUGGINGFACE_API_KEY` | If using HuggingFace | HuggingFace token |

## Tech Stack

- **discord.py** — Discord bot framework
- **aiohttp** — Async HTTP for arXiv + LLM APIs
- **aiosqlite** — Async SQLite database
- **PyYAML** — Configuration
- **python-dotenv** — Environment management

## License

MIT

## Author

**Abel Yagubyan** — [GitHub](https://github.com/Abelo9996)
