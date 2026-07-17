from __future__ import annotations

import shutil
import subprocess
import tempfile
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
    # A dedicated user profile prevents concurrent conversions from contending on
    # LibreOffice's global profile lock and also works when HOME is read-only.
    try:
        with tempfile.TemporaryDirectory(prefix="stonehenge-wiki-soffice-profile-") as profile:
            profile_uri = Path(profile).resolve().as_uri()
            result = subprocess.run(
                [
                    soffice,
                    f"-env:UserInstallation={profile_uri}",
                    "--headless",
                    "--nologo",
                    "--nodefault",
                    "--nofirststartwizard",
                    "--convert-to",
                    target_ext,
                    "--outdir",
                    str(out_dir.resolve()),
                    str(source.resolve()),
                ],
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    exact = out_dir / f"{source.stem}.{target_ext}"
    if exact.exists():
        return exact
    matches = sorted(out_dir.glob(f"*.{target_ext}"))
    return matches[0] if matches else None
