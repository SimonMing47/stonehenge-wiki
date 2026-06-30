from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

LEGACY_TO_MODERN = {
    "doc": "docx",
    "ppt": "pptx",
    "xls": "xlsx",
}


def has_soffice() -> bool:
    return bool(find_soffice())


def find_soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def convert_office(source: Path, target_ext: str, out_dir: Path, timeout: int = 30) -> Path | None:
    soffice = find_soffice()
    if not soffice:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            target_ext,
            "--outdir",
            str(out_dir),
            str(source),
        ],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        return None
    exact = out_dir / f"{source.stem}.{target_ext}"
    if exact.exists():
        return exact
    matches = sorted(out_dir.glob(f"*.{target_ext}"))
    return matches[0] if matches else None

