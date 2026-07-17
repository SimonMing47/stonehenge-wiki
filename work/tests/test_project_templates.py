from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stonehenge_wiki.cli import discover_wiki_root
from stonehenge_wiki.config import load_config


REPO_ROOT = Path(__file__).resolve().parents[2]


class ProjectTemplateTest(unittest.TestCase):
    def test_pull_request_template_covers_delivery_guardrails(self) -> None:
        path = REPO_ROOT / ".github" / "pull_request_template.md"
        if not path.exists():
            self.skipTest("repository metadata is not in the submission ZIP")
        template = path.read_text(encoding="utf-8")

        for required in [
            "Platform/API/Security",
            "Web Console/Product",
            "CLI/Skill/Quality/Release",
            "no-RAG",
            "Rust CLI remains REST-only",
            "stonehenge_wiki.contract_checks",
            "Browser smoke",
            "Release smoke",
            "GitHub Actions run",
        ]:
            self.assertIn(required, template)

    def test_issue_forms_preserve_architecture_and_safety_prompts(self) -> None:
        if not (REPO_ROOT / ".github").exists():
            self.skipTest("repository metadata is not in the submission ZIP")
        bug = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").read_text(encoding="utf-8")
        feature = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml").read_text(encoding="utf-8")
        config = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8")

        for text in (bug, feature):
            self.assertIn("Platform/API/Security", text)
            self.assertIn("Web Console/Product", text)
            self.assertIn("CLI/Skill/Quality/Release", text)
            self.assertIn("no-RAG", text)
            self.assertIn("REST", text)
        self.assertIn("Sensitive values", bug)
        self.assertIn("compiled wiki", feature)
        self.assertIn("release bundles", feature)
        self.assertIn("blank_issues_enabled: false", config)

    def test_ci_workflow_uses_current_action_majors(self) -> None:
        path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        if not path.exists():
            self.skipTest("repository metadata is not in the submission ZIP")
        workflow = path.read_text(encoding="utf-8")

        self.assertIn("actions/checkout@v7", workflow)
        self.assertIn("actions/setup-python@v6", workflow)
        self.assertNotIn("actions/checkout@v4", workflow)
        self.assertNotIn("actions/setup-python@v5", workflow)

    def test_opencode_bootstrap_is_documented_without_secrets(self) -> None:
        scripts = REPO_ROOT / "work" / "skills" / "stonehenge-wiki" / "scripts"
        script = scripts / "configure_opencode.sh"
        skill = (REPO_ROOT / "work" / "skills" / "stonehenge-wiki" / "SKILL.md").read_text(encoding="utf-8")
        instruction = (REPO_ROOT / "INSTRUCTION.md").read_text(encoding="utf-8")
        script_text = script.read_text(encoding="utf-8")

        self.assertTrue(script.exists())
        self.assertFalse((scripts / ("configure_opencode_from_" + "her" + "mes.sh")).exists())
        self.assertFalse(
            (REPO_ROOT / "work" / "skills" / "stonehenge-wiki" / "agents" / ("open" + "ai.yaml")).exists()
        )
        self.assertIn("configure_opencode.sh", skill)
        self.assertIn("configure_opencode.sh", instruction)
        self.assertIn("OPENCODE_API_KEY", script_text)
        self.assertIn('OPENCODE_PROVIDER="${OPENCODE_PROVIDER:-zhipu}"', script_text)
        self.assertIn('OPENCODE_MODEL="${OPENCODE_MODEL:-glm-5.2}"', script_text)
        self.assertIn("opencode run --pure --format json", instruction)
        self.assertNotRegex(script_text, r"sk-[A-Za-z0-9]{20,}")

    def test_opencode_bootstrap_writes_private_external_config(self) -> None:
        script = REPO_ROOT / "work" / "skills" / "stonehenge-wiki" / "scripts" / "configure_opencode.sh"
        with tempfile.TemporaryDirectory(prefix="llm-wiki-opencode-config-") as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            config_dir = root / "config"
            bin_dir.mkdir()
            fake_runtime = bin_dir / "opencode"
            fake_runtime.write_text("#!/bin/sh\necho opencode-test\n", encoding="utf-8")
            fake_runtime.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
                "OPENCODE_CONFIG_DIR": str(config_dir),
                "OPENCODE_API_KEY": "unit-test-placeholder",
            }
            process = subprocess.run(
                ["bash", str(script)],
                cwd=REPO_ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            config_path = config_dir / "opencode.json"
            key_path = config_dir / "opencode-runtime.key"
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["model"], "zhipu/glm-5.2")
            self.assertEqual(config_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(key_path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("unit-test-placeholder", config_path.read_text(encoding="utf-8"))

    def test_data_root_discovery_prefers_work_sibling_llm_wiki(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-root-discovery-") as tmp:
            repo = Path(tmp)
            for name in ("llm-wiki", "stonehenge-wiki"):
                candidate = repo / name
                (candidate / "docs").mkdir(parents=True)
                (candidate / "question").mkdir()
                (candidate / "Permission.json").write_text("{}", encoding="utf-8")

            self.assertEqual(discover_wiki_root(repo), repo / "llm-wiki")
            (repo / "llm-wiki" / "Permission.json").unlink()
            self.assertEqual(discover_wiki_root(repo), repo / "stonehenge-wiki")

    def test_unpacked_data_root_defaults_to_opencode_runtime(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-default-config-") as tmp:
            wiki_root = Path(tmp) / "llm-wiki"
            wiki_root.mkdir()
            with patch.dict(os.environ, {"OPENCODE_MODEL": "glm-5.2"}):
                config = load_config(wiki_root)

            self.assertEqual(config.llm_default_agent, "opencode")
            self.assertTrue(config.llm_agents["opencode"].enabled)
            self.assertEqual(config.llm_agents["opencode"].runtime_mode, "opencode")
            self.assertEqual(config.llm_agents["opencode"].model, "glm-5.2")
            self.assertIn("opencode run", config.llm_agents["opencode"].runtime_command)


if __name__ == "__main__":
    unittest.main()
