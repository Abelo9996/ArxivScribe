"""SQLite database manager for ArxivScribe — async via aiosqlite."""
import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Async SQLite database for subscriptions, papers, votes, and guild settings."""

    def __init__(self, db_path: str = "arxivscribe.db"):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
        return self._conn

    async def initialize(self):
        """Create tables if they don't exist."""
        conn = await self._get_conn()
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, channel_id, keyword)
            );

            CREATE TABLE IF NOT EXISTS papers (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                abstract TEXT,
                authors TEXT,
                published TEXT,
                categories TEXT,
                url TEXT,
                pdf_url TEXT,
                summary TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS posted_papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paper_id) REFERENCES papers(id),
                UNIQUE(paper_id, guild_id, channel_id)
            );

            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                vote_type TEXT NOT NULL CHECK(vote_type IN ('upvote', 'downvote', 'maybe')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paper_id) REFERENCES papers(id),
                UNIQUE(paper_id, user_id, vote_type)
            );

            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                categories TEXT,
                digest_channel_id INTEGER,
                digest_hour INTEGER DEFAULT 9,
                digest_minute INTEGER DEFAULT 0,
                timezone TEXT DEFAULT 'UTC',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_subscriptions_guild_channel
                ON subscriptions(guild_id, channel_id);
            CREATE INDEX IF NOT EXISTS idx_posted_papers_lookup
                ON posted_papers(paper_id, guild_id, channel_id);
            CREATE INDEX IF NOT EXISTS idx_votes_paper
                ON votes(paper_id);
            CREATE INDEX IF NOT EXISTS idx_papers_fetched
                ON papers(fetched_at);
        """)
        await conn.commit()
        logger.info("Database initialized successfully")

    # --- Subscriptions ---

    async def add_subscription(self, guild_id: int, channel_id: int, keyword: str) -> bool:
        conn = await self._get_conn()
        try:
            await conn.execute(
                "INSERT INTO subscriptions (guild_id, channel_id, keyword) VALUES (?, ?, ?)",
                (guild_id, channel_id, keyword.lower())
            )
            await conn.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def remove_subscription(self, guild_id: int, channel_id: int, keyword: str) -> bool:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "DELETE FROM subscriptions WHERE guild_id = ? AND channel_id = ? AND keyword = ?",
            (guild_id, channel_id, keyword.lower())
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def get_channel_subscriptions(self, guild_id: int, channel_id: int) -> List[str]:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT keyword FROM subscriptions WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id)
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def get_all_subscribed_channels(self) -> List[Tuple[int, int]]:
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT DISTINCT guild_id, channel_id FROM subscriptions")
        rows = await cursor.fetchall()
        return [(row[0], row[1]) for row in rows]

    # --- Papers ---

    async def store_paper(self, paper: dict, guild_id: int, channel_id: int, message_id: int):
        conn = await self._get_conn()
        await conn.execute("""
            INSERT OR REPLACE INTO papers
            (id, title, abstract, authors, published, categories, url, pdf_url, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            paper['id'], paper['title'], paper.get('abstract', ''),
            ','.join(paper.get('authors', [])), paper.get('published', ''),
            ','.join(paper.get('categories', [])), paper['url'],
            paper.get('pdf_url', ''), paper.get('summary', '')
        ))
        await conn.execute("""
            INSERT OR REPLACE INTO posted_papers
            (paper_id, guild_id, channel_id, message_id)
            VALUES (?, ?, ?, ?)
        """, (paper['id'], guild_id, channel_id, message_id))
        await conn.commit()

    async def is_paper_posted(self, paper_id: str, guild_id: int, channel_id: int) -> bool:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT 1 FROM posted_papers WHERE paper_id = ? AND guild_id = ? AND channel_id = ?",
            (paper_id, guild_id, channel_id)
        )
        return await cursor.fetchone() is not None

    async def get_paper_by_message(self, guild_id: int, channel_id: int, message_id: int) -> Optional[str]:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT paper_id FROM posted_papers WHERE guild_id = ? AND channel_id = ? AND message_id = ?",
            (guild_id, channel_id, message_id)
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    # --- Votes ---

    async def add_vote(self, paper_id: str, user_id: int, guild_id: int, channel_id: int, vote_type: str):
        conn = await self._get_conn()
        await conn.execute("""
            INSERT OR REPLACE INTO votes
            (paper_id, user_id, guild_id, channel_id, vote_type)
            VALUES (?, ?, ?, ?, ?)
        """, (paper_id, user_id, guild_id, channel_id, vote_type))
        await conn.commit()

    async def remove_vote(self, paper_id: str, user_id: int, vote_type: str):
        conn = await self._get_conn()
        await conn.execute(
            "DELETE FROM votes WHERE paper_id = ? AND user_id = ? AND vote_type = ?",
            (paper_id, user_id, vote_type)
        )
        await conn.commit()

    async def get_vote_summary(self, paper_id: str) -> dict:
        conn = await self._get_conn()
        cursor = await conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN vote_type = 'upvote' THEN 1 ELSE 0 END), 0) as upvotes,
                COALESCE(SUM(CASE WHEN vote_type = 'downvote' THEN 1 ELSE 0 END), 0) as downvotes,
                COALESCE(SUM(CASE WHEN vote_type = 'maybe' THEN 1 ELSE 0 END), 0) as maybe
            FROM votes WHERE paper_id = ?
        """, (paper_id,))
        row = await cursor.fetchone()
        return {'upvotes': row[0], 'downvotes': row[1], 'maybe': row[2]}

    async def get_top_papers(self, guild_id: int, channel_id: int, days: int = 7) -> List[dict]:
        conn = await self._get_conn()
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cursor = await conn.execute("""
            SELECT
                p.id, p.title, p.url,
                COALESCE(SUM(CASE WHEN v.vote_type = 'upvote' THEN 1 ELSE 0 END), 0) as upvotes,
                COALESCE(SUM(CASE WHEN v.vote_type = 'downvote' THEN 1 ELSE 0 END), 0) as downvotes
            FROM papers p
            JOIN posted_papers pp ON p.id = pp.paper_id
            LEFT JOIN votes v ON p.id = v.paper_id
            WHERE pp.guild_id = ? AND pp.channel_id = ? AND pp.posted_at >= ?
            GROUP BY p.id
            HAVING upvotes > 0
            ORDER BY (upvotes - downvotes) DESC
            LIMIT 10
        """, (guild_id, channel_id, since))
        rows = await cursor.fetchall()
        return [{'id': r[0], 'title': r[1], 'url': r[2], 'upvotes': r[3], 'downvotes': r[4]} for r in rows]

    # --- Metadata ---

    async def get_last_fetch_time(self) -> Optional[datetime]:
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT value FROM metadata WHERE key = 'last_fetch_time'")
        row = await cursor.fetchone()
        if row:
            try:
                return datetime.fromisoformat(row[0])
            except ValueError:
                pass
        return datetime.utcnow() - timedelta(days=1)

    async def update_last_fetch_time(self):
        conn = await self._get_conn()
        now = datetime.utcnow().isoformat()
        await conn.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES ('last_fetch_time', ?, CURRENT_TIMESTAMP)
        """, (now,))
        await conn.commit()

    # --- Guild Settings ---

    async def get_guild_settings(self, guild_id: int) -> Optional[dict]:
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
        if row:
            return {
                'guild_id': row[0], 'categories': row[1],
                'digest_channel_id': row[2], 'digest_hour': row[3],
                'digest_minute': row[4], 'timezone': row[5]
            }
        return None

    async def set_guild_categories(self, guild_id: int, categories: List[str]):
        conn = await self._get_conn()
        cats = ','.join(categories)
        await conn.execute("""
            INSERT INTO guild_settings (guild_id, categories) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET categories = ?, updated_at = CURRENT_TIMESTAMP
        """, (guild_id, cats, cats))
        await conn.commit()

    # --- Stats ---

    async def get_stats(self, guild_id: int, channel_id: int) -> dict:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id)
        )
        sub_count = (await cursor.fetchone())[0]

        cursor = await conn.execute(
            "SELECT COUNT(*) FROM posted_papers WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id)
        )
        paper_count = (await cursor.fetchone())[0]

        cursor = await conn.execute(
            "SELECT COUNT(*) FROM votes v JOIN posted_papers pp ON v.paper_id = pp.paper_id WHERE pp.guild_id = ? AND pp.channel_id = ?",
            (guild_id, channel_id)
        )
        vote_count = (await cursor.fetchone())[0]

        return {'subscriptions': sub_count, 'papers_posted': paper_count, 'total_votes': vote_count}

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None
