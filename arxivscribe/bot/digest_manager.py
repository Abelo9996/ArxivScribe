"""Digest manager for fetching, summarizing, and posting papers."""
import discord
from discord.ext import commands
import logging
from typing import List
from datetime import datetime

from arxivscribe.arxiv.fetcher import ArxivFetcher
from arxivscribe.llm.summarizer import Summarizer
from arxivscribe.bot.filters import KeywordFilter
from arxivscribe.bot.voting import VotingSystem
from arxivscribe.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class DigestManager:
    """Manages the paper digest workflow."""

    def __init__(
        self, bot: commands.Bot, db: DatabaseManager,
        fetcher: ArxivFetcher, summarizer: Summarizer,
        voting_system: VotingSystem, categories: List[str]
    ):
        self.bot = bot
        self.db = db
        self.fetcher = fetcher
        self.summarizer = summarizer
        self.voting_system = voting_system
        self.categories = categories

    async def run_digest_for_all_channels(self) -> int:
        """Run digest for all subscribed channels."""
        total_posted = 0
        channels = await self.db.get_all_subscribed_channels()

        for guild_id, channel_id in channels:
            try:
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    logger.warning(f"Channel {channel_id} not found, skipping")
                    continue
                count = await self.run_digest_for_channel(channel)
                total_posted += count
            except Exception as e:
                logger.error(f"Error running digest for channel {channel_id}: {e}")

        return total_posted

    async def run_digest_for_channel(self, channel: discord.TextChannel) -> int:
        """Run digest for a specific channel."""
        guild_id = channel.guild.id
        channel_id = channel.id

        keywords = await self.db.get_channel_subscriptions(guild_id, channel_id)
        if not keywords:
            return 0

        logger.info(f"Digest for #{channel.name}: keywords={keywords}")

        # Check guild-specific categories
        guild_settings = await self.db.get_guild_settings(guild_id)
        categories = self.categories
        if guild_settings and guild_settings.get('categories'):
            categories = guild_settings['categories'].split(',')

        # Fetch papers
        last_fetch = await self.db.get_last_fetch_time()
        papers = await self.fetcher.fetch_papers(categories=categories, since=last_fetch)

        if not papers:
            return 0

        logger.info(f"Fetched {len(papers)} papers, filtering by {len(keywords)} keyword(s)")

        # Filter
        filtered = KeywordFilter.filter_papers_by_keywords(papers, keywords)
        if not filtered:
            return 0

        # Summarize and post
        posted = 0
        for paper, matched_keywords in filtered:
            try:
                if await self.db.is_paper_posted(paper['id'], guild_id, channel_id):
                    continue

                paper['summary'] = await self.summarizer.summarize(paper)
                message = await self._post_paper(channel, paper, matched_keywords)
                await self.voting_system.add_voting_reactions(message)
                await self.db.store_paper(paper, guild_id, channel_id, message.id)
                posted += 1

            except Exception as e:
                logger.error(f"Error posting paper {paper.get('id', '?')}: {e}")

        await self.db.update_last_fetch_time()
        logger.info(f"Posted {posted} papers to #{channel.name}")
        return posted

    async def _post_paper(
        self, channel: discord.TextChannel,
        paper: dict, matched_keywords: set
    ) -> discord.Message:
        """Post a paper embed to Discord."""
        # Color based on primary category
        cat = paper.get('primary_category', '')
        color = self._category_color(cat)

        embed = discord.Embed(
            title=paper['title'][:256],
            url=paper['url'],
            description=paper.get('summary', 'No summary available'),
            color=color,
            timestamp=datetime.utcnow()
        )

        # Authors (compact)
        authors = paper.get('authors', [])
        if len(authors) > 5:
            authors_str = ", ".join(authors[:5]) + f" +{len(authors) - 5} more"
        else:
            authors_str = ", ".join(authors) or "Unknown"
        embed.add_field(name="Authors", value=authors_str, inline=False)

        # Categories + Keywords in one row
        cats = ", ".join(paper.get('categories', [])[:5])
        embed.add_field(name="Categories", value=f"`{cats}`", inline=True)

        kw_str = ", ".join(sorted(matched_keywords))
        embed.add_field(name="Matched", value=f"`{kw_str}`", inline=True)

        # Links
        links = f"[Abstract]({paper['url']})"
        if paper.get('pdf_url'):
            links += f" | [PDF]({paper['pdf_url']})"
        embed.add_field(name="Links", value=links, inline=False)

        embed.set_footer(text=f"arXiv:{paper['id']}")

        return await channel.send(embed=embed)

    @staticmethod
    def _category_color(category: str) -> discord.Color:
        """Map arXiv category to embed color."""
        colors = {
            'cs.LG': discord.Color.blue(),
            'cs.AI': discord.Color.purple(),
            'cs.CL': discord.Color.green(),
            'cs.CV': discord.Color.orange(),
            'stat.ML': discord.Color.teal(),
            'cs.IR': discord.Color.gold(),
        }
        return colors.get(category, discord.Color.greyple())
