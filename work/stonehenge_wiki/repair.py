from __future__ import annotations

import re
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .models import CommentRecord, DocumentRecord
from .office_bridge import LEGACY_TO_MODERN, convert_office

REPLACE_PATTERNS = (
    re.compile(
        r"(?:将)?[^，,。；;\n]{0,30}?从\s*[‘’“”\"']?(?P<old>[^，,。；;\n]{1,80}?)[‘’“”\"']?\s*"
        r"(?:改成|改为|修改为|替换为|更新为)\s*[‘’“”\"']?(?P<new>[^，,。；;\n]{1,80})"
    ),
    re.compile(
        r"(?:应该|请|需要|需)?\s*(?:把|将)\s*[‘’“”\"']?(?P<old>[^，,。；;\n]{1,80}?)[‘’“”\"']?\s*"
        r"(?:改成|改为|修改为|替换为|更新为)\s*[‘’“”\"']?(?P<new>[^，,。；;\n]{1,80})"
    ),
    re.compile(r"[‘’“”\"']?(?P<old>[^，,。；;\n]{1,80}?)[‘’“”\"']?\s*(?:=>|→)\s*[‘’“”\"']?(?P<new>[^，,。；;\n]{1,80})"),
)


def repair_document(
    record: DocumentRecord,
    wiki_root: Path,
    comments: list[CommentRecord],
    replacements: list[tuple[str, str]] | None = None,
) -> tuple[str, str]:
    source_rel = record.rel_path
    target_rel = repair_target_rel(source_rel)
    target_path = wiki_root / target_rel
    target_path.parent.mkdir(parents=True, exist_ok=True)

    fd, raw_temp = tempfile.mkstemp(
        prefix=f".{target_path.stem}.", suffix=target_path.suffix, dir=target_path.parent
    )
    os.close(fd)
    temp_target = Path(raw_temp)
    temp_target.unlink(missing_ok=True)

    try:
        replacements = extract_replacements(comments) if replacements is None else replacements
        if not replacements:
            shutil.copy2(record.full_path, temp_target)
        else:
            suffix = record.suffix
            if suffix in {"py", "java", "js", "html", "md", "xml", "txt", "csv", "json"}:
                text = record.full_path.read_text(encoding="utf-8", errors="ignore")
                text = apply_text_replacements(text, replacements)
                temp_target.write_text(text, encoding="utf-8")
            elif suffix in {"docx", "pptx", "xlsx"} or zipfile.is_zipfile(record.full_path):
                replace_in_zip_xml(record.full_path, temp_target, replacements)
            elif suffix in LEGACY_TO_MODERN and repair_legacy_office(
                record.full_path, temp_target, suffix, replacements
            ):
                pass
            else:
                shutil.copy2(record.full_path, temp_target)
        os.replace(temp_target, target_path)
    except Exception:
        temp_target.unlink(missing_ok=True)
        raise
    return source_rel, target_rel


def repair_target_rel(source_rel: str) -> str:
    source_parts = Path(source_rel).parts
    if not source_parts or source_parts[0] != "docs" or ".." in source_parts:
        raise ValueError("source path must be inside docs")
    return "output/fixed/" + Path(*source_parts[1:]).as_posix()


def extract_replacements(comments: list[CommentRecord]) -> list[tuple[str, str]]:
    replacements: list[tuple[str, str]] = []
    for comment in comments:
        text = comment.todo or comment.raw_text
        for pattern in REPLACE_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            old = clean_replacement_value(match.group("old"))
            new = clean_replacement_value(match.group("new"))
            if old and new and old != new:
                replacements.append((old, new))
            break
    # Preserve instruction order while avoiding repeated replacements.
    return list(dict.fromkeys(replacements))


def clean_replacement_value(value: str) -> str:
    cleaned = value.strip(" \t\r\n‘’“”\"'：:")
    cleaned = re.sub(r"\s*(?:即可|为准|并保存|后保存|后输出)$", "", cleaned)
    return cleaned.strip(" \t\r\n‘’“”\"'")


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
            if should_repair_office_part(item.filename):
                data = replace_xml_content(data, replacements)
            zout.writestr(item, data)


def should_repair_office_part(name: str) -> bool:
    if not name.endswith(".xml"):
        return False
    if name.startswith("word/"):
        return bool(
            re.match(r"word/(?:document|header\d*|footer\d*|footnotes|endnotes)\.xml$", name)
        )
    if name.startswith("ppt/"):
        return name.startswith("ppt/slides/") or name.startswith("ppt/notesSlides/")
    if name.startswith("xl/"):
        return name == "xl/sharedStrings.xml" or name.startswith("xl/worksheets/")
    return False


def replace_xml_content(data: bytes, replacements: list[tuple[str, str]]) -> bytes:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    updated = text
    for old, new in replacements:
        updated = updated.replace(old, new)
    if updated != text:
        return updated.encode("utf-8")

    # Word and PowerPoint often split a visible phrase across several text runs.
    # Only reserialize when such a split replacement is actually required.
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return data
    changed = False
    containers = [elem for elem in root.iter() if local_name(elem.tag) in {"p", "si", "is"}]
    for container in containers:
        nodes = [elem for elem in container.iter() if local_name(elem.tag) in {"t", "text"} and elem.text]
        if not nodes:
            continue
        visible = "".join(node.text or "" for node in nodes)
        replaced = visible
        for old, new in replacements:
            replaced = replaced.replace(old, new)
        if replaced == visible:
            continue
        nodes[0].text = replaced
        for node in nodes[1:]:
            node.text = ""
        changed = True
    if not changed:
        return data
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


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
