from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Question


def resolve_question_files(
    wiki_root: Path,
    explicit_files: list[Path] | None,
    groups: list[str] | None,
) -> list[Path]:
    question_dir = wiki_root / "question"
    if question_dir.is_symlink():
        raise ValueError("question directory must not be a symbolic link")
    question_root = question_dir.resolve()

    def validate(path: Path) -> Path:
        candidate = path if path.is_absolute() else (Path.cwd() / path)
        if candidate.is_symlink():
            raise ValueError(f"question file must not be a symbolic link: {candidate}")
        resolved = candidate.resolve()
        if question_root not in resolved.parents or not resolved.is_file():
            raise ValueError(f"question file must be inside the wiki question directory: {candidate}")
        return resolved

    if explicit_files:
        return [validate(path) for path in explicit_files]
    if groups:
        files: list[Path] = []
        for group in groups:
            stem = group.removesuffix(".md")
            files.append(validate(question_dir / f"{stem}.md"))
        return files
    return sorted(validate(path) for path in question_dir.glob("group-*.md"))


def output_path_for_question_file(wiki_root: Path, question_file: Path) -> Path:
    return wiki_root / "output" / f"{question_file.stem}-answer.md"


def write_json_atomic(path: Path, payload: Any) -> None:
    """Publish a complete JSON document even when several judges run in parallel."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(raw_temp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def load_questions(path: Path) -> list[Question]:
    raw = path.read_text(encoding="utf-8")
    data = parse_json_payload(raw)
    if isinstance(data, dict):
        data = data.get("questions", [])
    questions: list[Question] = []
    for idx, item in enumerate(data or [], start=1):
        if not isinstance(item, dict):
            continue
        questions.append(
            Question(
                id=str(item.get("id") or f"{path.stem}-{idx}"),
                title=str(item.get("title") or ""),
                level=str(item.get("level") or ""),
                answer_format=item.get("answer_format"),
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
        pass

    # Question Markdown may carry TODO/comment prose around the required JSON
    # array. Scan for a decodable array instead of trusting the first brace in
    # that prose; this also tolerates trailing Markdown after the payload.
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "[":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            return value
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("questions"), list):
            return value
    raise json.JSONDecodeError("no JSON question array found", text, 0)


def write_result_log(wiki_root: Path, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"- {timestamp} {message}\n".encode("utf-8")
    submission_root = Path(__file__).resolve().parents[2]
    submission_result = submission_root / "result" / "output.md"
    sibling_result = wiki_root.parent / "result" / "output.md"
    judge_assets = Path("/app/code/judge-assets")
    if wiki_root == judge_assets or judge_assets in wiki_root.parents:
        candidates = [submission_result, sibling_result]
    else:
        candidates = [sibling_result, submission_result]
    # Result logging must never turn a successfully generated answer into a
    # failed run when judge assets live in a read-only /app tree.
    for result_path in candidates:
        try:
            result_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(result_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(descriptor, line)
            finally:
                os.close(descriptor)
            return
        except OSError:
            continue
