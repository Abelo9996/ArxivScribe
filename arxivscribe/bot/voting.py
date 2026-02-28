"""Voting system for papers."""
import discord
from discord.ext import commands
import logging

from arxivscribe.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class VotingSystem:
    """Handles emoji voting on paper posts."""

    UPVOTE_EMOJI = "👍"
    MAYBE_EMOJI = "🤔"
    DOWNVOTE_EMOJI = "👎"
    VOTE_EMOJIS = {UPVOTE_EMOJI: "upvote", MAYBE_EMOJI: "maybe", DOWNVOTE_EMOJI: "downvote"}

    def __init__(self, bot: commands.Bot, db: DatabaseManager):
        self.bot = bot
        self.db = db

    async def add_voting_reactions(self, message: discord.Message):
        try:
            for emoji in [self.UPVOTE_EMOJI, self.MAYBE_EMOJI, self.DOWNVOTE_EMOJI]:
                await message.add_reaction(emoji)
        except discord.errors.Forbidden:
            logger.warning(f"Missing reaction permissions in {message.channel.id}")
        except Exception as e:
            logger.error(f"Error adding reactions: {e}")

    async def setup_listeners(self):
        @self.bot.event
        async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
            if payload.user_id == self.bot.user.id:
                return
            await self._handle_vote(payload, is_add=True)

        @self.bot.event
        async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
            await self._handle_vote(payload, is_add=False)

    async def _handle_vote(self, payload: discord.RawReactionActionEvent, is_add: bool):
        emoji = str(payload.emoji)
        vote_type = self.VOTE_EMOJIS.get(emoji)
        if not vote_type:
            return

        paper_id = await self.db.get_paper_by_message(
            payload.guild_id, payload.channel_id, payload.message_id
        )
        if not paper_id:
            return

        if is_add:
            await self.db.add_vote(paper_id, payload.user_id, payload.guild_id, payload.channel_id, vote_type)
        else:
            await self.db.remove_vote(paper_id, payload.user_id, vote_type)

        logger.debug(f"{'Added' if is_add else 'Removed'} {vote_type} on {paper_id} by {payload.user_id}")
