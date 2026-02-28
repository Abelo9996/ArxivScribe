"""Scheduler for automated paper digest posting."""
import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional
from discord.ext import commands, tasks

from arxivscribe.bot.digest_manager import DigestManager

logger = logging.getLogger(__name__)


class Scheduler:
    """Handles scheduled digest posting using discord.ext.tasks."""

    def __init__(self, bot: commands.Bot, digest_manager: DigestManager, schedule_time: time):
        self.bot = bot
        self.digest_manager = digest_manager
        self.schedule_time = schedule_time
        self._task: Optional[tasks.Loop] = None

    def start(self):
        if self._task is None or not self._task.is_running():
            self._task = self._create_task()
            self._task.start()
            logger.info(f"Scheduler started — daily digest at {self.schedule_time}")

    def stop(self):
        if self._task and self._task.is_running():
            self._task.cancel()
            logger.info("Scheduler stopped")

    def _create_task(self):
        @tasks.loop(hours=24)
        async def daily_digest():
            logger.info("Running scheduled digest...")
            try:
                total = await self.digest_manager.run_digest_for_all_channels()
                logger.info(f"Scheduled digest complete — {total} paper(s) posted")
            except Exception as e:
                logger.error(f"Scheduled digest error: {e}", exc_info=True)

        @daily_digest.before_loop
        async def before_daily_digest():
            await self.bot.wait_until_ready()

            now = datetime.utcnow()
            target = datetime.combine(now.date(), self.schedule_time)

            if now >= target:
                # Schedule for tomorrow
                target += timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            logger.info(f"Next digest in {wait_seconds / 3600:.1f}h at {target.isoformat()}")
            await asyncio.sleep(wait_seconds)

        return daily_digest

    def reschedule(self, new_time: time):
        self.stop()
        self.schedule_time = new_time
        self.start()
        logger.info(f"Rescheduled to {new_time}")
