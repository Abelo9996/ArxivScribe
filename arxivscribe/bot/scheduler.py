"""Scheduler for automated paper digest posting."""
import asyncio
import logging
from datetime import datetime, time
from typing import Optional
import discord
from discord.ext import commands, tasks

from arxivscribe.bot.digest_manager import DigestManager

logger = logging.getLogger(__name__)


class Scheduler:
    """Handles scheduled digest posting."""

    def __init__(self, bot: commands.Bot, digest_manager: DigestManager, schedule_time: time):
        """
        Initialize the scheduler.
        
        Args:
            bot: Discord bot instance
            digest_manager: DigestManager instance
            schedule_time: Time of day to run digest (datetime.time object)
        """
        self.bot = bot
        self.digest_manager = digest_manager
        self.schedule_time = schedule_time
        self._task: Optional[tasks.Loop] = None

    def start(self):
        """Start the scheduled digest task."""
        if self._task is None or not self._task.is_running():
            self._task = self._create_task()
            self._task.start()
            logger.info(f"Scheduler started. Daily digest at {self.schedule_time}")

    def stop(self):
        """Stop the scheduled digest task."""
        if self._task and self._task.is_running():
            self._task.cancel()
            logger.info("Scheduler stopped.")

    def _create_task(self):
        """Create the scheduled task loop."""
        
        @tasks.loop(hours=24)
        async def daily_digest():
            """Run the daily digest for all channels."""
            logger.info("Running scheduled digest...")
            
            try:
                total_posted = await self.digest_manager.run_digest_for_all_channels()
                logger.info(f"Scheduled digest complete. Posted {total_posted} papers total.")
            except Exception as e:
                logger.error(f"Error in scheduled digest: {e}", exc_info=True)

        @daily_digest.before_loop
        async def before_daily_digest():
            """Wait until the scheduled time before starting the loop."""
            await self.bot.wait_until_ready()
            
            # Calculate time until next scheduled run
            now = datetime.now()
            target = datetime.combine(now.date(), self.schedule_time)
            
            # If we've passed today's scheduled time, schedule for tomorrow
            if now.time() >= self.schedule_time:
                target = datetime.combine(
                    now.date(),
                    self.schedule_time
                )
                target = target.replace(day=target.day + 1)
            
            seconds_until_target = (target - now).total_seconds()
            logger.info(f"Waiting {seconds_until_target / 3600:.2f} hours until next digest at {target}")
            
            await asyncio.sleep(seconds_until_target)

        return daily_digest

    def reschedule(self, new_time: time):
        """
        Reschedule the digest to a new time.
        
        Args:
            new_time: New time of day to run digest
        """
        self.stop()
        self.schedule_time = new_time
        self.start()
        logger.info(f"Rescheduled digest to {new_time}")
