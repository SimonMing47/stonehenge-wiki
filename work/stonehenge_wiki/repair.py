from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from .models import CommentRecord, DocumentRecord
from .office_bridge import LEGACY_TO_MODERN, convert_office

REPLACE_RE = re.compile(r"(?:把|将)?(?P<old>[^，,。；;\s]{1,80})(?:改成|改为|替换为)(?P<new>[^，,。；;\s]{1,80})")


def repair_document(record: DocumentRecord, wiki_root: Path, comments: list[CommentRecord]) -> tuple[str, str]:
    source_rel = record.rel_path
    target_rel = "output/fixed/" + source_rel.removeprefix("docs/")
    target_path = wiki_root / target_rel
    target_path.parent.mkdir(parents=True, exist_ok=True)

    replacements = extract_replacements(comments)
    if not replacements:
        shutil.copy2(record.full_path, target_path)
        return source_rel, target_rel

    suffix = record.suffix
    if suffix in {"py", "java", "js", "html", "md", "xml", "txt", "csv", "json"}:
        text = record.full_path.read_text(encoding="utf-8", errors="ignore")
        text = apply_text_replacements(text, replacements)
        target_path.write_text(text, encoding="utf-8")
    elif suffix in {"docx", "pptx", "xlsx"}:
        replace_in_zip_xml(record.full_path, target_path, replacements)
    elif suffix in LEGACY_TO_MODERN and repair_legacy_office(record.full_path, target_path, suffix, replacements):
        pass
    else:
        shutil.copy2(record.full_path, target_path)
    return source_rel, target_rel


def extract_replacements(comments: list[CommentRecord]) -> list[tuple[str, str]]:
    replacements: list[tuple[str, str]] = []
    for comment in comments:
        text = comment.todo or comment.raw_text
        match = REPLACE_RE.search(text)
        if not match:
            continue
        old = match.group("old").strip()
        new = match.group("new").strip()
        if old and new and old != new:
            replacements.append((old, new))
    return replacements


def apply_text_replacements(text: str, replacements: list[tuple[str, str]]) -> str:
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if "todo" in stripped.lower() or stripped.startswith(("#", "//", "/*", "*", "<!--")):
            lines.append(line)
            continue
        updated = line
        for old, new in replacements:
            updated = updated.replace(old, new)
        lines.append(updated)
    return "".join(lines)


def replace_in_zip_xml(source: Path, target: Path, replacements: list[tuple[str, str]]) -> None:
    with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith(".xml"):
                text = data.decode("utf-8", errors="ignore")
                for old, new in replacements:
                    text = text.replace(old, new)
                data = text.encode("utf-8")
            zout.writestr(item, data)


def repair_legacy_office(
    source: Path,
    target: Path,
    source_suffix: str,
    replacements: list[tuple[str, str]],
) -> bool:
    modern_ext = LEGACY_TO_MODERN[source_suffix]
    with tempfile.TemporaryDirectory(prefix="stonehenge-wiki-office-repair-") as tmp:
        tmp_dir = Path(tmp)
        converted = convert_office(source, modern_ext, tmp_dir / "modern")
        if not converted:
            return False
        repaired_modern = tmp_dir / f"repaired.{modern_ext}"
        replace_in_zip_xml(converted, repaired_modern, replacements)
        converted_back = convert_office(repaired_modern, source_suffix, tmp_dir / "legacy")
        if not converted_back:
            return False
        shutil.copy2(converted_back, target)
        return True
