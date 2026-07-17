from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .extractors import COUNT_EXTENSIONS, extract_document
from .models import CommentRecord, DocumentRecord

STOPWORDS = {
    "请问",
    "哪些",
    "哪个",
    "什么",
    "文件",
    "路径",
    "名称",
    "统计",
    "数量",
    "多少",
    "包含",
    "涉及",
    "涉及到",
    "关于",
    "业务",
    "答案",
    "列出",
    "获取",
    "一下",
    "中的",
    "所有",
}


class WikiIndex:
    def __init__(self, wiki_root: Path, access_guard: object | None = None):
        self.wiki_root = wiki_root
        self.docs_dir = wiki_root / "docs"
        self.access_guard = access_guard
        self.records: list[DocumentRecord] = []
        self.by_path: dict[str, DocumentRecord] = {}

    def build(self) -> "WikiIndex":
        self.records = []
        self.by_path = {}
        if self.docs_dir.is_symlink() or not self.docs_dir.exists():
            return self
        docs_root = self.docs_dir.resolve()
        wiki_root = self.wiki_root.resolve()
        if docs_root != wiki_root and wiki_root not in docs_root.parents:
            return self
        for path in sorted(self.docs_dir.rglob("*")):
            if path.is_symlink() or not path.is_file() or path.name.startswith("."):
                continue
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved != docs_root and docs_root not in resolved.parents:
                # Never follow a docs/ symlink into the host filesystem.
                continue
            rel_path = path.relative_to(self.wiki_root).as_posix()
            if self.access_guard is not None and self.access_guard.path_blocked(rel_path, operation="read"):
                # Preserve only suffix metadata so policy reporting and counts can
                # reason about the path without ever opening a forbidden file.
                record = DocumentRecord(
                    path,
                    rel_path,
                    path.suffix.lower().lstrip("."),
                    "[permission_denied]",
                )
                self.records.append(record)
                self.by_path[record.rel_path] = record
                continue
            try:
                record = extract_document(path, self.wiki_root)
            except Exception as exc:
                record = DocumentRecord(path, rel_path, path.suffix.lower().lstrip("."), f"[extract_error] {exc}")
            self.records.append(record)
            self.by_path[record.rel_path] = record
        return self

    def with_records(self, records: list[DocumentRecord]) -> "WikiIndex":
        view = WikiIndex(self.wiki_root, access_guard=self.access_guard)
        view.records = list(records)
        view.by_path = {record.rel_path: record for record in view.records}
        return view

    @property
    def comments(self) -> list[CommentRecord]:
        result: list[CommentRecord] = []
        for record in self.records:
            result.extend(record.comments)
        return result

    def file_counts(self, exts: list[str] | None = None) -> dict[str, int]:
        requested = exts or sorted(COUNT_EXTENSIONS)
        counter = Counter(record.suffix for record in self.records)
        return {ext: counter.get(ext, 0) for ext in requested}

    def find_records_mentioned(self, text: str) -> list[DocumentRecord]:
        low = text.lower()
        result: list[DocumentRecord] = []
        for record in self.records:
            if record.rel_path.lower() in low or record.name.lower() in low:
                result.append(record)
        return result

    def search(self, query: str, limit: int = 8, records: list[DocumentRecord] | None = None) -> list[DocumentRecord]:
        return [record for _, record in self.search_with_scores(query, limit=limit, records=records)]

    def search_with_scores(
        self,
        query: str,
        limit: int = 8,
        records: list[DocumentRecord] | None = None,
    ) -> list[tuple[int, DocumentRecord]]:
        pool = records if records is not None else self.records
        terms = query_terms(query)
        if not terms:
            return [(0, record) for record in pool[:limit]]
        scored: list[tuple[int, DocumentRecord]] = []
        for record in pool:
            hay_path = record.rel_path.lower()
            hay_name = record.name.lower()
            hay_text = record.text.lower()
            tag_text = " ".join(record.tags).lower()
            score = 0
            for term in terms:
                low = term.lower()
                if low in hay_name:
                    score += 30
                if low in hay_path:
                    score += 16
                if low in tag_text:
                    score += 12
                count = hay_text.count(low)
                if count:
                    score += min(count, 8)
            if score:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].rel_path))
        return scored[:limit]


def query_terms(query: str) -> list[str]:
    raw_terms: list[str] = []
    raw_terms.extend(re.findall(r"[A-Za-z][A-Za-z0-9_.-]{1,}", query))
    raw_terms.extend(re.findall(r"\d{2,}", query))
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", query):
        if chunk not in STOPWORDS:
            raw_terms.append(chunk)
        for size in (2, 3, 4):
            for idx in range(0, max(0, len(chunk) - size + 1)):
                piece = chunk[idx : idx + size]
                if piece not in STOPWORDS:
                    raw_terms.append(piece)
    seen: set[str] = set()
    terms: list[str] = []
    for term in raw_terms:
        cleaned = term.strip().lower()
        if len(cleaned) < 2 or cleaned in STOPWORDS or cleaned in seen:
            continue
        seen.add(cleaned)
        terms.append(cleaned)
    return terms[:80]
