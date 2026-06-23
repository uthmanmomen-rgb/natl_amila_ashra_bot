from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "poll_data.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS polls (
                poll_date TEXT PRIMARY KEY,
                telegram_poll_id TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS votes (
                poll_date TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                option_index INTEGER NOT NULL,
                option_text TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (poll_date, user_id)
            );
            """
        )


def save_poll(
    poll_date: date,
    telegram_poll_id: str,
    message_id: int,
    chat_id: int,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO polls
            (poll_date, telegram_poll_id, message_id, chat_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                poll_date.isoformat(),
                telegram_poll_id,
                message_id,
                chat_id,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def get_poll_by_telegram_id(telegram_poll_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM polls WHERE telegram_poll_id = ?",
            (telegram_poll_id,),
        ).fetchone()
    return row


def save_vote(
    poll_date: date,
    user_id: int,
    user_name: str,
    option_index: int,
    option_text: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO votes
            (poll_date, user_id, user_name, option_index, option_text, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(poll_date, user_id) DO UPDATE SET
                user_name = excluded.user_name,
                option_index = excluded.option_index,
                option_text = excluded.option_text,
                updated_at = excluded.updated_at
            """,
            (
                poll_date.isoformat(),
                user_id,
                user_name,
                option_index,
                option_text,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def poll_exists(poll_date: date) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM polls WHERE poll_date = ?",
            (poll_date.isoformat(),),
        ).fetchone()
    return row is not None


def get_month_votes(year: int, month: int) -> dict[date, list[sqlite3.Row]]:
    prefix = f"{year:04d}-{month:02d}-"
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT poll_date, user_id, user_name, option_index, option_text
            FROM votes
            WHERE poll_date LIKE ?
            ORDER BY poll_date, user_name COLLATE NOCASE
            """,
            (f"{prefix}%",),
        ).fetchall()

    grouped: dict[date, list[sqlite3.Row]] = {}
    for row in rows:
        day = date.fromisoformat(row["poll_date"])
        grouped.setdefault(day, []).append(row)
    return grouped
