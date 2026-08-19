"""
SQLite database setup and query helpers.

Provides persistence for meeting transcripts, summaries, decisions,
and action items using Python's standard library sqlite3.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Generator

from .models import MeetingDetailResponse, MeetingListItemResponse, ActionItem

# Default database file path in workspace root (ignored by .gitignore)
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "meetings.db")))


@contextmanager
def get_db_cursor(db_path: Optional[Path | str] = None) -> Generator[sqlite3.Cursor, None, None]:
    """
    Context manager that yields a cursor and safely commits/closes the connection.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Optional[Path | str] = None) -> None:
    """
    Initialize SQLite database and create required tables if they do not exist.
    """
    with get_db_cursor(db_path) as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS meetings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                filename     TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                transcript   TEXT NOT NULL,
                summary      TEXT NOT NULL,
                decisions    TEXT NOT NULL,
                action_items TEXT NOT NULL
            );
            """
        )
        # Create an index on created_at for fast reverse-chronological retrieval
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_meetings_created_at 
            ON meetings(created_at DESC);
            """
        )


def insert_meeting(
    filename: str,
    transcript: str,
    summary: str,
    decisions: list[str],
    action_items: list[dict[str, Any] | ActionItem],
    created_at: Optional[str] = None,
    db_path: Optional[Path | str] = None,
) -> MeetingDetailResponse:
    """
    Insert a processed meeting record into SQLite and return the created MeetingDetailResponse.
    """
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()

    # Convert ActionItem models to dicts if needed
    normalized_action_items: list[dict[str, str]] = []
    for item in action_items:
        if isinstance(item, ActionItem):
            normalized_action_items.append(item.model_dump())
        elif isinstance(item, dict):
            normalized_action_items.append({
                "task": item.get("task", ""),
                "owner": item.get("owner", "Not specified"),
                "deadline": item.get("deadline", "Not specified"),
            })

    decisions_json = json.dumps(decisions, ensure_ascii=False)
    action_items_json = json.dumps(normalized_action_items, ensure_ascii=False)

    with get_db_cursor(db_path) as cursor:
        cursor.execute(
            """
            INSERT INTO meetings (filename, created_at, transcript, summary, decisions, action_items)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (filename, created_at, transcript, summary, decisions_json, action_items_json),
        )
        meeting_id = cursor.lastrowid

    return MeetingDetailResponse(
        id=meeting_id,
        filename=filename,
        created_at=created_at,
        transcript=transcript,
        summary=summary,
        decisions=decisions,
        action_items=[ActionItem(**item) for item in normalized_action_items],
    )


def get_meeting_by_id(
    meeting_id: int, db_path: Optional[Path | str] = None
) -> Optional[MeetingDetailResponse]:
    """
    Retrieve a single meeting by its integer ID.
    Returns None if no matching record is found.
    """
    with get_db_cursor(db_path) as cursor:
        cursor.execute(
            """
            SELECT id, filename, created_at, transcript, summary, decisions, action_items
            FROM meetings
            WHERE id = ?;
            """,
            (meeting_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        decisions_list = json.loads(row["decisions"])
        raw_actions = json.loads(row["action_items"])
        action_items = [ActionItem(**item) for item in raw_actions]

        return MeetingDetailResponse(
            id=row["id"],
            filename=row["filename"],
            created_at=row["created_at"],
            transcript=row["transcript"],
            summary=row["summary"],
            decisions=decisions_list,
            action_items=action_items,
        )


def get_all_meetings(
    db_path: Optional[Path | str] = None,
) -> list[MeetingListItemResponse]:
    """
    Retrieve all meetings in reverse-chronological order (latest first).
    Returns a list of MeetingListItemResponse.
    """
    with get_db_cursor(db_path) as cursor:
        cursor.execute(
            """
            SELECT id, filename, created_at, summary
            FROM meetings
            ORDER BY id DESC;
            """
        )
        rows = cursor.fetchall()

        return [
            MeetingListItemResponse(
                id=row["id"],
                filename=row["filename"],
                created_at=row["created_at"],
                summary=row["summary"],
            )
            for row in rows
        ]
