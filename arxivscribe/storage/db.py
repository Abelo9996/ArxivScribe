"""SQLite database manager for ArxivScribe — async via aiosqlite."""
import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Async SQLite database for subscriptions, papers, and votes."""

    def __init__(self, db_path: str = "arxivscribe.db"):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
        return self._conn

    async def initialize(self):
        conn = await self._get_conn()
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL DEFAULT 0,
                channel_id INTEGER NOT NULL DEFAULT 0,
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
                primary_category TEXT,
                url TEXT,
                pdf_url TEXT,
                summary TEXT,
                matched_keywords TEXT,
                score INTEGER DEFAULT 0,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_papers_fetched ON papers(fetched_at DESC);
            CREATE INDEX IF NOT EXISTS idx_papers_score ON papers(score DESC);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_kw ON subscriptions(keyword);
        """)
        await conn.commit()
        logger.info("Database initialized")

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
        return [row[0] for row in await cursor.fetchall()]

    async def get_all_subscriptions(self) -> List[str]:
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT DISTINCT keyword FROM subscriptions ORDER BY keyword")
        return [row[0] for row in await cursor.fetchall()]

    async def get_all_subscribed_channels(self) -> List[Tuple[int, int]]:
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT DISTINCT guild_id, channel_id FROM subscriptions")
        return [(row[0], row[1]) for row in await cursor.fetchall()]

    # --- Papers (local web) ---

    async def store_paper_local(self, paper: dict):
        conn = await self._get_conn()
        await conn.execute("""
            INSERT OR IGNORE INTO papers
            (id, title, abstract, authors, published, categories, primary_category, url, pdf_url, summary, matched_keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            paper['id'], paper['title'], paper.get('abstract', ''),
            ','.join(paper.get('authors', [])), paper.get('published', ''),
            ','.join(paper.get('categories', [])), paper.get('primary_category', ''),
            paper.get('url', ''), paper.get('pdf_url', ''),
            paper.get('summary', ''), paper.get('matched_keywords', '')
        ))
        await conn.commit()

    async def is_paper_stored(self, paper_id: str) -> bool:
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT 1 FROM papers WHERE id = ?", (paper_id,))
        return await cursor.fetchone() is not None

    async def get_recent_papers(
        self, limit: int = 50, offset: int = 0,
        keyword: Optional[str] = None, sort: str = "date"
    ) -> List[dict]:
        conn = await self._get_conn()
        query = "SELECT * FROM papers"
        params = []

        if keyword:
            query += " WHERE (title LIKE ? OR abstract LIKE ? OR matched_keywords LIKE ?)"
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])

        sort_map = {"date": "fetched_at DESC", "votes": "score DESC", "title": "title ASC"}
        query += f" ORDER BY {sort_map.get(sort, 'fetched_at DESC')}"
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [self._paper_from_row(row) for row in rows]

    async def count_papers(self, keyword: Optional[str] = None) -> int:
        conn = await self._get_conn()
        if keyword:
            kw = f"%{keyword}%"
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM papers WHERE title LIKE ? OR abstract LIKE ? OR matched_keywords LIKE ?",
                (kw, kw, kw)
            )
        else:
            cursor = await conn.execute("SELECT COUNT(*) FROM papers")
        return (await cursor.fetchone())[0]

    async def vote_paper(self, paper_id: str, delta: int):
        conn = await self._get_conn()
        await conn.execute("UPDATE papers SET score = score + ? WHERE id = ?", (delta, paper_id))
        await conn.commit()

    async def get_paper_score(self, paper_id: str) -> int:
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT score FROM papers WHERE id = ?", (paper_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

    def _paper_from_row(self, row) -> dict:
        return {
            'id': row[0], 'title': row[1], 'abstract': row[2],
            'authors': row[3].split(',') if row[3] else [],
            'published': row[4], 'categories': row[5].split(',') if row[5] else [],
            'primary_category': row[6], 'url': row[7], 'pdf_url': row[8],
            'summary': row[9], 'matched_keywords': row[10].split(',') if row[10] else [],
            'score': row[11], 'fetched_at': row[12]
        }

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
        await conn.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES ('last_fetch_time', ?, CURRENT_TIMESTAMP)
        """, (datetime.utcnow().isoformat(),))
        await conn.commit()

    # --- Stats ---

    async def get_global_stats(self) -> dict:
        conn = await self._get_conn()
        papers = (await (await conn.execute("SELECT COUNT(*) FROM papers")).fetchone())[0]
        subs = (await (await conn.execute("SELECT COUNT(DISTINCT keyword) FROM subscriptions")).fetchone())[0]
        votes = (await (await conn.execute("SELECT COALESCE(SUM(ABS(score)), 0) FROM papers")).fetchone())[0]
        last = await self.get_last_fetch_time()
        return {
            'total_papers': papers, 'total_subscriptions': subs,
            'total_votes': votes, 'last_fetch': last.isoformat() if last else None
        }

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None
