from __future__ import annotations

import json
import sqlite3
import hashlib
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
                CREATE TABLE IF NOT EXISTS source_registry (
                  rel_path TEXT PRIMARY KEY,
                  origin_type TEXT NOT NULL,
                  origin TEXT NOT NULL,
                  title TEXT NOT NULL,
                  category TEXT NOT NULL,
                  sha256 TEXT NOT NULL,
                  size INTEGER NOT NULL,
                  status TEXT NOT NULL,
                  imported_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  last_indexed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_source_registry_status ON source_registry(status);
                CREATE INDEX IF NOT EXISTS idx_source_registry_sha256 ON source_registry(sha256);
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
            self._sync_source_registry(con, index, now)

    def record_source_provenance(
        self,
        rel_path: str,
        origin_type: str,
        origin: str,
        title: str,
        category: str,
        sha256: str,
        size: int,
    ) -> None:
        now = utc_now()
        with self.connect() as con:
            existing = con.execute(
                "SELECT imported_at, last_indexed_at FROM source_registry WHERE rel_path = ?",
                (rel_path,),
            ).fetchone()
            con.execute(
                """
                INSERT INTO source_registry(
                    rel_path, origin_type, origin, title, category, sha256, size, status,
                    imported_at, updated_at, last_indexed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                ON CONFLICT(rel_path) DO UPDATE SET
                    origin_type = excluded.origin_type,
                    origin = excluded.origin,
                    title = excluded.title,
                    category = excluded.category,
                    sha256 = excluded.sha256,
                    size = excluded.size,
                    status = 'active',
                    updated_at = excluded.updated_at,
                    last_indexed_at = excluded.last_indexed_at
                """,
                (
                    rel_path,
                    origin_type,
                    origin,
                    title or Path(rel_path).stem,
                    category or source_category(rel_path),
                    sha256,
                    size,
                    existing["imported_at"] if existing else now,
                    now,
                    existing["last_indexed_at"] if existing else now,
                ),
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

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT id, created_at, job_type, status, input_json, output_json
                FROM job_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        jobs: list[dict[str, Any]] = []
        for row in rows:
            job = dict(row)
            job["input"] = json.loads(job.pop("input_json") or "{}")
            job["output"] = json.loads(job.pop("output_json") or "{}")
            jobs.append(job)
        return jobs

    def list_sources(self, include_missing: bool = False) -> list[dict[str, Any]]:
        where = "" if include_missing else "WHERE s.status != 'missing'"
        with self.connect() as con:
            rows = con.execute(
                f"""
                SELECT
                  s.rel_path, s.origin_type, s.origin, s.title, s.category, s.sha256,
                  s.size, s.status, s.imported_at, s.updated_at, s.last_indexed_at,
                  f.suffix, f.tags_json, f.comment_count
                FROM source_registry s
                LEFT JOIN files f ON f.rel_path = s.rel_path
                {where}
                ORDER BY s.status ASC, s.updated_at DESC, s.rel_path ASC
                """
            ).fetchall()
        sources: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            tags_json = item.pop("tags_json") or "[]"
            item["tags"] = json.loads(tags_json)
            item["comment_count"] = int(item["comment_count"] or 0)
            sources.append(item)
        return sources

    def stats(self) -> dict[str, Any]:
        with self.connect() as con:
            file_count = con.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            comment_count = con.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
            audit_count = con.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
            job_count = con.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0]
            source_count = con.execute("SELECT COUNT(*) FROM source_registry WHERE status != 'missing'").fetchone()[0]
            missing_source_count = con.execute("SELECT COUNT(*) FROM source_registry WHERE status = 'missing'").fetchone()[0]
        return {
            "files": file_count,
            "comments": comment_count,
            "audit_events": audit_count,
            "jobs": job_count,
            "sources": source_count,
            "missing_sources": missing_source_count,
        }

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

    def _sync_source_registry(self, con: sqlite3.Connection, index: WikiIndex, indexed_at: str) -> None:
        rows = con.execute("SELECT * FROM source_registry").fetchall()
        existing = {row["rel_path"]: dict(row) for row in rows}
        seen: set[str] = set()
        for record in index.records:
            seen.add(record.rel_path)
            previous = existing.get(record.rel_path, {})
            size = safe_size(record.full_path)
            sha256 = file_sha256(record.full_path) if size else ""
            imported_at = str(previous.get("imported_at") or indexed_at)
            con.execute(
                """
                INSERT INTO source_registry(
                    rel_path, origin_type, origin, title, category, sha256, size, status,
                    imported_at, updated_at, last_indexed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                ON CONFLICT(rel_path) DO UPDATE SET
                    sha256 = excluded.sha256,
                    size = excluded.size,
                    status = 'active',
                    updated_at = excluded.updated_at,
                    last_indexed_at = excluded.last_indexed_at
                """,
                (
                    record.rel_path,
                    str(previous.get("origin_type") or "local"),
                    str(previous.get("origin") or record.rel_path),
                    str(previous.get("title") or record.name),
                    str(previous.get("category") or source_category(record.rel_path)),
                    sha256,
                    size,
                    imported_at,
                    indexed_at,
                    indexed_at,
                ),
            )
        for rel_path, previous in existing.items():
            if rel_path in seen or previous.get("status") == "missing":
                continue
            con.execute(
                "UPDATE source_registry SET status = 'missing', updated_at = ? WHERE rel_path = ?",
                (indexed_at, rel_path),
            )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def source_category(rel_path: str) -> str:
    parts = rel_path.split("/")
    if len(parts) >= 3 and parts[0] == "docs":
        return parts[1]
    return "uncategorized"
