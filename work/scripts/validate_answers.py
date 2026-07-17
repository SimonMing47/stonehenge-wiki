#!/usr/bin/env python3
"""Validate competition answer files without exposing their contents.

The validator deliberately reads only ``question/group-*.md`` and the matching
``output/group-*-answer.md`` files.  For repaired-document answers it performs
metadata-only checks (path resolution and ``is_file``) on the reported target;
it never opens source documents, repaired documents, configuration, or secret
files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any


DENIED_MESSAGE = "高危命令，拒绝访问"
OFFICIAL_FILE_TYPES = frozenset(
    {"doc", "docx", "ppt", "pptx", "xls", "xlsx", "xml", "java", "py", "html", "md", "js"}
)
REQUIRED_ANSWER_FIELDS = frozenset({"id", "answer"})
SAFE_GROUP_RE = re.compile(r"^group-[A-Za-z0-9_-]+$")


@dataclass
class ValidationSummary:
    groups_total: int = 0
    groups_valid: int = 0
    questions_total: int = 0
    answers_total: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def add_error(self, code: str, group: str | None = None, index: int | None = None) -> None:
        """Record location metadata only; never copy untrusted values."""
        error: dict[str, Any] = {"code": code}
        if group and SAFE_GROUP_RE.fullmatch(group):
            error["group"] = group
        if index is not None:
            error["index"] = index
        self.errors.append(error)

    def payload(self) -> dict[str, Any]:
        return {
            "ok": not self.errors,
            "groups_total": self.groups_total,
            "groups_valid": self.groups_valid,
            "questions_total": self.questions_total,
            "answers_total": self.answers_total,
            "error_count": len(self.errors),
            "errors": self.errors,
        }


def _read_json(path: Path, *, allow_markdown_array: bool) -> Any:
    raw = path.read_text(encoding="utf-8")
    if not allow_markdown_array:
        return json.loads(raw)

    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Questions are Markdown files and may contain prose or a fenced JSON array.
    # Select only a decodable list whose entries resemble question objects.
    decoder = json.JSONDecoder()
    for offset, char in enumerate(text):
        if char != "[":
            continue
        try:
            value, _ = decoder.raw_decode(text[offset:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            return value
    raise ValueError("question JSON array not found")


def _valid_question(item: Any) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and bool(item["id"])
        and isinstance(item.get("title"), str)
        and bool(item["title"])
        and isinstance(item.get("level"), str)
        and bool(item["level"])
    )


def _normalise_answer_format(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        nested = value.get("answer")
        return nested if isinstance(nested, dict) else value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        decoded = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(decoded, dict):
        return None
    nested = decoded.get("answer")
    return nested if isinstance(nested, dict) else decoded


def _shape_name(keys: set[str]) -> str | None:
    if keys == {"error_msg"}:
        return "error"
    if keys == {"count"}:
        return "count"
    if keys == {"source", "target"}:
        return "repair"
    if keys == {"datas"}:
        return "datas"
    if keys and "error_msg" not in keys and "count" not in keys and "source" not in keys and "target" not in keys and "datas" not in keys:
        return "file_counts"
    return None


def _safe_relative_posix_path(value: str, required_prefix: tuple[str, ...]) -> bool:
    if not value or "\\" in value or "\x00" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and path.parts[: len(required_prefix)] == required_prefix
        and len(path.parts) > len(required_prefix)
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _validate_answer_shape(
    wiki_root: Path,
    question: dict[str, Any],
    answer: Any,
) -> str | None:
    if not isinstance(answer, dict):
        return "answer_not_object"

    keys = set(answer)
    shape = _shape_name(keys)
    if shape is None:
        return "answer_shape_invalid"

    # A security refusal always supersedes the question's requested format.
    if shape == "error":
        return None if answer.get("error_msg") == DENIED_MESSAGE else "error_message_invalid"

    expected = _normalise_answer_format(question.get("answer_format"))
    expected_shape = _shape_name(set(expected)) if expected else None
    if expected_shape and shape != expected_shape:
        return "answer_format_mismatch"

    if shape == "count":
        value = answer["count"]
        return None if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else "count_invalid"

    if shape == "datas":
        values = answer["datas"]
        return None if isinstance(values, list) and all(isinstance(value, str) for value in values) else "datas_invalid"

    if shape == "repair":
        source = answer["source"]
        target = answer["target"]
        if not isinstance(source, str) or not _safe_relative_posix_path(source, ("docs",)):
            return "repair_source_invalid"
        if not isinstance(target, str) or not _safe_relative_posix_path(target, ("output", "fixed")):
            return "repair_target_invalid"
        fixed_root = (wiki_root / "output" / "fixed").resolve()
        target_path = (wiki_root / Path(*PurePosixPath(target).parts)).resolve()
        try:
            target_path.relative_to(fixed_root)
        except ValueError:
            return "repair_target_outside_fixed"
        # Do not open the file: existence and regular-file metadata are enough.
        return None if target_path.is_file() else "repair_target_missing"

    allowed_types = set(OFFICIAL_FILE_TYPES)
    normalised_keys = {str(key).lower() for key in keys}
    if normalised_keys != set(keys) or not normalised_keys.issubset(allowed_types):
        return "file_count_type_invalid"
    if expected and set(expected) != keys:
        return "answer_format_mismatch"
    if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in answer.values()):
        return "file_count_value_invalid"
    return None


def validate(wiki_root: Path) -> ValidationSummary:
    summary = ValidationSummary()
    question_dir = wiki_root / "question"
    output_dir = wiki_root / "output"
    question_files = sorted(question_dir.glob("group-*.md")) if question_dir.is_dir() else []
    answer_files = sorted(output_dir.glob("group-*-answer.md")) if output_dir.is_dir() else []
    summary.groups_total = len(question_files)

    if not question_files:
        summary.add_error("no_question_groups")

    expected_answers = {f"{path.stem}-answer.md" for path in question_files}
    for answer_file in answer_files:
        if answer_file.name not in expected_answers:
            group = answer_file.name.removesuffix("-answer.md")
            summary.add_error("orphan_answer_group", group=group)

    for question_file in question_files:
        group = question_file.stem
        group_error_start = len(summary.errors)
        answer_file = output_dir / f"{group}-answer.md"

        try:
            questions = _read_json(question_file, allow_markdown_array=True)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            summary.add_error("question_json_invalid", group=group)
            continue
        if not isinstance(questions, list):
            summary.add_error("question_root_not_array", group=group)
            continue

        summary.questions_total += len(questions)
        question_ids: set[str] = set()
        questions_valid = True
        for index, question in enumerate(questions, start=1):
            if not _valid_question(question):
                summary.add_error("question_schema_invalid", group=group, index=index)
                questions_valid = False
                continue
            if question["id"] in question_ids:
                summary.add_error("question_id_duplicate", group=group, index=index)
                questions_valid = False
            question_ids.add(question["id"])

        if not answer_file.is_file():
            summary.add_error("answer_file_missing", group=group)
            continue
        try:
            answers = _read_json(answer_file, allow_markdown_array=False)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            summary.add_error("answer_json_invalid", group=group)
            continue
        if not isinstance(answers, list):
            summary.add_error("answer_root_not_array", group=group)
            continue

        summary.answers_total += len(answers)
        if len(answers) != len(questions):
            summary.add_error("answer_count_mismatch", group=group)

        answer_ids: set[str] = set()
        for index, (question, entry) in enumerate(zip(questions, answers), start=1):
            if not _valid_question(question):
                continue
            if not isinstance(entry, dict) or set(entry) != set(REQUIRED_ANSWER_FIELDS):
                summary.add_error("answer_entry_schema_invalid", group=group, index=index)
                continue
            entry_id = entry.get("id")
            if not isinstance(entry_id, str):
                summary.add_error("answer_id_invalid", group=group, index=index)
            elif entry_id in answer_ids:
                summary.add_error("answer_id_duplicate", group=group, index=index)
            answer_ids.add(entry_id) if isinstance(entry_id, str) else None

            if entry.get("id") != question["id"]:
                summary.add_error("answer_id_mismatch", group=group, index=index)
            shape_error = _validate_answer_shape(wiki_root, question, entry.get("answer"))
            if shape_error:
                summary.add_error(shape_error, group=group, index=index)

        if questions_valid and len(summary.errors) == group_error_start:
            summary.groups_valid += 1

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate all competition answer groups")
    parser.add_argument("--wiki-root", required=True, type=Path, help="Path to the released llm-wiki directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = validate(args.wiki_root.resolve())
    except Exception:
        # Keep unexpected failures machine-readable and never serialize exception
        # text, which could contain an answer value or sensitive filesystem path.
        summary = ValidationSummary()
        summary.add_error("validator_internal_error")
    json.dump(summary.payload(), sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0 if not summary.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
