from __future__ import annotations

import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .models import CommentRecord, DocumentRecord
from .office_bridge import LEGACY_TO_MODERN, convert_office

COUNT_EXTENSIONS = {
    "doc",
    "docx",
    "ppt",
    "pptx",
    "xls",
    "xlsx",
    "xml",
    "java",
    "py",
    "html",
    "md",
    "js",
}
SUPPORTED_EXTENSIONS = COUNT_EXTENSIONS | {"pdf"}

TEXT_EXTENSIONS = {"xml", "java", "py", "html", "md", "js", "txt", "csv", "json", "yaml", "yml"}

STRUCTURED_TODO_RE = re.compile(
    r"(?is)\btodo\b\s*[:：]\s*(?P<todo>.*?)\s*(?:[,，;；]\s*|\s+)"
    r"\bto\b\s*[:：]\s*(?P<to>.*?)\s*(?:[,，;；]\s*|\s+)"
    r"\bend[\s_-]*date\b\s*[:：]\s*(?P<end_date>\d{8})"
)
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/|<!--.*?-->", re.DOTALL)


def extract_document(path: Path, wiki_root: Path) -> DocumentRecord:
    suffix = path.suffix.lower().lstrip(".")
    rel_path = path.relative_to(wiki_root).as_posix()
    text, office_comments = extract_text_and_office_comments(path, suffix, rel_path)
    comments = office_comments + extract_inline_comments(rel_path, text, suffix)
    return DocumentRecord(
        full_path=path,
        rel_path=rel_path,
        suffix=suffix,
        text=text,
        comments=dedupe_comments(comments),
        tags=infer_tags(rel_path, text),
    )


def extract_text_and_office_comments(
    path: Path, suffix: str, rel_path: str
) -> tuple[str, list[CommentRecord]]:
    if suffix == "docx":
        return extract_docx(path, rel_path)
    if suffix == "pptx":
        return extract_pptx(path, rel_path)
    if suffix == "xlsx":
        return extract_xlsx(path, rel_path)
    if suffix == "pdf":
        return extract_pdf(path), []
    if suffix in LEGACY_TO_MODERN:
        converted = extract_legacy_office(path, suffix, rel_path)
        if converted is not None:
            return converted
    if suffix in TEXT_EXTENSIONS:
        return read_text_best_effort(path), []
    return extract_binary_strings(path), []


def extract_pdf(path: Path) -> str:
    pdftotext = shutil_which("pdftotext")
    if pdftotext:
        try:
            result = subprocess.run(
                [pdftotext, "-layout", str(path), "-"],
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except Exception:
            pass
    return extract_binary_strings(path)


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def extract_legacy_office(path: Path, suffix: str, rel_path: str) -> tuple[str, list[CommentRecord]] | None:
    with tempfile.TemporaryDirectory(prefix="stonehenge-wiki-office-") as tmp:
        converted = convert_office(path, LEGACY_TO_MODERN[suffix], Path(tmp))
        if not converted:
            return None
        return extract_text_and_office_comments(converted, converted.suffix.lower().lstrip("."), rel_path)


def read_text_best_effort(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def extract_binary_strings(path: Path) -> str:
    data = path.read_bytes()
    chunks = re.findall(rb"[\x09\x0a\x0d\x20-\x7e]{4,}|(?:[\x80-\xff][\x80-\xff]?){4,}", data)
    decoded: list[str] = []
    for chunk in chunks:
        for encoding in ("utf-8", "gb18030", "latin-1"):
            try:
                decoded.append(chunk.decode(encoding))
                break
            except UnicodeDecodeError:
                continue
    return "\n".join(decoded)


def extract_docx(path: Path, rel_path: str) -> tuple[str, list[CommentRecord]]:
    text_parts: list[str] = []
    comments: list[CommentRecord] = []
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.startswith("word/") and name.endswith(".xml") and (
                    "document" in name or "header" in name or "footer" in name
                ):
                    text_parts.append(xml_text(zf.read(name)))
            if "word/comments.xml" in zf.namelist():
                comments.extend(parse_docx_comments(zf.read("word/comments.xml"), rel_path))
    except Exception:
        return extract_binary_strings(path), []
    return "\n".join(text_parts), comments


def parse_docx_comments(data: bytes, rel_path: str) -> list[CommentRecord]:
    comments: list[CommentRecord] = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return comments
    for elem in root.iter():
        if not elem.tag.endswith("}comment") and elem.tag != "comment":
            continue
        raw = " ".join(t.strip() for t in elem.itertext() if t and t.strip())
        if not raw:
            continue
        comments.append(make_comment(rel_path, raw, "office", author=elem.attrib.get(_attr("author"))))
    return comments


def extract_pptx(path: Path, rel_path: str) -> tuple[str, list[CommentRecord]]:
    text_parts: list[str] = []
    comments: list[CommentRecord] = []
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.startswith("ppt/slides/") and name.endswith(".xml"):
                    text_parts.append(xml_text(zf.read(name)))
                if name.startswith("ppt/comments/") and name.endswith(".xml"):
                    raw = xml_text(zf.read(name))
                    if raw.strip():
                        comments.append(make_comment(rel_path, raw, "office"))
    except Exception:
        return extract_binary_strings(path), []
    return "\n".join(text_parts), comments


def extract_xlsx(path: Path, rel_path: str) -> tuple[str, list[CommentRecord]]:
    try:
        return extract_xlsx_openpyxl(path, rel_path)
    except Exception:
        return extract_xlsx_zip(path, rel_path)


def extract_xlsx_openpyxl(path: Path, rel_path: str) -> tuple[str, list[CommentRecord]]:
    from openpyxl import load_workbook

    workbook = load_workbook(path, data_only=True, read_only=False)
    text_parts: list[str] = []
    comments: list[CommentRecord] = []
    for sheet in workbook.worksheets:
        text_parts.append(f"[sheet] {sheet.title}")
        for row in sheet.iter_rows():
            values: list[str] = []
            for cell in row:
                if cell.value is not None:
                    values.append(str(cell.value))
                if cell.comment and cell.comment.text:
                    comments.append(
                        make_comment(
                            rel_path,
                            cell.comment.text,
                            "office",
                            author=cell.comment.author,
                        )
                    )
            if values:
                text_parts.append(" | ".join(values))
    return "\n".join(text_parts), comments


def extract_xlsx_zip(path: Path, rel_path: str) -> tuple[str, list[CommentRecord]]:
    text_parts: list[str] = []
    comments: list[CommentRecord] = []
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.endswith(".xml") and (
                    name.startswith("xl/worksheets/")
                    or name == "xl/sharedStrings.xml"
                    or name.startswith("xl/comments")
                ):
                    raw = xml_text(zf.read(name))
                    if name.startswith("xl/comments") and raw.strip():
                        comments.append(make_comment(rel_path, raw, "office"))
                    text_parts.append(raw)
    except Exception:
        return extract_binary_strings(path), []
    return "\n".join(text_parts), comments


def xml_text(data: bytes) -> str:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return data.decode("utf-8", errors="ignore")
    values: list[str] = []
    for elem in root.iter():
        if elem.text and elem.text.strip():
            values.append(elem.text.strip())
    return "\n".join(values)


def extract_inline_comments(rel_path: str, text: str, suffix: str) -> list[CommentRecord]:
    comments: list[CommentRecord] = []
    for match in STRUCTURED_TODO_RE.finditer(text):
        comments.append(make_comment(rel_path, match.group(0), "code"))
    for block in BLOCK_COMMENT_RE.finditer(text):
        comments.append(make_comment(rel_path, block.group(0), "code"))
    for line_no, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        if STRUCTURED_TODO_RE.search(line):
            continue
        if "todo" in low or re.search(r"^\s*(#|//|--)", line):
            if "todo" in low or "需要" in line or "待" in line:
                comments.append(make_comment(rel_path, line, "code", line=line_no))
    return comments


def make_comment(
    rel_path: str,
    raw_text: str,
    kind: str,
    line: int | None = None,
    author: str | None = None,
) -> CommentRecord:
    cleaned = " ".join(raw_text.split())
    match = STRUCTURED_TODO_RE.search(cleaned)
    if match:
        return CommentRecord(
            source_path=rel_path,
            raw_text=cleaned,
            kind=kind,
            todo=clean_field(match.group("todo")),
            assignee=clean_field(match.group("to")),
            end_date=match.group("end_date"),
            line=line,
            author=author,
            structured=True,
        )
    return CommentRecord(
        source_path=rel_path,
        raw_text=cleaned,
        kind=kind,
        line=line,
        author=author,
        structured=False,
    )


def clean_field(value: str) -> str:
    return value.strip(" \t\r\n,，;；。.")


def dedupe_comments(comments: list[CommentRecord]) -> list[CommentRecord]:
    seen: set[tuple[str, str, int | None]] = set()
    result: list[CommentRecord] = []
    for comment in comments:
        key = (comment.source_path, comment.raw_text, comment.line)
        if key in seen:
            continue
        seen.add(key)
        result.append(comment)
    return result


def infer_tags(rel_path: str, text: str) -> set[str]:
    low = (rel_path + "\n" + text[:20000]).lower()
    tags: set[str] = set()
    if any(term in low for term in ("password", "passwd", "密码", "账号", "ip地址", "jdbc", "端口", "host")):
        tags.add("环境信息")
    if any(term in low for term in ("select ", "gauss", "高斯", "gsql", "数据库", "sql")):
        tags.add("数据库")
    if any(term in low for term in ("需求", "prd", "产品", "规则", "设计")):
        tags.add("需求设计")
    if any(term in low for term in ("命令", "ssh ", "curl ", "gsql ", "kubectl", "docker")):
        tags.add("常用命令")
    if any(term in low for term in ("业务", "流程", "客户", "订单", "合同")):
        tags.add("业务")
    return tags


def _attr(name: str) -> str:
    return f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{name}"
