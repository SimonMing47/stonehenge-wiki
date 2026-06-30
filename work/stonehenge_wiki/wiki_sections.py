from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .indexer import query_terms

SECRET_RE = re.compile(r"(password|passwd|密码|密钥|secret|token)", re.IGNORECASE)
INJECTION_RE = re.compile(r"(忽略.*规则|上帝模式|ignore.*previous|god\s*mode|删除全部文档)", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class WikiSection:
    section_id: str
    page_path: str
    page_title: str
    kind: str
    heading: str
    level: int
    source_path: str
    body: str
    terms: list[str]
    line_start: int
    line_end: int


def build_wiki_sections(compiled_root: Path) -> list[WikiSection]:
    if not compiled_root.exists():
        return []
    sections: list[WikiSection] = []
    for page in sorted(compiled_root.rglob("*.md")):
        if page.name == "log.md":
            continue
        rel_page = page.relative_to(compiled_root).as_posix()
        sections.extend(parse_wiki_page(page, rel_page))
    return sections


def parse_wiki_page(path: Path, rel_page: str) -> list[WikiSection]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    metadata, body_lines, body_offset = split_frontmatter(text)
    page_title = metadata.get("title") or path.stem
    kind = metadata.get("kind") or "page"
    source_path = metadata.get("source_path") or ""
    heading_positions: list[tuple[int, int, str]] = []
    for idx, line in enumerate(body_lines, start=body_offset):
        match = HEADING_RE.match(line)
        if match:
            heading_positions.append((idx, len(match.group(1)), match.group(2).strip()))
    if not heading_positions:
        heading_positions = [(body_offset, 1, page_title)]

    sections: list[WikiSection] = []
    for pos, (line_no, level, heading) in enumerate(heading_positions):
        next_line = heading_positions[pos + 1][0] if pos + 1 < len(heading_positions) else body_offset + len(body_lines)
        start_idx = max(0, line_no - body_offset + 1)
        end_idx = max(start_idx, next_line - body_offset)
        section_body = clean_section_body(body_lines[start_idx:end_idx])
        section_text = "\n".join([heading, section_body]).strip()
        if not section_text:
            continue
        section_id = f"{rel_page}#{slug(heading)}"
        sections.append(
            WikiSection(
                section_id=section_id,
                page_path=rel_page,
                page_title=page_title,
                kind=kind,
                heading=heading,
                level=level,
                source_path=source_path,
                body=section_body,
                terms=query_terms(section_text)[:80],
                line_start=line_no,
                line_end=max(line_no, next_line - 1),
            )
        )
    return sections


def split_frontmatter(text: str) -> tuple[dict[str, str], list[str], int]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, lines, 1
    metadata: dict[str, str] = {}
    end = 0
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = idx
            break
        key, sep, value = line.partition(":")
        if sep:
            metadata[key.strip()] = value.strip().strip('"')
    if not end:
        return {}, lines, 1
    return metadata, lines[end + 1 :], end + 2


def clean_section_body(lines: list[str]) -> str:
    cleaned: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or SECRET_RE.search(line) or INJECTION_RE.search(line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned[:40])


def slug(value: str) -> str:
    slugged = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", value).strip("-").lower()
    return slugged[:80] or "section"
