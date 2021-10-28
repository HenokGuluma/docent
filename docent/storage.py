"""
Storage. One table, one file, no ORM. Docent is meant to be read end
to end in an afternoon, and SQLite's stdlib driver is plenty for a
single-user reading room.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "docent.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                tags TEXT,            -- comma-separated
                doc_type TEXT,
                raw_text TEXT,
                source TEXT,          -- 'llm:<model>' or 'local-heuristic'
                created_at TEXT NOT NULL
            )
            """
        )


def next_id() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM documents").fetchone()
        return row["next_id"]


def insert_document(doc_id, original_filename, stored_filename, raw_text, title, summary, tags, doc_type, source):
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO documents
                (id, original_filename, stored_filename, title, summary, tags, doc_type, raw_text, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id, original_filename, stored_filename, title, summary,
                ", ".join(tags), doc_type, raw_text, source,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def update_card(doc_id, card):
    with _connect() as conn:
        conn.execute(
            "UPDATE documents SET title = ?, summary = ?, tags = ?, doc_type = ?, source = ? WHERE id = ?",
            (card["title"], card["summary"], ", ".join(card["tags"]), card["doc_type"], card["source"], doc_id),
        )


def get_document(doc_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None


def list_documents(query: str = "", doc_type: str = ""):
    sql = "SELECT * FROM documents WHERE 1=1"
    params = []
    if query:
        sql += " AND (title LIKE ? OR summary LIKE ? OR tags LIKE ? OR raw_text LIKE ?)"
        like = f"%{query}%"
        params += [like, like, like, like]
    if doc_type:
        sql += " AND doc_type = ?"
        params.append(doc_type)
    sql += " ORDER BY created_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def list_doc_types():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT doc_type, COUNT(*) AS n FROM documents GROUP BY doc_type ORDER BY n DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def count_documents() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]


def delete_document(doc_id):
    with _connect() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
