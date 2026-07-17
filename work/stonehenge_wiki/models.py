from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CommentRecord:
    source_path: str
    raw_text: str
    kind: str
    todo: str | None = None
    assignee: str | None = None
    end_date: str | None = None
    line: int | None = None
    author: str | None = None
    created: str | None = None
    structured: bool = False

    def summary(self) -> str:
        parts = [self.source_path]
        if self.line:
            parts.append(f"line:{self.line}")
        if self.todo:
            parts.append(f"todo:{self.todo}")
        if self.assignee:
            parts.append(f"to:{self.assignee}")
        if self.end_date:
            parts.append(f"end_date:{self.end_date}")
        if self.author:
            parts.append(f"author:{self.author}")
        if self.created:
            parts.append(f"created:{self.created}")
        if not self.structured:
            text = " ".join(self.raw_text.split())
            parts.append(f"comment:{text[:160]}")
        return " | ".join(parts)


@dataclass
class DocumentRecord:
    full_path: Path
    rel_path: str
    suffix: str
    text: str
    comments: list[CommentRecord] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)

    @property
    def name(self) -> str:
        return self.full_path.name


@dataclass
class Question:
    id: str
    title: str
    level: str = ""
    answer_format: Any = None


@dataclass
class GoalRecord:
    goal_id: str
    source_path: str
    todo: str
    assignee: str | None
    end_date: str | None
    status: str
    line: int | None = None
    kind: str = ""
    raw_text: str = ""
    created_at: str = ""
    state_updated_at: str = ""
    updated_at: str | None = None
