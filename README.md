# 📚 ArxivScribe

> **Automated ML Paper Digests for Discord**  
> Monitor arXiv, generate AI-powered summaries, and keep your research team informed.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue.svg)](https://github.com/Rapptz/discord.py)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## ✨ Features

- 🤖 **Automated arXiv Monitoring** — Fetches new papers daily from CS and ML categories
- 🧠 **AI-Powered Summaries** — Generates concise TLDRs using OpenAI or HuggingFace
- 🔍 **Keyword Filtering** — Subscribe to topics you care about (transformers, RLHF, diffusion, etc.)
- 📊 **Community Voting** — Upvote/downvote papers with emoji reactions
- 📈 **Top Papers Ranking** — See what the community finds most interesting
- ⚙️ **Fully Configurable** — Easy YAML config for categories, schedule, and models
- 🐳 **Docker Ready** — Deploy in seconds with Docker Compose

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Discord Bot Token ([Create one here](https://discord.com/developers/applications))
- OpenAI API Key or HuggingFace API Token

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Abelo9996/ArxivScribe.git
   cd ArxivScribe
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your tokens:
   # DISCORD_BOT_TOKEN=your_token_here
   # OPENAI_API_KEY=your_openai_key_here
   ```

4. **Configure bot settings** (optional)
   ```bash
   # Edit config.yaml to customize:
   # - arXiv categories
   # - Daily schedule time
   # - LLM provider and model
   ```

5. **Run the bot**
   ```bash
   python main.py
   ```

### Docker Deployment

```bash
# Set up environment variables
cp .env.example .env
# Edit .env with your tokens

# Build and run
docker-compose up -d

# View logs
docker-compose logs -f
```

---

## 📖 Usage

### Slash Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/subscribe` | Subscribe to keywords | `/subscribe diffusion, RLHF` |
| `/unsubscribe` | Unsubscribe from keywords | `/unsubscribe diffusion` |
| `/subscriptions` | View active subscriptions | `/subscriptions` |
| `/force-digest` | Trigger digest immediately (admin) | `/force-digest` |
| `/top-papers` | Show highest-voted papers | `/top-papers 7` |
| `/ping` | Check bot responsiveness | `/ping` |

### Workflow

1. **Subscribe to Topics**
   ```
   /subscribe transformers, attention mechanisms, LLMs
   ```

2. **Daily Digests**
   - Bot automatically posts matching papers every morning (configurable)
   - Each paper includes:
     - Title and authors
     - AI-generated TLDR summary
     - arXiv link and PDF download
     - Matched keywords
     - Category tags

3. **Vote on Papers**
   - Click 👍 for interesting papers
   - Click 🤔 for maybes
   - Click 👎 for not relevant

4. **Check Top Papers**
   ```
   /top-papers 7
   ```
   See what the community found most valuable this week.

---

## ⚙️ Configuration

### `config.yaml`

```yaml
# arXiv categories to monitor
arxiv:
  categories:
    - cs.LG   # Machine Learning
    - cs.AI   # Artificial Intelligence
    - cs.CL   # Computation and Language
    - cs.CV   # Computer Vision
    - stat.ML # Statistics ML
  max_results_per_category: 50

# Daily schedule (24-hour format)
schedule:
  hour: 9
  minute: 0

# LLM provider
llm:
  provider: openai  # or 'huggingface'
  model: gpt-3.5-turbo
```

### Environment Variables

```bash
DISCORD_BOT_TOKEN=your_discord_token
OPENAI_API_KEY=your_openai_key
HUGGINGFACE_API_KEY=your_huggingface_token  # if using HF
```

---

## 🏗️ Architecture

```
arxivscribe/
├── bot/
│   ├── commands.py        # Slash command handlers
│   ├── scheduler.py       # Daily digest scheduler
│   ├── digest_manager.py  # Fetch → Filter → Summarize → Post
│   ├── filters.py         # Keyword matching logic
│   └── voting.py          # Emoji voting system
├── arxiv/
│   ├── fetcher.py         # arXiv API client
│   └── parser.py          # XML response parser
├── llm/
│   ├── summarizer.py      # Main summarization interface
│   ├── prompts.py         # LLM prompt templates
│   └── providers/
│       ├── openai_provider.py
│       └── huggingface_provider.py
└── storage/
    └── db.py              # SQLite database manager
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=arxivscribe --cov-report=html

# Run specific test file
pytest tests/test_filters.py
```

---

## 🛠️ Extending ArxivScribe

### Add a New LLM Provider

1. Create `arxivscribe/llm/providers/my_provider.py`
2. Implement `generate(prompt: str) -> str` method
3. Update `summarizer.py` to support the new provider

### Add Slack Integration

The modular architecture makes it easy to add Slack:
1. Create `arxivscribe/slack/` module
2. Reuse `digest_manager.py` logic
3. Adapt message formatting for Slack blocks

### Enable PDF Summarization

1. Add PDF parsing (e.g., PyPDF2)
2. Extract text from arXiv PDFs
3. Feed extracted text to LLM for deeper summaries

---

## 🗺️ Roadmap

- [ ] Slack bot integration
- [ ] Web dashboard for analytics
- [ ] PDF full-text summarization
- [ ] Topic clustering and recommendations
- [ ] Multi-language support
- [ ] RSS feed generation
- [ ] Integration with Notion/Obsidian
- [ ] Author follow system

---

## 🤝 Contributing

Contributions are welcome! Here's how:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run tests (`pytest`)
6. Commit changes (`git commit -m 'Add amazing feature'`)
7. Push to branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Code Style

- Follow PEP 8
- Add docstrings to all functions
- Keep functions focused and modular
- Write tests for new features

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [arXiv](https://arxiv.org/) for providing open access to research papers
- [Discord.py](https://github.com/Rapptz/discord.py) for the excellent Discord library
- [OpenAI](https://openai.com/) and [HuggingFace](https://huggingface.co/) for LLM APIs
- The open-source community for inspiration

---

## 📧 Contact

**Project Maintainer:** [@Abelo9996](https://github.com/Abelo9996)

**Issues:** [GitHub Issues](https://github.com/Abelo9996/ArxivScribe/issues)

---

## 🌟 Star History

If you find ArxivScribe useful, please consider giving it a star! It helps others discover the project.

---

**Made with ❤️ for the ML research community**
