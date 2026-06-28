from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .indexer import WikiIndex
from .models import DocumentRecord


class WikiCompiler:
    def __init__(self, wiki_root: Path, index: WikiIndex):
        self.wiki_root = wiki_root
        self.index = index
        self.compiled_root = wiki_root / "wiki"
        self.sources_dir = self.compiled_root / "sources"
        self.topics_dir = self.compiled_root / "topics"

    def compile(self) -> dict[str, Any]:
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.topics_dir.mkdir(parents=True, exist_ok=True)

        generated_sources: list[Path] = []
        for record in self.index.records:
            target = self.source_page_path(record)
            target.write_text(self.render_source_page(record), encoding="utf-8")
            generated_sources.append(target)

        generated_topics = self.write_topic_pages()
        removed_sources = remove_stale_pages(self.sources_dir, generated_sources)
        removed_topics = remove_stale_pages(self.topics_dir, generated_topics)
        (self.compiled_root / "index.md").write_text(
            self.render_index_page(generated_sources, generated_topics),
            encoding="utf-8",
        )
        self.append_log(
            "compile",
            f"files={len(generated_sources)} topics={len(generated_topics)} "
            f"removed={removed_sources + removed_topics}",
        )
        return {
            "wiki_dir": self.compiled_root.as_posix(),
            "source_pages": len(generated_sources),
            "topic_pages": len(generated_topics),
            "removed_pages": removed_sources + removed_topics,
            "index": (self.compiled_root / "index.md").as_posix(),
            "log": (self.compiled_root / "log.md").as_posix(),
        }

    def lint(self) -> dict[str, Any]:
        issues: list[dict[str, str]] = []
        source_paths = {self.source_page_path(record).resolve() for record in self.index.records}
        existing_sources = set(self.sources_dir.glob("*.md")) if self.sources_dir.exists() else set()
        for missing in sorted(source_paths - {path.resolve() for path in existing_sources}):
            issues.append({"level": "error", "code": "missing_source_page", "path": str(missing)})
        for stale in sorted({path.resolve() for path in existing_sources} - source_paths):
            issues.append({"level": "warning", "code": "stale_source_page", "path": str(stale)})
        for required in ("index.md", "log.md"):
            if not (self.compiled_root / required).exists():
                issues.append({"level": "warning", "code": "missing_wiki_file", "path": str(self.compiled_root / required)})
        broken_links = self.find_broken_links()
        issues.extend({"level": "error", "code": "broken_link", "path": item} for item in broken_links)
        status = "ok" if not any(issue["level"] == "error" for issue in issues) else "error"
        return {"status": status, "issue_count": len(issues), "issues": issues}

    def source_page_path(self, record: DocumentRecord) -> Path:
        return self.sources_dir / f"{slug(record.rel_path)}.md"

    def write_topic_pages(self) -> list[Path]:
        by_tag: dict[str, list[DocumentRecord]] = defaultdict(list)
        for record in self.index.records:
            for tag in record.tags or {"未分类"}:
                by_tag[tag].append(record)

        generated: list[Path] = []
        for tag, records in sorted(by_tag.items()):
            path = self.topics_dir / f"{slug(tag)}.md"
            lines = [
                "---",
                f'title: "{escape_yaml(tag)}"',
                "kind: topic",
                "---",
                "",
                f"# {tag}",
                "",
                f"- Source count: {len(records)}",
                "",
                "## Raw",
                "",
            ]
            for record in sorted(records, key=lambda item: item.rel_path):
                lines.append(f"- [[../sources/{self.source_page_path(record).name}|{record.rel_path}]]")
            lines.append("")
            path.write_text("\n".join(lines), encoding="utf-8")
            generated.append(path)
        return generated

    def render_source_page(self, record: DocumentRecord) -> str:
        tags = ", ".join(sorted(record.tags)) or "未分类"
        snippets = meaningful_snippets(record.text)
        comment_lines = [comment.summary() for comment in record.comments[:25]]
        lines = [
            "---",
            f'title: "{escape_yaml(record.name)}"',
            "kind: source",
            f'source_path: "{escape_yaml(record.rel_path)}"',
            f"file_type: {record.suffix or 'unknown'}",
            f"tags: [{', '.join(escape_yaml(tag) for tag in sorted(record.tags))}]",
            f"comment_count: {len(record.comments)}",
            f'generated_at: "{utc_now()}"',
            "---",
            "",
            f"# {record.name}",
            "",
            f"- Source: `{record.rel_path}`",
            f"- Type: `{record.suffix or 'unknown'}`",
            f"- Tags: {tags}",
            f"- Comments/TODOs: {len(record.comments)}",
            "",
            "## Summary",
            "",
            source_summary(record),
            "",
            "## Evidence Snippets",
            "",
        ]
        lines.extend(f"- {snippet}" for snippet in snippets)
        if not snippets:
            lines.append("- No stable text snippet extracted.")
        lines.extend(["", "## Comments And TODOs", ""])
        lines.extend(f"- {line}" for line in comment_lines)
        if not comment_lines:
            lines.append("- None found.")
        lines.append("")
        return "\n".join(lines)

    def render_index_page(self, source_pages: list[Path], topic_pages: list[Path]) -> str:
        lines = [
            "# LLM Wiki Index",
            "",
            f"Generated at: {utc_now()}",
            "",
            "## Operating Model",
            "",
            "- `docs/` contains raw source documents.",
            "- `wiki/` contains compiled Markdown knowledge pages.",
            "- `AGENTS.md` defines the schema and maintenance contract.",
            "- `log.md` records compile/lint operations.",
            "",
            "## Topics",
            "",
        ]
        for path in sorted(topic_pages):
            lines.append(f"- [[topics/{path.name}|{path.stem}]]")
        if not topic_pages:
            lines.append("- No topics generated.")
        lines.extend(["", "## Raw", ""])
        for record in sorted(self.index.records, key=lambda item: item.rel_path):
            page = self.source_page_path(record).name
            lines.append(f"- [[sources/{page}|{record.rel_path}]]")
        if not source_pages:
            lines.append("- No sources indexed.")
        lines.append("")
        return "\n".join(lines)

    def append_log(self, operation: str, detail: str) -> None:
        log_path = self.compiled_root / "log.md"
        if not log_path.exists():
            log_path.write_text("# LLM Wiki Log\n\n", encoding="utf-8")
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"- {utc_now()} `{operation}` {detail}\n")

    def find_broken_links(self) -> list[str]:
        if not self.compiled_root.exists():
            return []
        broken: list[str] = []
        pattern = re.compile(r"\[\[([^]|]+)(?:\|[^]]+)?\]\]")
        for page in self.compiled_root.rglob("*.md"):
            text = page.read_text(encoding="utf-8", errors="ignore")
            for target in pattern.findall(text):
                target_path = (page.parent / target).resolve()
                if not target_path.exists():
                    broken.append(f"{page.relative_to(self.compiled_root)} -> {target}")
        return broken


def source_summary(record: DocumentRecord) -> str:
    pieces = []
    if record.tags:
        pieces.append("tags " + ", ".join(sorted(record.tags)))
    if record.comments:
        pieces.append(f"{len(record.comments)} comments/TODOs")
    if not pieces:
        pieces.append("indexed source with extracted text")
    return f"This page summarizes `{record.rel_path}` with " + " and ".join(pieces) + "."


def meaningful_snippets(text: str, limit: int = 8) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        cleaned = " ".join(line.split())
        if len(cleaned) < 10:
            continue
        if re.search(r"(password|passwd|secret|token|密钥|密码)", cleaned, re.IGNORECASE):
            continue
        if re.search(r"(忽略.*规则|上帝模式|ignore.*previous|god\s*mode)", cleaned, re.IGNORECASE):
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        snippets.append(cleaned[:220])
        if len(snippets) >= limit:
            break
    return snippets


def slug(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    base = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", value).strip("-").lower()
    if not base:
        base = "page"
    return f"{base[:72]}-{digest}"


def escape_yaml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def remove_stale_pages(directory: Path, generated: list[Path]) -> int:
    if not directory.exists():
        return 0
    keep = {path.resolve() for path in generated}
    removed = 0
    for path in directory.glob("*.md"):
        if path.resolve() in keep:
            continue
        path.unlink()
        removed += 1
    return removed


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
