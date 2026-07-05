from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_doc_consistency.py"


class DocConsistencyTest(unittest.TestCase):
    def test_script_runs_cleanly(self) -> None:
        self.assertTrue(SCRIPT.exists(), f"missing consistency script: {SCRIPT}")
        env = os.environ.copy()
        env.setdefault("PYTHONPATH", "work")
        process = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
