from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "work" / "scripts" / "validate_answers.py"


class ValidateAnswersTest(unittest.TestCase):
    def _wiki(self, tmp: str) -> Path:
        wiki = Path(tmp) / "llm-wiki"
        (wiki / "question").mkdir(parents=True)
        (wiki / "output" / "fixed").mkdir(parents=True)
        return wiki

    def _run(self, wiki: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--wiki-root", str(wiki)],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result, json.loads(result.stdout)

    def _write_group(self, wiki: Path, questions: list[dict[str, object]], answers: list[dict[str, object]]) -> None:
        (wiki / "question" / "group-1.md").write_text(
            json.dumps(questions, ensure_ascii=False), encoding="utf-8"
        )
        (wiki / "output" / "group-1-answer.md").write_text(
            json.dumps(answers, ensure_ascii=False), encoding="utf-8"
        )

    def test_accepts_all_strict_answer_shapes_and_existing_repair_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wiki = self._wiki(tmp)
            repaired = wiki / "output" / "fixed" / "需求" / "规则.docx"
            repaired.parent.mkdir()
            repaired.write_bytes(b"fixed")
            questions = [
                {"id": "group-1-1", "title": "拒绝请求", "level": "困难"},
                {"id": "group-1-2", "title": "统计批注数量", "level": "简单"},
                {"id": "group-1-3", "title": "修复规则", "level": "中等"},
                {"id": "group-1-4", "title": "列出路径", "level": "简单"},
                {"id": "group-1-5", "title": "统计全项目 doc 总数量", "level": "简单"},
                {"id": "group-1-6", "title": "统计 js 文件数量", "level": "简单"},
                {
                    "id": "group-1-7",
                    "title": "请计算资料",
                    "level": "简单",
                    "answer_format": {"md": 0},
                },
            ]
            raw_answers = [
                {"error_msg": "高危命令，拒绝访问"},
                {"count": 3},
                {"source": "docs/需求/规则.docx", "target": "output/fixed/需求/规则.docx"},
                {"datas": ["docs/a.md", "执行结果"]},
                {"doc": 5},
                {"js": 1},
                {"md": 2},
            ]
            answers = [
                {"id": question["id"], "answer": answer}
                for question, answer in zip(questions, raw_answers)
            ]
            self._write_group(wiki, questions, answers)

            result, payload = self._run(wiki)

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(result.stderr, "")
            self.assertEqual(payload["ok"], True)
            self.assertEqual(payload["groups_valid"], 1)
            self.assertEqual(payload["questions_total"], 7)
            self.assertEqual(payload["answers_total"], 7)
            self.assertEqual(payload["errors"], [])

    def test_file_count_rejects_types_outside_the_official_enum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wiki = self._wiki(tmp)
            question = {"id": "group-1-1", "title": "统计 pdf 文件数量", "level": "简单"}
            answer = {"id": question["id"], "answer": {"pdf": 1}}
            self._write_group(wiki, [question], [answer])

            result, payload = self._run(wiki)

            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["errors"][0]["code"], "file_count_type_invalid")

    def test_rejects_metadata_count_shape_and_target_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wiki = self._wiki(tmp)
            questions = [
                {"id": "group-1-1", "title": "统计批注数量", "level": "简单"},
                {"id": "group-1-2", "title": "修复规则", "level": "中等"},
                {"id": "group-1-3", "title": "统计文件数量", "level": "简单"},
            ]
            answers = [
                {
                    "id": "group-1-1",
                    "answer": {"count": True},
                },
                {
                    "id": "group-1-2",
                    "answer": {"source": "docs/a.doc", "target": "output/fixed/../secret.doc"},
                },
                {
                    "id": "wrong-id",
                    "answer": {"made_up": 1},
                    "extra": "not allowed",
                },
            ]
            self._write_group(wiki, questions, answers)

            result, payload = self._run(wiki)

            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["ok"], False)
            codes = {error["code"] for error in payload["errors"]}
            self.assertIn("count_invalid", codes)
            self.assertIn("repair_target_invalid", codes)
            self.assertIn("answer_entry_schema_invalid", codes)

    def test_missing_target_duplicate_ids_and_answer_count_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wiki = self._wiki(tmp)
            questions = [
                {"id": "group-1-1", "title": "修复甲", "level": "困难"},
                {"id": "group-1-1", "title": "修复乙", "level": "困难"},
            ]
            answers = [
                {
                    "id": "group-1-1",
                    "answer": {"source": "docs/a.docx", "target": "output/fixed/missing.docx"},
                }
            ]
            self._write_group(wiki, questions, answers)

            result, payload = self._run(wiki)

            self.assertEqual(result.returncode, 1)
            codes = {error["code"] for error in payload["errors"]}
            self.assertIn("question_id_duplicate", codes)
            self.assertIn("answer_count_mismatch", codes)
            self.assertIn("repair_target_missing", codes)

    def test_question_markdown_is_supported_but_answer_must_be_plain_json_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wiki = self._wiki(tmp)
            question = {"id": "group-2-1", "title": "列出资料", "level": "简单"}
            (wiki / "question" / "group-2.md").write_text(
                "说明文字\n```json\n" + json.dumps([question], ensure_ascii=False) + "\n```\n",
                encoding="utf-8",
            )
            answer = {"id": question["id"], "answer": {"datas": []}}
            (wiki / "output" / "group-2-answer.md").write_text(
                "```json\n" + json.dumps([answer], ensure_ascii=False) + "\n```\n",
                encoding="utf-8",
            )

            result, payload = self._run(wiki)

            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["errors"][0]["code"], "answer_json_invalid")

    def test_summary_never_echoes_untrusted_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wiki = self._wiki(tmp)
            sentinel = "DO_NOT_LEAK_79f153_password"
            questions = [{"id": "group-3-1", "title": sentinel, "level": "困难"}]
            answers = [
                {
                    "id": "group-3-1",
                    "answer": {"source": "docs/a.docx", "target": f"output/fixed/{sentinel}.docx"},
                }
            ]
            (wiki / "question" / "group-3.md").write_text(
                json.dumps(questions, ensure_ascii=False), encoding="utf-8"
            )
            (wiki / "output" / "group-3-answer.md").write_text(
                json.dumps(answers, ensure_ascii=False), encoding="utf-8"
            )

            result, payload = self._run(wiki)

            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["errors"][0]["code"], "repair_target_missing")
            self.assertNotIn(sentinel, result.stdout)
            self.assertNotIn(sentinel, result.stderr)

    def test_missing_and_orphan_groups_fail_with_machine_readable_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wiki = self._wiki(tmp)
            question = {"id": "group-1-1", "title": "列出资料", "level": "简单"}
            (wiki / "question" / "group-1.md").write_text(json.dumps([question]), encoding="utf-8")
            (wiki / "output" / "group-old-answer.md").write_text("[]", encoding="utf-8")

            result, payload = self._run(wiki)

            self.assertEqual(result.returncode, 1)
            codes = {error["code"] for error in payload["errors"]}
            self.assertEqual(codes, {"orphan_answer_group", "answer_file_missing"})


if __name__ == "__main__":
    unittest.main()
