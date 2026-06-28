from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

from .indexer import query_terms
from .models import DocumentRecord

SECRET_RE = re.compile(r"(password|passwd|密码|密钥|secret|token)", re.IGNORECASE)
INJECTION_RE = re.compile(r"(忽略.*规则|上帝模式|ignore.*previous|god\s*mode|删除全部文档)", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
HTML_BOILERPLATE_RE = re.compile(
    r"^(function\s|var\s|if\s*\(|\}?\s*else\b|\}\s*$|\},?\s*\d+\)?$|"
    r"return\s|settimeout\b|document\.|window\.|antiRobot|"
    r".*\.style|.*getElementById|/\*|"
    r"Home$|Menu$|About$|Documentation$|Download$|License$|Support$|Purchase$|Search$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    rel_path: str
    ordinal: int
    text: str
    terms: list[str]
    line_start: int
    line_end: int
    char_count: int


def build_chunks(record: DocumentRecord, max_chars: int = 1200, overlap_lines: int = 2) -> list[ChunkRecord]:
    lines = clean_lines(record.text, suffix=record.suffix)
    chunks: list[ChunkRecord] = []
    buffer: list[tuple[int, str]] = []
    size = 0
    ordinal = 0
    for line_no, text in lines:
        if buffer and size + len(text) + 1 > max_chars:
            chunks.append(make_chunk(record.rel_path, ordinal, buffer))
            ordinal += 1
            buffer = buffer[-overlap_lines:] if overlap_lines else []
            size = sum(len(item[1]) + 1 for item in buffer)
        buffer.append((line_no, text))
        size += len(text) + 1
    if buffer:
        chunks.append(make_chunk(record.rel_path, ordinal, buffer))
    return chunks


def clean_lines(text: str, suffix: str = "") -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = clean_line(raw_line)
        if not line:
            continue
        if SECRET_RE.search(line) or INJECTION_RE.search(line):
            continue
        if suffix == "html" and HTML_BOILERPLATE_RE.search(line):
            continue
        result.append((line_no, line))
    return result


def clean_line(raw_line: str) -> str:
    if re.match(r"^\s*<(?:!doctype|html|head|meta|link|script|style)\b", raw_line, re.IGNORECASE):
        return ""
    text = HTML_TAG_RE.sub(" ", raw_line)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if text in {"{", "}", ");", "};"}:
        return ""
    return text


def make_chunk(rel_path: str, ordinal: int, lines: list[tuple[int, str]]) -> ChunkRecord:
    text = "\n".join(line for _, line in lines).strip()
    line_start = lines[0][0]
    line_end = lines[-1][0]
    chunk_id = f"{rel_path}#chunk-{ordinal:04d}"
    terms = query_terms(text)[:80]
    return ChunkRecord(
        chunk_id=chunk_id,
        rel_path=rel_path,
        ordinal=ordinal,
        text=text,
        terms=terms,
        line_start=line_start,
        line_end=line_end,
        char_count=len(text),
    )
