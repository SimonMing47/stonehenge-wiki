from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class ProjectTemplateTest(unittest.TestCase):
    def test_pull_request_template_covers_delivery_guardrails(self) -> None:
        template = (REPO_ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")

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
        workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("actions/checkout@v7", workflow)
        self.assertIn("actions/setup-python@v6", workflow)
        self.assertNotIn("actions/checkout@v4", workflow)
        self.assertNotIn("actions/setup-python@v5", workflow)

    def test_opencode_hermes_bootstrap_is_documented_without_secrets(self) -> None:
        script = REPO_ROOT / "work" / "skills" / "stonehenge-wiki" / "scripts" / "configure_opencode_from_hermes.sh"
        skill = (REPO_ROOT / "work" / "skills" / "stonehenge-wiki" / "SKILL.md").read_text(encoding="utf-8")
        instruction = (REPO_ROOT / "INSTRUCTION.md").read_text(encoding="utf-8")
        script_text = script.read_text(encoding="utf-8")

        self.assertTrue(script.exists())
        self.assertIn("configure_opencode_from_hermes.sh", skill)
        self.assertIn("configure_opencode_from_hermes.sh", instruction)
        self.assertIn("DEEPSEEK_API_KEY", script_text)
        self.assertIn("OPENCODE_PROVIDER=\"${OPENCODE_PROVIDER:-hermes-deepseek}\"", script_text)
        self.assertIn("OPENCODE_MODEL=\"${OPENCODE_MODEL:-deepseek-v4-pro}\"", script_text)
        self.assertIn("opencode run -m hermes-deepseek/deepseek-v4-pro", instruction)
        self.assertNotRegex(script_text, r"sk-[A-Za-z0-9]{20,}")


if __name__ == "__main__":
    unittest.main()
