#!/usr/bin/env python3
"""Build and verify the competition submission ZIP.

The archive is intentionally assembled from a small allowlist instead of from the
whole repository.  This keeps development state, sample data and local runtime
credentials out of the deliverable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


REQUIRED_FILE_PATHS = (
    PurePosixPath("INSTRUCTION.md"),
    PurePosixPath("result/output.md"),
    PurePosixPath("logs/interaction.md"),
)
REQUIRED_DIRECTORY_PATHS = (
    PurePosixPath("work"),
    PurePosixPath("result"),
    PurePosixPath("logs"),
    PurePosixPath("logs/trace"),
)
ALLOWED_TOP_LEVEL = frozenset({"INSTRUCTION.md", "work", "result", "logs", "problem_statement"})
PACKAGE_DIRECTORIES = ("work", "result", "logs")
OPTIONAL_PACKAGE_DIRECTORIES = ("problem_statement",)

EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".cache",
        ".config",
        ".aws",
        ".azure",
        ".git",
        ".gnupg",
        ".hg",
        ".kube",
        ".local",
        ".mypy_cache",
        ".nox",
        ".opencode",
        ".pytest_cache",
        ".ruff_cache",
        ".ssh",
        ".state",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "generated",
        "node_modules",
        "output",
        "outputs",
        "releases",
        "target",
        "temp",
        "tmp",
        "venv",
    }
)
EXCLUDED_FILE_NAMES = frozenset(
    {
        ".env",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "auth.json",
        "credentials",
        "credentials.json",
        "id_ed25519",
        "id_rsa",
        "opencode-runtime.key",
        "opencode.json",
    }
)
EXCLUDED_FILE_SUFFIXES = (
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pem",
    ".pfx",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".zip",
)

# These patterns are deliberately narrow.  They catch credentials commonly
# copied into a repository without rejecting documented environment-variable
# names or obvious placeholders.
SECRET_PATTERNS = (
    ("private key", re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("OpenAI-style API key", re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("GLM-style API key", re.compile(rb"\b[0-9a-fA-F]{32}\.[A-Za-z0-9_-]{16,}\b")),
    ("GitHub token", re.compile(rb"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b")),
    ("AWS access key", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
)

MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
FIXED_ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


class PackageError(RuntimeError):
    """Raised when a source tree or ZIP violates the delivery contract."""


@dataclass(frozen=True)
class SourceEntry:
    relative_path: PurePosixPath
    source_path: Path
    is_directory: bool


@dataclass(frozen=True)
class VerificationReport:
    archive: Path
    root: str
    files: int
    directories: int
    uncompressed_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "archive": str(self.archive),
            "root": self.root,
            "files": self.files,
            "directories": self.directories,
            "uncompressed_bytes": self.uncompressed_bytes,
            "status": "ok",
        }


def _is_excluded(relative_path: PurePosixPath, *, is_directory: bool) -> bool:
    lower_parts = tuple(part.casefold() for part in relative_path.parts)
    if any(part in EXCLUDED_DIRECTORY_NAMES for part in lower_parts[:-1]):
        return True

    name = lower_parts[-1]
    if is_directory:
        return name in EXCLUDED_DIRECTORY_NAMES
    if name in EXCLUDED_FILE_NAMES or name.startswith(".env."):
        return True
    return any(name.endswith(suffix) for suffix in EXCLUDED_FILE_SUFFIXES)


def _validate_team_name(team_name: str) -> str:
    if not team_name or team_name != team_name.strip():
        raise PackageError("team-name 不能为空，也不能包含首尾空白")
    if len(team_name) > 80:
        raise PackageError("team-name 不能超过 80 个字符")
    if not all(character.isalnum() or character in {"-", "_"} for character in team_name):
        raise PackageError("team-name 只能包含 Unicode 字母、数字、连字符或下划线")
    return team_name


def submission_name(track_id: str, question_id: str, team_name: str) -> str:
    if track_id not in {"01", "02"}:
        raise PackageError("track-id 必须为 01 或 02")
    if not re.fullmatch(r"\d{2}", question_id):
        raise PackageError("question-id 必须是两位数字，例如 00 或 01")
    return f"{track_id}_{question_id}_{_validate_team_name(team_name)}"


def _validate_source_root(source_root: Path) -> Path:
    if source_root.is_symlink():
        raise PackageError("source-root 不能是符号链接")
    try:
        resolved = source_root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PackageError(f"source-root 不存在：{source_root}") from exc
    if not resolved.is_dir():
        raise PackageError(f"source-root 不是目录：{source_root}")

    for relative in REQUIRED_FILE_PATHS:
        candidate = resolved.joinpath(*relative.parts)
        if candidate.is_symlink() or not candidate.is_file():
            raise PackageError(f"缺少必选普通文件：{relative.as_posix()}")
    for relative in REQUIRED_DIRECTORY_PATHS:
        candidate = resolved.joinpath(*relative.parts)
        if candidate.is_symlink() or not candidate.is_dir():
            raise PackageError(f"缺少必选目录：{relative.as_posix()}/")
    return resolved


def _walk_directory(source_root: Path, directory: Path) -> Iterable[SourceEntry]:
    relative_directory = PurePosixPath(directory.relative_to(source_root).as_posix())
    yield SourceEntry(relative_directory, directory, True)

    with os.scandir(directory) as iterator:
        children = sorted(iterator, key=lambda entry: entry.name)
    for child in children:
        child_path = Path(child.path)
        relative = PurePosixPath(child_path.relative_to(source_root).as_posix())
        if child.is_symlink():
            raise PackageError(f"交付目录中不允许符号链接：{relative.as_posix()}")
        if child.is_dir(follow_symlinks=False):
            if not _is_excluded(relative, is_directory=True):
                yield from _walk_directory(source_root, child_path)
            continue
        if child.is_file(follow_symlinks=False):
            if not _is_excluded(relative, is_directory=False):
                yield SourceEntry(relative, child_path, False)
            continue
        raise PackageError(f"交付目录中存在不支持的文件类型：{relative.as_posix()}")


def collect_source_entries(source_root: Path) -> list[SourceEntry]:
    root = _validate_source_root(source_root)
    entries = [SourceEntry(PurePosixPath("INSTRUCTION.md"), root / "INSTRUCTION.md", False)]
    for name in PACKAGE_DIRECTORIES:
        entries.extend(_walk_directory(root, root / name))
    for name in OPTIONAL_PACKAGE_DIRECTORIES:
        candidate = root / name
        if candidate.is_symlink():
            raise PackageError(f"可选交付目录不能是符号链接：{name}")
        if candidate.exists():
            if not candidate.is_dir():
                raise PackageError(f"可选交付项必须是目录：{name}")
            entries.extend(_walk_directory(root, candidate))
    return sorted(entries, key=lambda entry: (entry.relative_path.as_posix(), not entry.is_directory))


def _scan_secret_bytes(data: bytes, relative_path: PurePosixPath) -> None:
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(data):
            raise PackageError(f"疑似包含 {label}，拒绝打包：{relative_path.as_posix()}")


def _read_safe_file(path: Path, relative_path: PurePosixPath) -> bytes:
    size = path.stat(follow_symlinks=False).st_size
    if size > MAX_FILE_BYTES:
        raise PackageError(f"单文件超过 128 MiB 限制：{relative_path.as_posix()}")
    data = path.read_bytes()
    _scan_secret_bytes(data, relative_path)
    return data


def _zip_info(name: str, *, is_directory: bool, executable: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIMESTAMP)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    if is_directory:
        info.external_attr = ((stat.S_IFDIR | 0o755) << 16) | 0x10
    else:
        mode = 0o755 if executable else 0o644
        info.external_attr = (stat.S_IFREG | mode) << 16
    return info


def build_submission(
    source_root: Path,
    output_dir: Path,
    track_id: str,
    question_id: str,
    team_name: str,
    *,
    force: bool = False,
) -> VerificationReport:
    root_name = submission_name(track_id, question_id, team_name)
    entries = collect_source_entries(source_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{root_name}.zip"
    if destination.exists() and not force:
        raise PackageError(f"目标文件已存在；确认覆盖时请增加 --force：{destination}")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{root_name}.", suffix=".tmp", dir=output_dir, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)

        with zipfile.ZipFile(temporary_path, "w", allowZip64=True) as archive:
            archive.writestr(_zip_info(f"{root_name}/", is_directory=True), b"")
            total_size = 0
            for entry in entries:
                member_name = f"{root_name}/{entry.relative_path.as_posix()}"
                if entry.is_directory:
                    archive.writestr(_zip_info(f"{member_name}/", is_directory=True), b"")
                    continue
                data = _read_safe_file(entry.source_path, entry.relative_path)
                total_size += len(data)
                if total_size > MAX_ARCHIVE_BYTES:
                    raise PackageError("交付文件总大小超过 512 MiB 限制")
                executable = bool(entry.source_path.stat(follow_symlinks=False).st_mode & stat.S_IXUSR)
                archive.writestr(_zip_info(member_name, is_directory=False, executable=executable), data)

        report = verify_archive(temporary_path, expected_root=root_name)
        os.replace(temporary_path, destination)
        temporary_path = None
        destination.chmod(0o644)
        return VerificationReport(
            archive=destination.resolve(),
            root=report.root,
            files=report.files,
            directories=report.directories,
            uncompressed_bytes=report.uncompressed_bytes,
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _safe_member_path(name: str) -> PurePosixPath:
    if not name or "\\" in name or name.startswith("/"):
        raise PackageError(f"ZIP 包含非法路径：{name!r}")
    stripped = name.rstrip("/")
    path = PurePosixPath(stripped)
    if not stripped or any(part in {"", ".", ".."} for part in path.parts):
        raise PackageError(f"ZIP 包含路径穿越或空路径：{name!r}")
    return path


def _zip_member_is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK


def verify_archive(archive_path: Path, *, expected_root: str | None = None) -> VerificationReport:
    if expected_root is None:
        if archive_path.suffix.casefold() != ".zip":
            raise PackageError("待验证文件必须使用 .zip 后缀")
        expected_root = archive_path.name[: -len(archive_path.suffix)]
    try:
        archive = zipfile.ZipFile(archive_path, "r")
    except (FileNotFoundError, zipfile.BadZipFile, OSError) as exc:
        raise PackageError(f"无法读取 ZIP：{archive_path}") from exc

    with archive:
        infos = archive.infolist()
        if not infos:
            raise PackageError("ZIP 不能为空")

        paths: dict[str, zipfile.ZipInfo] = {}
        roots: set[str] = set()
        file_count = 0
        directory_count = 0
        total_size = 0
        for info in infos:
            path = _safe_member_path(info.filename)
            normalized = path.as_posix()
            if normalized in paths:
                raise PackageError(f"ZIP 包含重复条目：{normalized}")
            paths[normalized] = info
            roots.add(path.parts[0])
            if info.flag_bits & 0x1:
                raise PackageError(f"ZIP 不允许加密条目：{normalized}")
            if _zip_member_is_symlink(info):
                raise PackageError(f"ZIP 不允许符号链接：{normalized}")
            if info.is_dir():
                directory_count += 1
            else:
                file_count += 1
                total_size += info.file_size
                if info.file_size > MAX_FILE_BYTES or total_size > MAX_ARCHIVE_BYTES:
                    raise PackageError("ZIP 解压大小超过安全限制")

        if len(roots) != 1:
            raise PackageError(f"ZIP 必须只有一个根目录，实际为：{sorted(roots)}")
        root = next(iter(roots))
        if root != expected_root:
            raise PackageError(f"ZIP 根目录应为 {expected_root}，实际为 {root}")
        if root not in paths or not paths[root].is_dir():
            raise PackageError("ZIP 必须显式包含同名根目录条目")

        prefix = f"{root}/"
        for normalized, info in paths.items():
            if normalized == root:
                continue
            if not normalized.startswith(prefix):
                raise PackageError(f"ZIP 条目不在唯一根目录内：{normalized}")
            relative = PurePosixPath(normalized.removeprefix(prefix))
            if relative.parts[0] not in ALLOWED_TOP_LEVEL:
                raise PackageError(f"ZIP 包含非交付项：{relative.as_posix()}")
            if _is_excluded(relative, is_directory=info.is_dir()):
                raise PackageError(f"ZIP 包含应排除项：{relative.as_posix()}")

        for required in REQUIRED_FILE_PATHS:
            name = f"{root}/{required.as_posix()}"
            if name not in paths or paths[name].is_dir():
                raise PackageError(f"ZIP 缺少必选文件：{required.as_posix()}")
        for required in REQUIRED_DIRECTORY_PATHS:
            name = f"{root}/{required.as_posix()}"
            if name not in paths or not paths[name].is_dir():
                raise PackageError(f"ZIP 缺少必选目录：{required.as_posix()}/")

        for normalized, info in paths.items():
            if info.is_dir():
                continue
            relative = PurePosixPath(normalized.removeprefix(prefix))
            with archive.open(info, "r") as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise PackageError(f"ZIP 单文件超过安全限制：{relative.as_posix()}")
            _scan_secret_bytes(data, relative)

    return VerificationReport(
        archive=archive_path.resolve(),
        root=root,
        files=file_count,
        directories=directory_count,
        uncompressed_bytes=total_size,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="构建并校验比赛 ZIP 交付包")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--track-id", help="赛道 ID：01（难题）或 02（竞赛）")
    parser.add_argument("--question-id", help="两位题号，例如 00 或 01")
    parser.add_argument("--team-name", help="队名")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的同名 ZIP")
    parser.add_argument("--verify", type=Path, metavar="ZIP", help="只校验已有 ZIP，不创建新包")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.verify is not None:
            if any(value is not None for value in (args.track_id, args.question_id, args.team_name)):
                raise PackageError("--verify 不能与 track-id/question-id/team-name 同时使用")
            report = verify_archive(args.verify)
        else:
            if not all((args.track_id, args.question_id, args.team_name)):
                raise PackageError("创建 ZIP 时必须同时提供 --track-id、--question-id、--team-name")
            report = build_submission(
                args.source_root,
                args.output_dir,
                args.track_id,
                args.question_id,
                args.team_name,
                force=args.force,
            )
    except PackageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
