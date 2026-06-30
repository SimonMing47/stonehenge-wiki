from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Question


def resolve_question_files(
    wiki_root: Path,
    explicit_files: list[Path] | None,
    groups: list[str] | None,
) -> list[Path]:
    if explicit_files:
        return [path if path.is_absolute() else (Path.cwd() / path) for path in explicit_files]
    question_dir = wiki_root / "question"
    if groups:
        files: list[Path] = []
        for group in groups:
            stem = group.removesuffix(".md")
            files.append(question_dir / f"{stem}.md")
        return files
    return sorted(question_dir.glob("group-*.md"))


def output_path_for_question_file(wiki_root: Path, question_file: Path) -> Path:
    return wiki_root / "output" / f"{question_file.stem}-answer.md"


def load_questions(path: Path) -> list[Question]:
    raw = path.read_text(encoding="utf-8")
    data = parse_json_payload(raw)
    if isinstance(data, dict):
        data = data.get("questions", [])
    questions: list[Question] = []
    for idx, item in enumerate(data or [], start=1):
        questions.append(
            Question(
                id=str(item.get("id") or f"{path.stem}-{idx}"),
                title=str(item.get("title") or ""),
                level=str(item.get("level") or ""),
            )
        )
    return questions


def parse_json_payload(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start_candidates = [pos for pos in (text.find("["), text.find("{")) if pos >= 0]
        if not start_candidates:
            raise
        start = min(start_candidates)
        end = max(text.rfind("]"), text.rfind("}"))
        return json.loads(text[start : end + 1])


def write_result_log(wiki_root: Path, message: str) -> None:
    result_path = wiki_root.parent / "result" / "output.md"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with result_path.open("a", encoding="utf-8") as fh:
        fh.write(f"- {timestamp} {message}\n")

