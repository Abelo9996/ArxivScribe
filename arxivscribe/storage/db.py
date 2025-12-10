"""SQLite database manager for ArxivScribe."""
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import threading

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database for subscriptions, papers, and votes."""

    def __init__(self, db_path: str = "arxivscribe.db"):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.local = threading.local()
        self._initialize_db()

    def _get_connection(self):
        """Get thread-local database connection."""
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.local.conn.row_factory = sqlite3.Row
        return self.local.conn

    def _initialize_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Subscriptions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, channel_id, keyword)
            )
        """)
        
        # Papers table
        cursor.execute("""
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
            )
        """)
        
        # Posted papers table (tracks which papers were posted where)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posted_papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paper_id) REFERENCES papers(id),
                UNIQUE(paper_id, guild_id, channel_id)
            )
        """)
        
        # Votes table
        cursor.execute("""
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
            )
        """)
        
        # Metadata table (for tracking last fetch time, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        logger.info("Database initialized successfully")

    # Subscription methods
    
    def add_subscription(self, guild_id: int, channel_id: int, keyword: str) -> bool:
        """Add a keyword subscription for a channel."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO subscriptions (guild_id, channel_id, keyword) VALUES (?, ?, ?)",
                (guild_id, channel_id, keyword.lower())
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_subscription(self, guild_id: int, channel_id: int, keyword: str) -> bool:
        """Remove a keyword subscription."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM subscriptions WHERE guild_id = ? AND channel_id = ? AND keyword = ?",
            (guild_id, channel_id, keyword.lower())
        )
        conn.commit()
        return cursor.rowcount > 0

    def get_channel_subscriptions(self, guild_id: int, channel_id: int) -> List[str]:
        """Get all keyword subscriptions for a channel."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT keyword FROM subscriptions WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id)
        )
        
        return [row['keyword'] for row in cursor.fetchall()]

    def get_all_subscribed_channels(self) -> List[Tuple[int, int]]:
        """Get all unique (guild_id, channel_id) pairs with subscriptions."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT guild_id, channel_id FROM subscriptions")
        
        return [(row['guild_id'], row['channel_id']) for row in cursor.fetchall()]

    # Paper methods
    
    def store_paper(self, paper: dict, guild_id: int, channel_id: int, message_id: int):
        """Store a paper and record where it was posted."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Store paper
        cursor.execute("""
            INSERT OR REPLACE INTO papers 
            (id, title, abstract, authors, published, categories, url, pdf_url, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            paper['id'],
            paper['title'],
            paper.get('abstract', ''),
            ','.join(paper.get('authors', [])),
            paper.get('published', ''),
            ','.join(paper.get('categories', [])),
            paper['url'],
            paper.get('pdf_url', ''),
            paper.get('summary', '')
        ))
        
        # Record posting
        cursor.execute("""
            INSERT OR REPLACE INTO posted_papers 
            (paper_id, guild_id, channel_id, message_id)
            VALUES (?, ?, ?, ?)
        """, (paper['id'], guild_id, channel_id, message_id))
        
        conn.commit()

    def is_paper_posted(self, paper_id: str, guild_id: int, channel_id: int) -> bool:
        """Check if a paper has already been posted to a channel."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT 1 FROM posted_papers WHERE paper_id = ? AND guild_id = ? AND channel_id = ?",
            (paper_id, guild_id, channel_id)
        )
        
        return cursor.fetchone() is not None

    def get_paper_by_message(self, guild_id: int, channel_id: int, message_id: int) -> Optional[str]:
        """Get paper ID by message ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT paper_id FROM posted_papers WHERE guild_id = ? AND channel_id = ? AND message_id = ?",
            (guild_id, channel_id, message_id)
        )
        
        row = cursor.fetchone()
        return row['paper_id'] if row else None

    # Vote methods
    
    def add_vote(self, paper_id: str, user_id: int, guild_id: int, channel_id: int, vote_type: str):
        """Add or update a vote."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO votes 
            (paper_id, user_id, guild_id, channel_id, vote_type)
            VALUES (?, ?, ?, ?, ?)
        """, (paper_id, user_id, guild_id, channel_id, vote_type))
        
        conn.commit()

    def remove_vote(self, paper_id: str, user_id: int, vote_type: str):
        """Remove a vote."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM votes WHERE paper_id = ? AND user_id = ? AND vote_type = ?",
            (paper_id, user_id, vote_type)
        )
        
        conn.commit()

    def get_vote_summary(self, paper_id: str) -> dict:
        """Get vote counts for a paper."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN vote_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
                SUM(CASE WHEN vote_type = 'downvote' THEN 1 ELSE 0 END) as downvotes,
                SUM(CASE WHEN vote_type = 'maybe' THEN 1 ELSE 0 END) as maybe
            FROM votes
            WHERE paper_id = ?
        """, (paper_id,))
        
        row = cursor.fetchone()
        return {
            'upvotes': row['upvotes'] or 0,
            'downvotes': row['downvotes'] or 0,
            'maybe': row['maybe'] or 0
        }

    def get_top_papers(self, guild_id: int, channel_id: int, days: int = 7) -> List[dict]:
        """Get top-voted papers from recent days."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(days=days)
        
        cursor.execute("""
            SELECT 
                p.id,
                p.title,
                p.url,
                SUM(CASE WHEN v.vote_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
                SUM(CASE WHEN v.vote_type = 'downvote' THEN 1 ELSE 0 END) as downvotes
            FROM papers p
            JOIN posted_papers pp ON p.id = pp.paper_id
            LEFT JOIN votes v ON p.id = v.paper_id
            WHERE pp.guild_id = ? AND pp.channel_id = ?
                AND pp.posted_at >= ?
            GROUP BY p.id
            HAVING upvotes > 0
            ORDER BY (upvotes - downvotes) DESC
            LIMIT 10
        """, (guild_id, channel_id, since))
        
        return [dict(row) for row in cursor.fetchall()]

    # Metadata methods
    
    def get_last_fetch_time(self) -> Optional[datetime]:
        """Get the last time papers were fetched."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM metadata WHERE key = 'last_fetch_time'")
        row = cursor.fetchone()
        
        if row:
            try:
                return datetime.fromisoformat(row['value'])
            except ValueError:
                pass
        
        # Default to 24 hours ago
        return datetime.now() - timedelta(days=1)

    def update_last_fetch_time(self):
        """Update the last fetch time to now."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES ('last_fetch_time', ?, CURRENT_TIMESTAMP)
        """, (now,))
        
        conn.commit()

    def close(self):
        """Close database connection."""
        if hasattr(self.local, 'conn'):
            self.local.conn.close()
