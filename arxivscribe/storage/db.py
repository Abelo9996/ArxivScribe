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

            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                collection TEXT DEFAULT 'Reading List',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paper_id) REFERENCES papers(id),
                UNIQUE(paper_id, collection)
            );

            CREATE TABLE IF NOT EXISTS digest_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('email', 'webhook')),
                target TEXT NOT NULL,
                keywords TEXT,
                categories TEXT,
                schedule TEXT DEFAULT 'daily',
                send_hour INTEGER DEFAULT 9,
                enabled INTEGER DEFAULT 1,
                last_sent TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_papers_fetched ON papers(fetched_at DESC);
            CREATE INDEX IF NOT EXISTS idx_papers_score ON papers(score DESC);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_kw ON subscriptions(keyword);
            CREATE INDEX IF NOT EXISTS idx_bookmarks_paper ON bookmarks(paper_id);
            CREATE INDEX IF NOT EXISTS idx_bookmarks_collection ON bookmarks(collection);
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
        keyword: Optional[str] = None, sort: str = "date",
        date_from: Optional[str] = None, date_to: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[dict]:
        conn = await self._get_conn()
        conditions = []
        params = []

        if keyword:
            conditions.append("(title LIKE ? OR abstract LIKE ? OR matched_keywords LIKE ?)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])

        if date_from:
            conditions.append("published >= ?")
            params.append(date_from)

        if date_to:
            conditions.append("published <= ?")
            params.append(date_to + "T23:59:59")

        if category:
            conditions.append("categories LIKE ?")
            params.append(f"%{category}%")

        query = "SELECT * FROM papers"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        sort_map = {"date": "fetched_at DESC", "votes": "score DESC", "title": "title ASC"}
        query += f" ORDER BY {sort_map.get(sort, 'fetched_at DESC')}"
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [self._paper_from_row(row) for row in rows]

    async def count_papers(
        self, keyword: Optional[str] = None,
        date_from: Optional[str] = None, date_to: Optional[str] = None,
        category: Optional[str] = None
    ) -> int:
        conn = await self._get_conn()
        conditions = []
        params = []

        if keyword:
            conditions.append("(title LIKE ? OR abstract LIKE ? OR matched_keywords LIKE ?)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        if date_from:
            conditions.append("published >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("published <= ?")
            params.append(date_to + "T23:59:59")
        if category:
            conditions.append("categories LIKE ?")
            params.append(f"%{category}%")

        query = "SELECT COUNT(*) FROM papers"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        cursor = await conn.execute(query, params)
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

    # --- Bookmarks ---

    async def add_bookmark(self, paper_id: str, collection: str = "Reading List", notes: str = "") -> bool:
        conn = await self._get_conn()
        try:
            await conn.execute(
                "INSERT INTO bookmarks (paper_id, collection, notes) VALUES (?, ?, ?)",
                (paper_id, collection, notes)
            )
            await conn.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def remove_bookmark(self, paper_id: str, collection: str = "Reading List") -> bool:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "DELETE FROM bookmarks WHERE paper_id = ? AND collection = ?",
            (paper_id, collection)
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def get_bookmarks(self, collection: str = None) -> List[dict]:
        conn = await self._get_conn()
        if collection:
            cursor = await conn.execute("""
                SELECT p.*, b.collection, b.notes, b.created_at as bookmarked_at
                FROM bookmarks b JOIN papers p ON b.paper_id = p.id
                WHERE b.collection = ? ORDER BY b.created_at DESC
            """, (collection,))
        else:
            cursor = await conn.execute("""
                SELECT p.*, b.collection, b.notes, b.created_at as bookmarked_at
                FROM bookmarks b JOIN papers p ON b.paper_id = p.id
                ORDER BY b.created_at DESC
            """)
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            paper = self._paper_from_row(row)
            paper['collection'] = row[13] if len(row) > 13 else 'Reading List'
            paper['notes'] = row[14] if len(row) > 14 else ''
            paper['bookmarked_at'] = row[15] if len(row) > 15 else ''
            results.append(paper)
        return results

    async def get_collections(self) -> List[dict]:
        conn = await self._get_conn()
        cursor = await conn.execute("""
            SELECT collection, COUNT(*) as count FROM bookmarks GROUP BY collection ORDER BY collection
        """)
        return [{'name': row[0], 'count': row[1]} for row in await cursor.fetchall()]

    async def is_bookmarked(self, paper_id: str) -> bool:
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT 1 FROM bookmarks WHERE paper_id = ?", (paper_id,))
        return await cursor.fetchone() is not None

    async def get_paper_by_id(self, paper_id: str) -> Optional[dict]:
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,))
        row = await cursor.fetchone()
        return self._paper_from_row(row) if row else None

    async def get_all_papers_for_similarity(self) -> List[dict]:
        """Get all papers with title+abstract for similarity computation."""
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT * FROM papers ORDER BY fetched_at DESC LIMIT 500")
        return [self._paper_from_row(row) for row in await cursor.fetchall()]

    # --- Digest configs ---

    async def add_digest_config(
        self, digest_type: str, target: str, keywords: str = "",
        categories: str = "", schedule: str = "daily", send_hour: int = 9
    ) -> int:
        conn = await self._get_conn()
        cursor = await conn.execute("""
            INSERT INTO digest_config (type, target, keywords, categories, schedule, send_hour)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (digest_type, target, keywords, categories, schedule, send_hour))
        await conn.commit()
        return cursor.lastrowid

    async def get_digest_configs(self, enabled_only: bool = True) -> List[dict]:
        conn = await self._get_conn()
        query = "SELECT * FROM digest_config"
        if enabled_only:
            query += " WHERE enabled = 1"
        cursor = await conn.execute(query)
        rows = await cursor.fetchall()
        return [{
            'id': r[0], 'type': r[1], 'target': r[2], 'keywords': r[3],
            'categories': r[4], 'schedule': r[5], 'send_hour': r[6],
            'enabled': bool(r[7]), 'last_sent': r[8], 'created_at': r[9]
        } for r in rows]

    async def remove_digest_config(self, digest_id: int) -> bool:
        conn = await self._get_conn()
        cursor = await conn.execute("DELETE FROM digest_config WHERE id = ?", (digest_id,))
        await conn.commit()
        return cursor.rowcount > 0

    async def toggle_digest_config(self, digest_id: int, enabled: bool) -> bool:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "UPDATE digest_config SET enabled = ? WHERE id = ?", (int(enabled), digest_id)
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def update_digest_last_sent(self, digest_id: int):
        conn = await self._get_conn()
        await conn.execute(
            "UPDATE digest_config SET last_sent = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), digest_id)
        )
        await conn.commit()

    async def get_distinct_categories(self) -> List[str]:
        """Get all distinct categories from stored papers."""
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT DISTINCT categories FROM papers WHERE categories != '' LIMIT 200")
        cats = set()
        for row in await cursor.fetchall():
            for c in (row[0] or '').split(','):
                c = c.strip()
                if c:
                    cats.add(c)
        return sorted(cats)
