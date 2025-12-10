"""Digest manager for fetching, summarizing, and posting papers."""
import discord
from discord.ext import commands
import logging
from typing import List, Optional
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
        self,
        bot: commands.Bot,
        db: DatabaseManager,
        fetcher: ArxivFetcher,
        summarizer: Summarizer,
        voting_system: VotingSystem,
        categories: List[str]
    ):
        """
        Initialize digest manager.
        
        Args:
            bot: Discord bot instance
            db: Database manager
            fetcher: ArXiv paper fetcher
            summarizer: LLM summarizer
            voting_system: Voting system
            categories: arXiv categories to fetch
        """
        self.bot = bot
        self.db = db
        self.fetcher = fetcher
        self.summarizer = summarizer
        self.voting_system = voting_system
        self.categories = categories

    async def run_digest_for_all_channels(self) -> int:
        """
        Run digest for all subscribed channels.
        
        Returns:
            Total number of papers posted
        """
        total_posted = 0
        
        # Get all unique channels with subscriptions
        channels = self.db.get_all_subscribed_channels()
        
        for guild_id, channel_id in channels:
            try:
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    logger.warning(f"Could not find channel {channel_id}")
                    continue
                
                count = await self.run_digest_for_channel(channel)
                total_posted += count
            except Exception as e:
                logger.error(f"Error running digest for channel {channel_id}: {e}")
        
        return total_posted

    async def run_digest_for_channel(self, channel: discord.TextChannel) -> int:
        """
        Run digest for a specific channel.
        
        Args:
            channel: Discord text channel
            
        Returns:
            Number of papers posted
        """
        guild_id = channel.guild.id
        channel_id = channel.id
        
        # Get channel's subscribed keywords
        keywords = self.db.get_channel_subscriptions(guild_id, channel_id)
        
        if not keywords:
            logger.info(f"Channel {channel_id} has no subscriptions, skipping.")
            return 0
        
        logger.info(f"Running digest for channel {channel.name} with keywords: {keywords}")
        
        # Fetch new papers
        last_fetch = self.db.get_last_fetch_time()
        papers = await self.fetcher.fetch_papers(
            categories=self.categories,
            since=last_fetch
        )
        
        logger.info(f"Fetched {len(papers)} papers from arXiv")
        
        if not papers:
            return 0
        
        # Filter papers by keywords
        filtered_papers = KeywordFilter.filter_papers_by_keywords(papers, keywords)
        
        logger.info(f"Filtered to {len(filtered_papers)} papers matching keywords")
        
        if not filtered_papers:
            return 0
        
        # Summarize and post each paper
        posted_count = 0
        for paper, matched_keywords in filtered_papers:
            try:
                # Check if already posted to this channel
                if self.db.is_paper_posted(paper['id'], guild_id, channel_id):
                    logger.debug(f"Paper {paper['id']} already posted to channel {channel_id}")
                    continue
                
                # Generate summary
                summary = await self.summarizer.summarize(paper)
                paper['summary'] = summary
                
                # Post to channel
                message = await self._post_paper(channel, paper, matched_keywords)
                
                # Add voting reactions
                await self.voting_system.add_voting_reactions(message)
                
                # Store in database
                self.db.store_paper(paper, guild_id, channel_id, message.id)
                
                posted_count += 1
                logger.info(f"Posted paper {paper['id']} to channel {channel.name}")
                
            except Exception as e:
                logger.error(f"Error processing paper {paper.get('id', 'unknown')}: {e}")
        
        # Update last fetch time
        self.db.update_last_fetch_time()
        
        return posted_count

    async def _post_paper(
        self,
        channel: discord.TextChannel,
        paper: dict,
        matched_keywords: set
    ) -> discord.Message:
        """
        Post a paper to a Discord channel.
        
        Args:
            channel: Discord text channel
            paper: Paper dictionary
            matched_keywords: Keywords that matched this paper
            
        Returns:
            Posted message
        """
        embed = discord.Embed(
            title=paper['title'][:256],  # Discord limit
            url=paper['url'],
            description=paper.get('summary', 'No summary available'),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Authors (truncate if too long)
        authors = ", ".join(paper.get('authors', []))
        if len(authors) > 1024:
            authors = authors[:1021] + "..."
        embed.add_field(name="Authors", value=authors, inline=False)
        
        # Categories
        categories = ", ".join(paper.get('categories', []))
        embed.add_field(name="Categories", value=categories, inline=True)
        
        # Published date
        published = paper.get('published', 'Unknown')
        embed.add_field(name="Published", value=published, inline=True)
        
        # Matched keywords
        keywords_str = ", ".join(sorted(matched_keywords))
        embed.add_field(name="Matched Keywords", value=f"`{keywords_str}`", inline=False)
        
        # PDF link
        if paper.get('pdf_url'):
            embed.add_field(name="PDF", value=f"[Download]({paper['pdf_url']})", inline=True)
        
        # Footer
        embed.set_footer(text=f"arXiv ID: {paper['id']}")
        
        message = await channel.send(embed=embed)
        return message
