from __future__ import annotations

import hashlib
import ipaddress
import mimetypes
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .extractors import SUPPORTED_EXTENSIONS, TEXT_EXTENSIONS
from .security import PermissionGuard

MAX_IMPORT_BYTES = 20 * 1024 * 1024
DEFAULT_CATEGORY = "00_inbox"
ALLOWED_EXTENSIONS = SUPPORTED_EXTENSIONS | TEXT_EXTENSIONS


@dataclass(frozen=True)
class ImportedSource:
    source: str
    source_type: str
    rel_path: str
    size: int
    sha256: str


class SourceImportError(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def import_source(
    wiki_root: Path,
    source: str,
    guard: PermissionGuard,
    title: str = "",
    category: str = DEFAULT_CATEGORY,
    max_bytes: int = MAX_IMPORT_BYTES,
) -> ImportedSource:
    source = source.strip()
    if not source:
        raise SourceImportError("empty_source", "source is required")

    if is_http_url(source):
        data, filename, final_source = read_url(source, max_bytes=max_bytes)
        source_type = "url"
    else:
        data, filename, final_source = read_local_file(source, guard=guard, max_bytes=max_bytes)
        source_type = "file"

    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        raise SourceImportError("unsupported_extension", f"unsupported extension: {ext or 'none'}")

    target_dir = wiki_root / "docs" / sanitize_category(category)
    target_name = safe_filename(title, fallback=filename)
    if Path(target_name).suffix.lower().lstrip(".") not in ALLOWED_EXTENSIONS:
        target_name = f"{Path(target_name).stem}.{ext}"
    target = unique_path(target_dir / target_name)
    rel_path = target.relative_to(wiki_root).as_posix()
    if guard.path_blocked(rel_path, operation="write"):
        raise SourceImportError("permission_path", "target path is blocked by Permission.json")

    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return ImportedSource(
        source=final_source,
        source_type=source_type,
        rel_path=rel_path,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def read_local_file(source: str, guard: PermissionGuard, max_bytes: int) -> tuple[bytes, str, str]:
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise SourceImportError("not_found", "source file does not exist")
    if guard.path_blocked(path.as_posix(), operation="read"):
        raise SourceImportError("permission_path", "source path is blocked by Permission.json")
    size = path.stat().st_size
    if size > max_bytes:
        raise SourceImportError("too_large", f"source is larger than {max_bytes} bytes")
    return path.read_bytes(), path.name, path.as_posix()


def read_url(source: str, max_bytes: int) -> tuple[bytes, str, str]:
    validate_public_http_url(source)
    opener = urllib.request.build_opener(SafeRedirectHandler)
    request = urllib.request.Request(source, headers={"User-Agent": "Stonehenge-Wiki/1.0"})
    try:
        with opener.open(request, timeout=30) as response:
            final_url = response.geturl()
            validate_public_http_url(final_url)
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise SourceImportError("too_large", f"source is larger than {max_bytes} bytes")
            content_type = response.headers.get("Content-Type", "")
    except SourceImportError:
        raise
    except urllib.error.HTTPError as exc:
        raise SourceImportError("http_error", f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SourceImportError("network_error", str(exc.reason)) from exc
    except TimeoutError as exc:
        raise SourceImportError("timeout", "URL import timed out") from exc
    filename = filename_from_url(final_url, content_type)
    return data, filename, final_url


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        validate_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SourceImportError("unsupported_url", "only http and https URLs are supported")
    if not parsed.hostname:
        raise SourceImportError("unsupported_url", "URL host is required")
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise SourceImportError("private_url", "private or local URLs are not allowed")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise SourceImportError("dns_error", str(exc)) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise SourceImportError("private_url", "private or local URLs are not allowed")


def filename_from_url(url: str, content_type: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    if Path(name).suffix:
        return name
    ext = extension_from_content_type(content_type)
    return f"{slugify(parsed.hostname or 'source')}.{ext}"


def extension_from_content_type(content_type: str) -> str:
    ctype = content_type.split(";", 1)[0].strip().lower()
    if ctype in {"text/html", "application/xhtml+xml"}:
        return "html"
    if ctype.startswith("text/"):
        return "txt"
    guessed = mimetypes.guess_extension(ctype) or ".txt"
    ext = guessed.lstrip(".")
    return "html" if ext == "htm" else ext


def is_http_url(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"}


def sanitize_category(category: str) -> str:
    raw = category.strip() or DEFAULT_CATEGORY
    return slugify(raw.replace("/", "-").replace("\\", "-")) or DEFAULT_CATEGORY


def safe_filename(title: str, fallback: str) -> str:
    fallback_path = Path(fallback)
    ext = fallback_path.suffix.lower()
    stem = slugify(title or fallback_path.stem) or "source"
    return f"{stem[:96]}{ext}"


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff._-]+", "-", value.strip()).strip("-._")
    return slug[:120]


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for idx in range(2, 1000):
        candidate = path.with_name(f"{stem}-{idx}{suffix}")
        if not candidate.exists():
            return candidate
    raise SourceImportError("name_conflict", "too many files with the same name")
