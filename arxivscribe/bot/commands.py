"""Discord bot slash commands implementation."""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging

from arxivscribe.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class ArxivCommands(commands.Cog):
    """Slash commands for ArxivScribe bot."""

    def __init__(self, bot: commands.Bot, db: DatabaseManager):
        self.bot = bot
        self.db = db

    @app_commands.command(name="subscribe", description="Subscribe to papers matching keywords")
    async def subscribe(self, interaction: discord.Interaction, keywords: str):
        """
        Subscribe a channel to papers matching specific keywords.
        
        Args:
            interaction: Discord interaction
            keywords: Comma-separated list of keywords
        """
        await interaction.response.defer()
        
        channel_id = interaction.channel_id
        guild_id = interaction.guild_id
        
        # Parse keywords
        keyword_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        
        if not keyword_list:
            await interaction.followup.send("❌ Please provide at least one keyword.")
            return
        
        # Add subscriptions
        added = []
        for keyword in keyword_list:
            if self.db.add_subscription(guild_id, channel_id, keyword):
                added.append(keyword)
        
        if added:
            await interaction.followup.send(
                f"✅ Subscribed to: **{', '.join(added)}**\n"
                f"This channel will now receive papers matching these keywords."
            )
            logger.info(f"Channel {channel_id} subscribed to: {added}")
        else:
            await interaction.followup.send("ℹ️ All keywords were already subscribed.")

    @app_commands.command(name="unsubscribe", description="Unsubscribe from keywords")
    async def unsubscribe(self, interaction: discord.Interaction, keywords: str):
        """
        Unsubscribe a channel from specific keywords.
        
        Args:
            interaction: Discord interaction
            keywords: Comma-separated list of keywords
        """
        await interaction.response.defer()
        
        channel_id = interaction.channel_id
        guild_id = interaction.guild_id
        
        # Parse keywords
        keyword_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        
        if not keyword_list:
            await interaction.followup.send("❌ Please provide at least one keyword.")
            return
        
        # Remove subscriptions
        removed = []
        for keyword in keyword_list:
            if self.db.remove_subscription(guild_id, channel_id, keyword):
                removed.append(keyword)
        
        if removed:
            await interaction.followup.send(
                f"✅ Unsubscribed from: **{', '.join(removed)}**"
            )
            logger.info(f"Channel {channel_id} unsubscribed from: {removed}")
        else:
            await interaction.followup.send("ℹ️ None of these keywords were subscribed.")

    @app_commands.command(name="subscriptions", description="View current keyword subscriptions")
    async def subscriptions(self, interaction: discord.Interaction):
        """Show all keywords this channel is subscribed to."""
        await interaction.response.defer()
        
        channel_id = interaction.channel_id
        guild_id = interaction.guild_id
        
        keywords = self.db.get_channel_subscriptions(guild_id, channel_id)
        
        if keywords:
            embed = discord.Embed(
                title="📚 Current Subscriptions",
                description=f"This channel is subscribed to:\n\n**{', '.join(keywords)}**",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                "ℹ️ This channel has no active subscriptions.\n"
                "Use `/subscribe <keywords>` to start receiving papers."
            )

    @app_commands.command(name="force-digest", description="Trigger paper digest immediately")
    @app_commands.checks.has_permissions(administrator=True)
    async def force_digest(self, interaction: discord.Interaction):
        """Manually trigger a digest for this channel (admin only)."""
        await interaction.response.defer()
        
        # Import here to avoid circular dependency
        from arxivscribe.bot.digest_manager import DigestManager
        
        digest_manager: DigestManager = self.bot.digest_manager
        
        await interaction.followup.send("🔄 Fetching and processing papers...")
        
        try:
            count = await digest_manager.run_digest_for_channel(interaction.channel)
            await interaction.channel.send(f"✅ Digest complete! Posted {count} papers.")
        except Exception as e:
            logger.error(f"Error running manual digest: {e}")
            await interaction.channel.send(f"❌ Error generating digest: {str(e)}")

    @app_commands.command(name="top-papers", description="Show highest-voted papers")
    async def top_papers(self, interaction: discord.Interaction, days: Optional[int] = 7):
        """
        Show the most upvoted papers from recent days.
        
        Args:
            interaction: Discord interaction
            days: Number of days to look back (default: 7)
        """
        await interaction.response.defer()
        
        channel_id = interaction.channel_id
        guild_id = interaction.guild_id
        
        top_papers = self.db.get_top_papers(guild_id, channel_id, days=days)
        
        if not top_papers:
            await interaction.followup.send(
                f"ℹ️ No papers with votes found in the last {days} days."
            )
            return
        
        embed = discord.Embed(
            title=f"🏆 Top Papers (Last {days} Days)",
            description="Most upvoted papers in this channel:",
            color=discord.Color.gold()
        )
        
        for i, paper in enumerate(top_papers[:10], 1):
            score = paper['upvotes'] - paper['downvotes']
            embed.add_field(
                name=f"{i}. {paper['title'][:100]}",
                value=(
                    f"Score: 👍 {paper['upvotes']} | 👎 {paper['downvotes']} (Net: {score})\n"
                    f"[View on arXiv]({paper['url']})"
                ),
                inline=False
            )
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ping", description="Check if bot is responsive")
    async def ping(self, interaction: discord.Interaction):
        """Simple ping command to check bot status."""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"🏓 Pong! Latency: {latency}ms",
            ephemeral=True
        )

    @force_digest.error
    async def force_digest_error(self, interaction: discord.Interaction, error):
        """Handle permission errors for force-digest command."""
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Setup function for loading this cog."""
    db = bot.db
    await bot.add_cog(ArxivCommands(bot, db))
