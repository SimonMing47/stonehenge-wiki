from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .indexer import WikiIndex
from .models import CommentRecord, DocumentRecord


class SQLiteStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.database_path)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _init_schema(self) -> None:
        with self.connect() as con:
            con.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS files (
                  rel_path TEXT PRIMARY KEY,
                  suffix TEXT NOT NULL,
                  name TEXT NOT NULL,
                  tags_json TEXT NOT NULL,
                  text_preview TEXT NOT NULL,
                  comment_count INTEGER NOT NULL,
                  indexed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS comments (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  source_path TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  raw_text TEXT NOT NULL,
                  todo TEXT,
                  assignee TEXT,
                  end_date TEXT,
                  line INTEGER,
                  author TEXT,
                  structured INTEGER NOT NULL,
                  indexed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_comments_source ON comments(source_path);
                CREATE INDEX IF NOT EXISTS idx_comments_assignee ON comments(assignee);
                CREATE INDEX IF NOT EXISTS idx_comments_end_date ON comments(end_date);
                CREATE TABLE IF NOT EXISTS audit_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT NOT NULL,
                  request_id TEXT NOT NULL,
                  event_type TEXT NOT NULL,
                  subject TEXT NOT NULL,
                  status TEXT NOT NULL,
                  blocked INTEGER NOT NULL,
                  payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_events(created_at);
                CREATE TABLE IF NOT EXISTS job_runs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT NOT NULL,
                  job_type TEXT NOT NULL,
                  status TEXT NOT NULL,
                  input_json TEXT NOT NULL,
                  output_json TEXT NOT NULL
                );
                """
            )

    def save_index(self, index: WikiIndex) -> None:
        now = utc_now()
        with self.connect() as con:
            con.execute("DELETE FROM comments")
            con.execute("DELETE FROM files")
            con.executemany(
                """
                INSERT INTO files(rel_path, suffix, name, tags_json, text_preview, comment_count, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [self._file_row(record, now) for record in index.records],
            )
            con.executemany(
                """
                INSERT INTO comments(source_path, kind, raw_text, todo, assignee, end_date, line, author, structured, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [self._comment_row(comment, now) for comment in index.comments],
            )

    def record_audit(
        self,
        event_type: str,
        request_id: str,
        subject: str,
        status: str,
        blocked: bool = False,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO audit_events(created_at, request_id, event_type, subject, status, blocked, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now(),
                    request_id,
                    event_type,
                    subject,
                    status,
                    1 if blocked else 0,
                    json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
                ),
            )

    def record_job(self, job_type: str, status: str, input_data: Any, output_data: Any) -> None:
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO job_runs(created_at, job_type, status, input_json, output_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    utc_now(),
                    job_type,
                    status,
                    json.dumps(input_data, ensure_ascii=False),
                    json.dumps(output_data, ensure_ascii=False),
                ),
            )

    def list_audit_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT id, created_at, request_id, event_type, subject, status, blocked, payload_json
                FROM audit_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            event = dict(row)
            payload_json = event.pop("payload_json")
            event["blocked"] = bool(row["blocked"])
            event["payload"] = json.loads(payload_json)
            events.append(event)
        return events

    def stats(self) -> dict[str, Any]:
        with self.connect() as con:
            file_count = con.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            comment_count = con.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
            audit_count = con.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        return {"files": file_count, "comments": comment_count, "audit_events": audit_count}

    def _file_row(self, record: DocumentRecord, indexed_at: str) -> tuple[Any, ...]:
        preview = "\n".join(record.text.splitlines()[:30])[:4000]
        return (
            record.rel_path,
            record.suffix,
            record.name,
            json.dumps(sorted(record.tags), ensure_ascii=False),
            preview,
            len(record.comments),
            indexed_at,
        )

    def _comment_row(self, comment: CommentRecord, indexed_at: str) -> tuple[Any, ...]:
        return (
            comment.source_path,
            comment.kind,
            comment.raw_text,
            comment.todo,
            comment.assignee,
            comment.end_date,
            comment.line,
            comment.author,
            1 if comment.structured else 0,
            indexed_at,
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
