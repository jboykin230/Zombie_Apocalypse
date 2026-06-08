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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                name       TEXT NOT NULL,
                location   TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS queries (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                location   TEXT,
                question   TEXT NOT NULL,
                answer     TEXT NOT NULL
            )
            """
        )


def reset_db():
    """Drop every table and recreate them empty — a fresh store each launch."""
    with _lock, _connect() as conn:
        for table in ("events", "users", "queries"):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
    init_db()  # outside the lock above — threading.Lock is not reentrant


# ---------------------------------------------------------------- events

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


def recent_events(limit=50):
    with _lock, _connect() as conn:
        cur = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]


def latest_batch():
    """Return (batch_id, [events]) for the most recently inserted batch.

    A batch shares one created_at timestamp, so batch_id == that timestamp.
    Returns (None, []) when no events exist yet.
    """
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT created_at FROM events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None, []
        batch_id = row["created_at"]
        cur = conn.execute(
            "SELECT * FROM events WHERE created_at = ? ORDER BY id DESC", (batch_id,)
        )
        return batch_id, [dict(r) for r in cur.fetchall()]


def count_events():
    with _lock, _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]


# ---------------------------------------------------------------- users

def add_user(name, location, created_at):
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (created_at, name, location) VALUES (?, ?, ?)",
            (created_at, name, location),
        )
        return cur.lastrowid


def log_query(location, question, answer, created_at):
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO queries (created_at, location, question, answer) "
            "VALUES (?, ?, ?, ?)",
            (created_at, location, question, answer),
        )
