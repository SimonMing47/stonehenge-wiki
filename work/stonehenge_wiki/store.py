from __future__ import annotations

import json
import sqlite3
import hashlib
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .indexer import WikiIndex
from .models import CommentRecord, DocumentRecord
from .wiki_sections import WikiSection, build_wiki_sections


class SQLiteStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.database_path, timeout=30.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=30000")
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
                CREATE TABLE IF NOT EXISTS source_versions (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  rel_path TEXT NOT NULL,
                  sha256 TEXT NOT NULL,
                  size INTEGER NOT NULL,
                  first_seen_at TEXT NOT NULL,
                  last_seen_at TEXT NOT NULL,
                  observation_count INTEGER NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_source_versions_identity ON source_versions(rel_path, sha256);
                CREATE INDEX IF NOT EXISTS idx_source_versions_rel_path ON source_versions(rel_path);
                CREATE TABLE IF NOT EXISTS source_review_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT NOT NULL,
                  rel_path TEXT NOT NULL,
                  status TEXT NOT NULL,
                  reason TEXT NOT NULL,
                  actor TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_source_review_events_rel_path ON source_review_events(rel_path);
                CREATE TABLE IF NOT EXISTS goals (
                  goal_id TEXT PRIMARY KEY,
                  source_path TEXT NOT NULL,
                  todo TEXT NOT NULL,
                  assignee TEXT,
                  end_date TEXT,
                  line INTEGER,
                  kind TEXT NOT NULL,
                  raw_text TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  state_updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_goals_source_path ON goals(source_path);
                CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
                CREATE INDEX IF NOT EXISTS idx_goals_assignee ON goals(assignee);
                CREATE INDEX IF NOT EXISTS idx_goals_end_date ON goals(end_date);
                DROP TABLE IF EXISTS document_chunks;
                CREATE TABLE IF NOT EXISTS wiki_sections (
                  section_id TEXT PRIMARY KEY,
                  page_path TEXT NOT NULL,
                  page_title TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  heading TEXT NOT NULL,
                  level INTEGER NOT NULL,
                  source_path TEXT NOT NULL,
                  body TEXT NOT NULL,
                  terms_json TEXT NOT NULL,
                  line_start INTEGER NOT NULL,
                  line_end INTEGER NOT NULL,
                  indexed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_wiki_sections_page_path ON wiki_sections(page_path);
                CREATE INDEX IF NOT EXISTS idx_wiki_sections_source_path ON wiki_sections(source_path);
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
            self._sync_goals(con, index.comments, now)
            self._sync_source_registry(con, index, now)

    def save_wiki_sections(self, compiled_root: Path) -> None:
        now = utc_now()
        sections = build_wiki_sections(compiled_root)
        with self.connect() as con:
            con.execute("DELETE FROM wiki_sections")
            con.executemany(
                """
                INSERT INTO wiki_sections(
                    section_id, page_path, page_title, kind, heading, level, source_path,
                    body, terms_json, line_start, line_end, indexed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [self._wiki_section_row(section, now) for section in sections],
            )

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

    def update_source_status(
        self,
        rel_path: str,
        status: str,
        reason: str = "",
        actor: str = "system",
    ) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as con:
            row = con.execute("SELECT * FROM source_registry WHERE rel_path = ?", (rel_path,)).fetchone()
            if row is None:
                return None
            con.execute(
                "UPDATE source_registry SET status = ?, updated_at = ? WHERE rel_path = ?",
                (status, now, rel_path),
            )
            con.execute(
                """
                INSERT INTO source_review_events(created_at, rel_path, status, reason, actor)
                VALUES (?, ?, ?, ?, ?)
                """,
                (now, rel_path, status, reason, actor),
            )
            updated = con.execute("SELECT * FROM source_registry WHERE rel_path = ?", (rel_path,)).fetchone()
        return dict(updated) if updated else None

    def list_source_reviews(self, rel_path: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        params: tuple[Any, ...]
        where = ""
        if rel_path:
            where = "WHERE rel_path = ?"
            params = (rel_path, limit)
        else:
            params = (limit,)
        with self.connect() as con:
            rows = con.execute(
                f"""
                SELECT id, created_at, rel_path, status, reason, actor
                FROM source_review_events
                {where}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

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

    def get_job(self, job_id: str | int) -> dict[str, Any] | None:
        try:
            parsed_id = int(job_id)
        except (TypeError, ValueError):
            return None
        with self.connect() as con:
            row = con.execute(
                """
                SELECT id, created_at, job_type, status, input_json, output_json
                FROM job_runs
                WHERE id = ?
                """,
                (parsed_id,),
            ).fetchone()
        if row is None:
            return None
        job = dict(row)
        job["input"] = json.loads(job.pop("input_json") or "{}")
        job["output"] = json.loads(job.pop("output_json") or "{}")
        return job

    def list_sources(self, include_missing: bool = False) -> list[dict[str, Any]]:
        where = "" if include_missing else "WHERE s.status != 'missing'"
        with self.connect() as con:
            rows = con.execute(
                f"""
                SELECT
                  s.rel_path, s.origin_type, s.origin, s.title, s.category, s.sha256,
                  s.size, s.status, s.imported_at, s.updated_at, s.last_indexed_at,
                  f.suffix, f.tags_json, f.comment_count,
                  (SELECT COUNT(*) FROM source_versions v WHERE v.rel_path = s.rel_path) AS version_count,
                  (SELECT COUNT(*) FROM wiki_sections w WHERE w.source_path = s.rel_path) AS wiki_section_count
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
            item["version_count"] = int(item["version_count"] or 0)
            item["wiki_section_count"] = int(item["wiki_section_count"] or 0)
            sources.append(item)
        return sources

    def list_wiki_sections(self, source_path: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        params: tuple[Any, ...]
        where = ""
        if source_path:
            where = "WHERE source_path = ?"
            params = (source_path, limit)
        else:
            params = (limit,)
        with self.connect() as con:
            rows = con.execute(
                f"""
                SELECT section_id, page_path, page_title, kind, heading, level, source_path,
                       body, terms_json, line_start, line_end, indexed_at
                FROM wiki_sections
                {where}
                ORDER BY page_path ASC, line_start ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [decode_wiki_section_row(row) for row in rows]

    def search_wiki_sections(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        from .indexer import query_terms

        terms = query_terms(query)
        if not terms:
            return self.list_wiki_sections(limit=limit)
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT section_id, page_path, page_title, kind, heading, level, source_path,
                       body, terms_json, line_start, line_end, indexed_at
                FROM wiki_sections
                """
            ).fetchall()
        scored: list[tuple[int, dict[str, Any]]] = []
        for row in rows:
            section = decode_wiki_section_row(row)
            score = score_wiki_section(section, terms)
            if score:
                section["score"] = score
                section["snippet"] = section_snippet(section, terms)
                scored.append((score, section))
        scored.sort(key=lambda item: (-item[0], item[1]["page_path"], item[1]["line_start"]))
        return [section for _, section in scored[:limit]]

    def list_source_versions(self, rel_path: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        params: tuple[Any, ...]
        where = ""
        if rel_path:
            where = "WHERE rel_path = ?"
            params = (rel_path, limit)
        else:
            params = (limit,)
        with self.connect() as con:
            rows = con.execute(
                f"""
                SELECT id, rel_path, sha256, size, first_seen_at, last_seen_at, observation_count
                FROM source_versions
                {where}
                ORDER BY last_seen_at DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict[str, Any]:
        with self.connect() as con:
            file_count = con.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            comment_count = con.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
            audit_count = con.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
            job_count = con.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0]
            wiki_section_count = con.execute("SELECT COUNT(*) FROM wiki_sections").fetchone()[0]
            source_count = con.execute("SELECT COUNT(*) FROM source_registry WHERE status != 'missing'").fetchone()[0]
            missing_source_count = con.execute("SELECT COUNT(*) FROM source_registry WHERE status = 'missing'").fetchone()[0]
            quarantined_source_count = con.execute("SELECT COUNT(*) FROM source_registry WHERE status = 'quarantined'").fetchone()[0]
            source_version_count = con.execute("SELECT COUNT(*) FROM source_versions").fetchone()[0]
            source_review_count = con.execute("SELECT COUNT(*) FROM source_review_events").fetchone()[0]
            goal_count = con.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
            open_goal_count = con.execute(
                "SELECT COUNT(*) FROM goals WHERE status IN ('open', 'in_progress')"
            ).fetchone()[0]
            blocked_goal_count = con.execute("SELECT COUNT(*) FROM goals WHERE status = 'blocked'").fetchone()[0]
        return {
            "files": file_count,
            "comments": comment_count,
            "audit_events": audit_count,
            "jobs": job_count,
            "wiki_sections": wiki_section_count,
            "sources": source_count,
            "missing_sources": missing_source_count,
            "quarantined_sources": quarantined_source_count,
            "source_versions": source_version_count,
            "source_reviews": source_review_count,
            "goals": goal_count,
            "open_goals": open_goal_count,
            "blocked_goals": blocked_goal_count,
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

    def _wiki_section_row(self, section: WikiSection, indexed_at: str) -> tuple[Any, ...]:
        return (
            section.section_id,
            section.page_path,
            section.page_title,
            section.kind,
            section.heading,
            section.level,
            section.source_path,
            section.body,
            json.dumps(section.terms, ensure_ascii=False),
            section.line_start,
            section.line_end,
            indexed_at,
        )

    def _sync_source_registry(self, con: sqlite3.Connection, index: WikiIndex, indexed_at: str) -> None:
        rows = con.execute("SELECT * FROM source_registry").fetchall()
        existing = {row["rel_path"]: dict(row) for row in rows}
        seen: set[str] = set()
        for record in index.records:
            seen.add(record.rel_path)
            previous = existing.get(record.rel_path, {})
            permission_denied = bool(
                index.access_guard is not None
                and index.access_guard.path_blocked(record.rel_path, operation="read")
            )
            # A file-deny rule forbids every content read, including background
            # hashing for registry metadata. Keep only the already-known path.
            size = 0 if permission_denied else safe_size(record.full_path)
            sha256 = file_sha256(record.full_path) if size and not permission_denied else ""
            if sha256:
                self._record_source_version(con, record.rel_path, sha256, size, indexed_at)
            imported_at = str(previous.get("imported_at") or indexed_at)
            previous_status = str(previous.get("status") or "active")
            registry_status = "quarantined" if previous_status == "quarantined" else "active"
            con.execute(
                """
                INSERT INTO source_registry(
                    rel_path, origin_type, origin, title, category, sha256, size, status,
                    imported_at, updated_at, last_indexed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(rel_path) DO UPDATE SET
                    sha256 = excluded.sha256,
                    size = excluded.size,
                    status = CASE
                      WHEN source_registry.status = 'quarantined' THEN 'quarantined'
                      ELSE 'active'
                    END,
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
                    registry_status,
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

    def _record_source_version(self, con: sqlite3.Connection, rel_path: str, sha256: str, size: int, observed_at: str) -> None:
        con.execute(
            """
            INSERT INTO source_versions(rel_path, sha256, size, first_seen_at, last_seen_at, observation_count)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(rel_path, sha256) DO UPDATE SET
                size = excluded.size,
                last_seen_at = excluded.last_seen_at,
                observation_count = source_versions.observation_count + 1
            """,
            (rel_path, sha256, size, observed_at, observed_at),
        )

    def _sync_goals(self, con: sqlite3.Connection, comments: list[CommentRecord], now: str) -> None:
        active_ids: set[str] = set()
        goal_rows: list[tuple[Any, ...]] = []
        for comment in comments:
            if not comment.todo:
                continue
            goal_id = build_goal_id(comment)
            active_ids.add(goal_id)
            raw_todo = comment.todo.strip()
            assignee = (comment.assignee or "").strip() or None
            end_date = normalize_goal_date(comment.end_date)
            kind = str(comment.kind or "").strip() or "todo"
            goal_rows.append(
                (
                    goal_id,
                    comment.source_path,
                    raw_todo,
                    assignee,
                    end_date,
                    comment.line,
                    kind,
                    comment.raw_text,
                    "open",
                    now,
                    now,
                    now,
                )
            )
        if goal_rows:
            con.executemany(
                """
                INSERT INTO goals(
                    goal_id, source_path, todo, assignee, end_date, line, kind, raw_text, status, created_at, updated_at, state_updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(goal_id) DO UPDATE SET
                    source_path = excluded.source_path,
                    todo = excluded.todo,
                    assignee = excluded.assignee,
                    end_date = excluded.end_date,
                    line = excluded.line,
                    kind = excluded.kind,
                    raw_text = excluded.raw_text,
                    updated_at = excluded.updated_at,
                    state_updated_at = excluded.state_updated_at,
                    status = CASE
                        WHEN goals.status = 'archived' THEN goals.status
                        ELSE excluded.status
                    END
                """,
                goal_rows,
            )
        if active_ids:
            placeholders = ",".join("?" for _ in active_ids)
            con.execute(
                f"""
                UPDATE goals
                SET status = 'archived', state_updated_at = ?
                WHERE status != 'archived' AND goal_id NOT IN ({placeholders})
                """,
                (now, *sorted(active_ids)),
            )

    def list_goals(
        self,
        status: str | None = None,
        assignee: str | None = None,
        source_path: str | None = None,
        search: str | None = None,
        include_archived: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        where = []
        args: list[Any] = []
        if not include_archived:
            where.append("status != 'archived'")
        if status:
            where.append("status = ?")
            args.append(status)
        if assignee:
            where.append("assignee = ?")
            args.append(assignee)
        if source_path:
            where.append("source_path = ?")
            args.append(source_path)
        if search:
            where.append("(todo LIKE ? OR source_path LIKE ? OR assignee LIKE ?)")
            pattern = f"%{search}%"
            args.extend([pattern, pattern, pattern])
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        args.append(limit)
        with self.connect() as con:
            rows = con.execute(
                f"""
                SELECT goal_id, source_path, todo, assignee, end_date, line, kind, raw_text, status, created_at, updated_at, state_updated_at
                FROM goals
                {clause}
                ORDER BY
                    CASE status
                        WHEN 'open' THEN 0
                        WHEN 'in_progress' THEN 1
                        WHEN 'blocked' THEN 2
                        WHEN 'done' THEN 3
                        ELSE 4
                    END,
                    COALESCE(end_date, '99999999') ASC,
                    source_path ASC,
                    goal_id ASC
                LIMIT ?
                """,
                tuple(args),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_goal(self, goal_id: str) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute(
                """
                SELECT goal_id, source_path, todo, assignee, end_date, line, kind, raw_text, status, created_at, updated_at, state_updated_at
                FROM goals
                WHERE goal_id = ?
                """,
                (goal_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_goal_status(self, goal_id: str, status: str, assignee: str | None = None) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as con:
            if assignee is not None:
                con.execute(
                    """
                    UPDATE goals
                    SET status = ?, assignee = ?, state_updated_at = ?
                    WHERE goal_id = ?
                    """,
                    (status, assignee, now, goal_id),
                )
            else:
                con.execute(
                    """
                    UPDATE goals
                    SET status = ?, state_updated_at = ?
                    WHERE goal_id = ?
                    """,
                    (status, now, goal_id),
                )
            row = con.execute(
                """
                SELECT goal_id, source_path, todo, assignee, end_date, line, kind, raw_text, status, created_at, updated_at, state_updated_at
                FROM goals
                WHERE goal_id = ?
                """,
                (goal_id,),
            ).fetchone()
        return dict(row) if row else None


def build_goal_id(comment: CommentRecord) -> str:
    material = "|".join(
        [
            comment.source_path,
            str(comment.line or ""),
            comment.raw_text.replace("\n", " ")[:240],
        ]
    ).strip()
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"goal-{digest}"


def normalize_goal_date(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = re.sub(r"\D", "", str(raw))
    if not cleaned or len(cleaned) != 8:
        return None
    try:
        datetime.strptime(cleaned, "%Y%m%d")
    except ValueError:
        return None
    return cleaned


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


def decode_wiki_section_row(row: sqlite3.Row) -> dict[str, Any]:
    section = dict(row)
    section["terms"] = json.loads(section.pop("terms_json") or "[]")
    return section


def score_wiki_section(section: dict[str, Any], terms: list[str]) -> int:
    hay_page = str(section.get("page_path") or "").lower()
    hay_heading = str(section.get("heading") or "").lower()
    hay_body = str(section.get("body") or "").lower()
    section_terms = {str(term).lower() for term in section.get("terms", [])}
    score = 0
    for term in terms:
        low = term.lower()
        if low in hay_heading:
            score += 20
        if low in hay_page:
            score += 4
        if low in section_terms:
            score += 10
        count = hay_body.count(low)
        if count:
            score += min(count * 3, 12)
    return score


def section_snippet(section: dict[str, Any], terms: list[str], radius: int = 180) -> str:
    text = "\n".join(
        value
        for value in [str(section.get("heading") or ""), str(section.get("body") or "")]
        if value
    )
    low_text = text.lower()
    positions = [
        low_text.find(term.lower())
        for term in terms
        if low_text.find(term.lower()) >= 0
    ]
    if not positions:
        return text[: radius * 2].strip()
    center = min(positions)
    start = max(0, center - radius)
    end = min(len(text), center + radius)
    snippet = text[start:end].strip()
    if start:
        snippet = "..." + snippet
    if end < len(text):
        snippet += "..."
    return snippet
