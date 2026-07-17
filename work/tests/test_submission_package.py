from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_SCRIPT = REPO_ROOT / "scripts" / "package_submission.py"

packager = None
if PACKAGE_SCRIPT.exists():
    SPEC = importlib.util.spec_from_file_location("submission_packager", PACKAGE_SCRIPT)
    assert SPEC is not None and SPEC.loader is not None
    packager = importlib.util.module_from_spec(SPEC)
    sys.modules[SPEC.name] = packager
    SPEC.loader.exec_module(packager)


@unittest.skipUnless(PACKAGE_SCRIPT.exists(), "repository-only packaging script is not in the submission ZIP")
class SubmissionPackageTest(unittest.TestCase):
    def _minimal_source(self, root: Path) -> None:
        (root / "work").mkdir(parents=True)
        (root / "result").mkdir()
        (root / "logs" / "trace").mkdir(parents=True)
        (root / "INSTRUCTION.md").write_text("# run\n", encoding="utf-8")
        (root / "work" / "main.py").write_text("print('ok')\n", encoding="utf-8")
        (root / "result" / "output.md").write_text("ok\n", encoding="utf-8")
        (root / "logs" / "interaction.md").write_text("", encoding="utf-8")

    def test_exact_final_name_has_one_matching_root_and_required_layout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-final-package-") as tmp:
            output_dir = Path(tmp)
            process = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE_SCRIPT),
                    "--source-root",
                    str(REPO_ROOT),
                    "--output-dir",
                    str(output_dir),
                    "--track-id",
                    "01",
                    "--question-id",
                    "01",
                    "--team-name",
                    "硬控AI三秒钟",
                ],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            payload = json.loads(process.stdout)
            archive_path = output_dir / "01_01_硬控AI三秒钟.zip"
            self.assertEqual(Path(payload["archive"]), archive_path)
            self.assertEqual(payload["root"], "01_01_硬控AI三秒钟")
            self.assertTrue(archive_path.is_file())

            with zipfile.ZipFile(archive_path) as archive:
                names = archive.namelist()
            root = "01_01_硬控AI三秒钟"
            self.assertEqual({name.rstrip("/").split("/", 1)[0] for name in names}, {root})
            for required in [
                f"{root}/",
                f"{root}/INSTRUCTION.md",
                f"{root}/work/",
                f"{root}/result/",
                f"{root}/result/output.md",
                f"{root}/logs/",
                f"{root}/logs/interaction.md",
                f"{root}/logs/trace/",
            ]:
                self.assertIn(required, names)

            joined = "\n".join(names)
            for forbidden in [
                "/.git/",
                "/__pycache__/",
                "/.state/",
                f"{root}/dist/",
                f"{root}/stonehenge-wiki/",
                f"{root}/scripts/package_submission.py",
            ]:
                self.assertNotIn(forbidden, joined)

            verify = subprocess.run(
                [sys.executable, str(PACKAGE_SCRIPT), "--verify", str(archive_path)],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
            self.assertEqual(json.loads(verify.stdout)["status"], "ok")

    def test_generated_state_credentials_and_sample_data_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-package-filter-") as tmp:
            root = Path(tmp) / "source"
            output = Path(tmp) / "out"
            self._minimal_source(root)
            (root / "work" / "__pycache__").mkdir()
            (root / "work" / "__pycache__" / "main.pyc").write_bytes(b"cache")
            (root / "work" / ".state").mkdir()
            (root / "work" / ".state" / "wiki.sqlite").write_bytes(b"state")
            (root / "work" / "dist").mkdir()
            (root / "work" / "dist" / "generated.bin").write_bytes(b"generated")
            (root / "work" / ".env").write_text("TOKEN=not-packaged\n", encoding="utf-8")
            (root / "work" / "opencode.json").write_text("{}\n", encoding="utf-8")
            (root / "stonehenge-wiki" / "docs").mkdir(parents=True)
            (root / "stonehenge-wiki" / "docs" / "sample.md").write_text("sample\n", encoding="utf-8")
            (root / "problem_statement").mkdir()
            (root / "problem_statement" / "PROBLEM.md").write_text("# problem\n", encoding="utf-8")

            report = packager.build_submission(root, output, "02", "01", "测试队")
            with zipfile.ZipFile(report.archive) as archive:
                names = archive.namelist()
            joined = "\n".join(names)
            self.assertIn("02_01_测试队/problem_statement/PROBLEM.md", names)
            for forbidden in ["__pycache__", ".state", "/dist/", ".env", "opencode.json", "sample.md"]:
                self.assertNotIn(forbidden, joined)

    def test_rejects_symlink_even_when_it_points_inside_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-package-link-") as tmp:
            root = Path(tmp) / "source"
            self._minimal_source(root)
            link = root / "work" / "main-link.py"
            try:
                link.symlink_to(root / "work" / "main.py")
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink unavailable: {exc}")

            with self.assertRaisesRegex(packager.PackageError, "符号链接"):
                packager.collect_source_entries(root)

    def test_rejects_secret_fingerprint_in_ordinary_source_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-package-secret-") as tmp:
            root = Path(tmp) / "source"
            self._minimal_source(root)
            fake_key = "a" * 32 + "." + "B" * 20
            (root / "work" / "accidental.txt").write_text(fake_key, encoding="utf-8")

            with self.assertRaisesRegex(packager.PackageError, "GLM-style API key"):
                packager.build_submission(root, Path(tmp) / "out", "01", "01", "测试队")

    def test_rejects_unsafe_metadata_and_zip_path_traversal(self) -> None:
        for team_name in ["../escape", "team/name", " team", "team.zip"]:
            with self.subTest(team_name=team_name):
                with self.assertRaises(packager.PackageError):
                    packager.submission_name("01", "01", team_name)
        with self.assertRaises(packager.PackageError):
            packager.submission_name("03", "01", "测试队")
        with self.assertRaises(packager.PackageError):
            packager.submission_name("01", "1", "测试队")

        with tempfile.TemporaryDirectory(prefix="llm-wiki-package-traversal-") as tmp:
            archive_path = Path(tmp) / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("safe/", b"")
                archive.writestr("safe/../escape.txt", b"escape")
            with self.assertRaisesRegex(packager.PackageError, "路径穿越"):
                packager.verify_archive(archive_path)

    def test_verify_requires_archive_filename_to_match_its_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-package-root-name-") as tmp:
            archive_path = Path(tmp) / "wrong-name.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("actual-root/", b"")
            with self.assertRaisesRegex(packager.PackageError, "根目录应为 wrong-name"):
                packager.verify_archive(archive_path)


if __name__ == "__main__":
    unittest.main()
