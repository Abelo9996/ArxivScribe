"""Discord bot slash commands implementation."""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging

from arxivscribe.storage.db import DatabaseManager

logger = logging.getLogger(__name__)

# Autocomplete for arXiv categories
ARXIV_CATEGORIES = [
    "cs.LG", "cs.AI", "cs.CL", "cs.CV", "cs.IR", "cs.RO", "cs.NE", "cs.MA",
    "stat.ML", "stat.ME", "math.OC", "eess.SP", "q-bio.QM", "physics.data-an"
]


class ArxivCommands(commands.Cog):
    """Slash commands for ArxivScribe bot."""

    def __init__(self, bot: commands.Bot, db: DatabaseManager):
        self.bot = bot
        self.db = db

    @app_commands.command(name="subscribe", description="Subscribe to papers matching keywords")
    @app_commands.describe(keywords="Comma-separated keywords (e.g. 'attention, transformer, RL')")
    async def subscribe(self, interaction: discord.Interaction, keywords: str):
        await interaction.response.defer()

        channel_id = interaction.channel_id
        guild_id = interaction.guild_id

        keyword_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        if not keyword_list:
            await interaction.followup.send("❌ Please provide at least one keyword.")
            return

        added = []
        for keyword in keyword_list:
            if await self.db.add_subscription(guild_id, channel_id, keyword):
                added.append(keyword)

        if added:
            await interaction.followup.send(
                f"✅ Subscribed to: **{', '.join(added)}**\n"
                f"This channel will receive papers matching these keywords in the daily digest."
            )
        else:
            await interaction.followup.send("ℹ️ All keywords were already subscribed.")

    @app_commands.command(name="unsubscribe", description="Unsubscribe from keywords")
    @app_commands.describe(keywords="Comma-separated keywords to remove")
    async def unsubscribe(self, interaction: discord.Interaction, keywords: str):
        await interaction.response.defer()

        channel_id = interaction.channel_id
        guild_id = interaction.guild_id

        keyword_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        if not keyword_list:
            await interaction.followup.send("❌ Please provide at least one keyword.")
            return

        removed = []
        for keyword in keyword_list:
            if await self.db.remove_subscription(guild_id, channel_id, keyword):
                removed.append(keyword)

        if removed:
            await interaction.followup.send(f"✅ Unsubscribed from: **{', '.join(removed)}**")
        else:
            await interaction.followup.send("ℹ️ None of those keywords were subscribed.")

    @app_commands.command(name="subscriptions", description="View current keyword subscriptions")
    async def subscriptions(self, interaction: discord.Interaction):
        await interaction.response.defer()

        keywords = await self.db.get_channel_subscriptions(interaction.guild_id, interaction.channel_id)

        if keywords:
            embed = discord.Embed(
                title="📋 Current Subscriptions",
                description="\n".join(f"• `{k}`" for k in sorted(keywords)),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"{len(keywords)} keyword(s) active")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                "No subscriptions yet. Use `/subscribe <keywords>` to get started."
            )

    @app_commands.command(name="digest", description="Trigger paper digest now (admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def force_digest(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.followup.send("📡 Fetching papers from arXiv...")

        try:
            count = await self.bot.digest_manager.run_digest_for_channel(interaction.channel)
            if count > 0:
                await interaction.channel.send(f"✅ Digest complete — posted **{count}** paper(s).")
            else:
                await interaction.channel.send("No new matching papers found.")
        except Exception as e:
            logger.error(f"Error running manual digest: {e}", exc_info=True)
            await interaction.channel.send(f"❌ Error: {str(e)[:200]}")

    @app_commands.command(name="top", description="Show highest-voted papers")
    @app_commands.describe(days="Number of days to look back (default: 7)")
    async def top_papers(self, interaction: discord.Interaction, days: Optional[int] = 7):
        await interaction.response.defer()

        top = await self.db.get_top_papers(interaction.guild_id, interaction.channel_id, days=days)

        if not top:
            await interaction.followup.send(f"No voted papers found in the last {days} days.")
            return

        embed = discord.Embed(
            title=f"🏆 Top Papers — Last {days} Days",
            color=discord.Color.gold()
        )

        for i, paper in enumerate(top, 1):
            score = paper['upvotes'] - paper['downvotes']
            embed.add_field(
                name=f"{i}. {paper['title'][:80]}{'...' if len(paper['title']) > 80 else ''}",
                value=f"👍 {paper['upvotes']} 👎 {paper['downvotes']} (net {score:+d}) — [arXiv]({paper['url']})",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="search", description="Search arXiv for papers")
    @app_commands.describe(query="Search query", count="Number of results (1-10, default 5)")
    async def search(self, interaction: discord.Interaction, query: str, count: Optional[int] = 5):
        await interaction.response.defer()

        count = max(1, min(count or 5, 10))
        papers = await self.bot.fetcher.search_papers(query, max_results=count)

        if not papers:
            await interaction.followup.send(f"No papers found for: **{query}**")
            return

        embed = discord.Embed(
            title=f"🔍 arXiv Search: {query}",
            description=f"Top {len(papers)} result(s)",
            color=discord.Color.green()
        )

        for paper in papers:
            authors = ", ".join(paper.get('authors', [])[:3])
            if len(paper.get('authors', [])) > 3:
                authors += f" +{len(paper['authors']) - 3} more"
            embed.add_field(
                name=paper['title'][:100],
                value=f"*{authors}*\n{paper.get('abstract', '')[:150]}...\n[arXiv]({paper['url']}) | [PDF]({paper.get('pdf_url', '')})",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="stats", description="Show bot statistics for this channel")
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer()

        s = await self.db.get_stats(interaction.guild_id, interaction.channel_id)

        embed = discord.Embed(
            title="📊 ArxivScribe Stats",
            color=discord.Color.purple()
        )
        embed.add_field(name="Active Subscriptions", value=str(s['subscriptions']), inline=True)
        embed.add_field(name="Papers Posted", value=str(s['papers_posted']), inline=True)
        embed.add_field(name="Total Votes", value=str(s['total_votes']), inline=True)
        embed.set_footer(text=f"Channel: #{interaction.channel.name}")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="help", description="Show ArxivScribe help")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📚 ArxivScribe — Help",
            description="Your daily arXiv paper digest bot with AI summaries.",
            color=discord.Color.blue()
        )

        commands_text = (
            "`/subscribe <keywords>` — Subscribe to paper topics\n"
            "`/unsubscribe <keywords>` — Remove subscriptions\n"
            "`/subscriptions` — View active subscriptions\n"
            "`/search <query>` — Search arXiv directly\n"
            "`/digest` — Force a digest now (admin)\n"
            "`/top [days]` — Show highest-voted papers\n"
            "`/stats` — Channel statistics\n"
            "`/ping` — Check bot latency\n"
            "`/help` — This message"
        )
        embed.add_field(name="Commands", value=commands_text, inline=False)

        embed.add_field(
            name="How it works",
            value=(
                "1. Subscribe to keywords with `/subscribe`\n"
                "2. Each day, ArxivScribe fetches new arXiv papers\n"
                "3. Papers matching your keywords get AI-summarized and posted\n"
                "4. Vote with 👍 🤔 👎 to surface the best papers\n"
                "5. Use `/top` to see community favorites"
            ),
            inline=False
        )

        embed.set_footer(text="github.com/Abelo9996/ArxivScribe")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Check if bot is responsive")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! {latency}ms", ephemeral=True)

    @force_digest.error
    async def force_digest_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "❌ Admin permissions required.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Setup function for loading this cog."""
    await bot.add_cog(ArxivCommands(bot, bot.db))
