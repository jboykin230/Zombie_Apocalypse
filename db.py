import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).parent / "zombie_events.db"
MAX_ENTRIES = 1000
_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock, _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                city       TEXT NOT NULL,
                state      TEXT NOT NULL,
                severity   TEXT NOT NULL,
                headline   TEXT NOT NULL,
                detail     TEXT NOT NULL
            )
            """
        )


def insert_events(events, created_at):
    rows = [
        (created_at, e["city"], e["state"], e["severity"], e["headline"], e["detail"])
        for e in events
    ]
    with _lock, _connect() as conn:
        conn.executemany(
            "INSERT INTO events (created_at, city, state, severity, headline, detail) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        # Hard cap at 1000 entries — evict the oldest rows (FIFO).
        conn.execute(
            "DELETE FROM events WHERE id NOT IN "
            "(SELECT id FROM events ORDER BY id DESC LIMIT ?)",
            (MAX_ENTRIES,),
        )


def recent_events(limit=60):
    with _lock, _connect() as conn:
        cur = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]


def count_events():
    with _lock, _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
