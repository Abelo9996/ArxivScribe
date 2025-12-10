"""Voting system for papers."""
import discord
from discord.ext import commands
import logging
from typing import Optional

from arxivscribe.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class VotingSystem:
    """Handles emoji voting on paper posts."""

    UPVOTE_EMOJI = "👍"
    MAYBE_EMOJI = "🤔"
    DOWNVOTE_EMOJI = "👎"

    def __init__(self, bot: commands.Bot, db: DatabaseManager):
        """
        Initialize voting system.
        
        Args:
            bot: Discord bot instance
            db: Database manager
        """
        self.bot = bot
        self.db = db

    async def add_voting_reactions(self, message: discord.Message):
        """
        Add voting reaction emojis to a message.
        
        Args:
            message: Discord message to add reactions to
        """
        try:
            await message.add_reaction(self.UPVOTE_EMOJI)
            await message.add_reaction(self.MAYBE_EMOJI)
            await message.add_reaction(self.DOWNVOTE_EMOJI)
        except discord.errors.Forbidden:
            logger.warning(f"Missing permissions to add reactions in channel {message.channel.id}")
        except Exception as e:
            logger.error(f"Error adding reactions: {e}")

    async def setup_listeners(self):
        """Setup event listeners for reaction adds/removes."""

        @self.bot.event
        async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
            """Handle reaction additions."""
            # Ignore bot's own reactions
            if payload.user_id == self.bot.user.id:
                return
            
            await self._handle_vote(payload, is_add=True)

        @self.bot.event
        async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
            """Handle reaction removals."""
            await self._handle_vote(payload, is_add=False)

    async def _handle_vote(self, payload: discord.RawReactionActionEvent, is_add: bool):
        """
        Handle a vote (reaction add or remove).
        
        Args:
            payload: Reaction event payload
            is_add: True if adding vote, False if removing
        """
        emoji = str(payload.emoji)
        
        # Only process our voting emojis
        if emoji not in [self.UPVOTE_EMOJI, self.MAYBE_EMOJI, self.DOWNVOTE_EMOJI]:
            return
        
        # Check if this message is a paper post
        paper_id = self.db.get_paper_by_message(
            payload.guild_id,
            payload.channel_id,
            payload.message_id
        )
        
        if not paper_id:
            return
        
        # Determine vote type
        vote_type = None
        if emoji == self.UPVOTE_EMOJI:
            vote_type = "upvote"
        elif emoji == self.DOWNVOTE_EMOJI:
            vote_type = "downvote"
        elif emoji == self.MAYBE_EMOJI:
            vote_type = "maybe"
        
        if vote_type:
            if is_add:
                self.db.add_vote(
                    paper_id,
                    payload.user_id,
                    payload.guild_id,
                    payload.channel_id,
                    vote_type
                )
                logger.debug(f"User {payload.user_id} voted {vote_type} on paper {paper_id}")
            else:
                self.db.remove_vote(
                    paper_id,
                    payload.user_id,
                    vote_type
                )
                logger.debug(f"User {payload.user_id} removed {vote_type} on paper {paper_id}")

    def get_vote_summary(self, paper_id: str) -> dict:
        """
        Get vote summary for a paper.
        
        Args:
            paper_id: Paper arXiv ID
            
        Returns:
            Dictionary with upvotes, downvotes, maybe counts
        """
        return self.db.get_vote_summary(paper_id)
