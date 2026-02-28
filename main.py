"""Main entry point for ArxivScribe Discord bot."""
import discord
from discord.ext import commands
import logging
import yaml
import os
from datetime import time
from pathlib import Path
from dotenv import load_dotenv

from arxivscribe.bot.commands import ArxivCommands
from arxivscribe.bot.scheduler import Scheduler
from arxivscribe.bot.digest_manager import DigestManager
from arxivscribe.bot.voting import VotingSystem
from arxivscribe.arxiv.fetcher import ArxivFetcher
from arxivscribe.llm.summarizer import Summarizer
from arxivscribe.storage.db import DatabaseManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('arxivscribe.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    return config


class ArxivScribeBot(commands.Bot):
    """ArxivScribe Discord bot."""

    def __init__(self, config: dict):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True

        super().__init__(
            command_prefix=config.get('bot', {}).get('prefix', '!'),
            intents=intents,
            help_command=None
        )

        self.config = config

        # Initialize database
        db_path = config.get('storage', {}).get('database_path', 'arxivscribe.db')
        self.db = DatabaseManager(db_path)

        # Initialize arXiv fetcher
        arxiv_config = config.get('arxiv', {})
        self.fetcher = ArxivFetcher(
            max_results_per_category=arxiv_config.get('max_results_per_category', 50),
            rate_limit_seconds=arxiv_config.get('rate_limit_seconds', 3.0)
        )

        # Initialize LLM summarizer
        llm_config = config.get('llm', {})
        provider = llm_config.get('provider', 'openai')
        api_key_env = f"{provider.upper()}_API_KEY"
        self.summarizer = Summarizer(
            provider=provider,
            api_key=os.getenv(api_key_env) or os.getenv("OPENAI_API_KEY"),
            model=llm_config.get('model'),
            max_concurrent=llm_config.get('max_concurrent', 5)
        )

        # Initialize voting system
        self.voting_system = VotingSystem(self, self.db)

        # Initialize digest manager
        categories = arxiv_config.get('categories', ['cs.LG', 'cs.AI'])
        self.digest_manager = DigestManager(
            self, self.db, self.fetcher, self.summarizer,
            self.voting_system, categories
        )

        # Initialize scheduler
        schedule_config = config.get('schedule', {})
        schedule_time = time(
            hour=schedule_config.get('hour', 9),
            minute=schedule_config.get('minute', 0)
        )
        self.scheduler = Scheduler(self, self.digest_manager, schedule_time)

    async def setup_hook(self):
        """Setup hook called when bot is starting."""
        logger.info("Setting up bot...")

        # Initialize async DB
        await self.db.initialize()

        # Load commands cog
        await self.load_extension('arxivscribe.bot.commands')

        # Setup voting system listeners
        await self.voting_system.setup_listeners()

        # Sync slash commands
        await self.tree.sync()

        logger.info("Bot setup complete")

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Logged in as {self.user.name} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # Start scheduler
        self.scheduler.start()

        # Set presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="arXiv for new papers"
            )
        )

        logger.info("ArxivScribe is ready!")

    async def close(self):
        """Clean up when bot is closing."""
        logger.info("Shutting down bot...")
        self.scheduler.stop()
        await self.db.close()
        await super().close()


def main():
    """Main entry point."""
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return

    discord_token = os.getenv('DISCORD_BOT_TOKEN')
    if not discord_token:
        logger.error("DISCORD_BOT_TOKEN not found in environment variables")
        return

    log_level = config.get('logging', {}).get('level', 'INFO')
    logging.getLogger().setLevel(getattr(logging, log_level.upper()))

    bot = ArxivScribeBot(config)

    try:
        bot.run(discord_token)
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
