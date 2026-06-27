#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[4]
    entry = repo_root / "work" / "main.py"
    return subprocess.call([sys.executable, str(entry), *sys.argv[1:]], cwd=repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
