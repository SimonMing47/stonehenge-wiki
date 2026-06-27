from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from llm_wiki.platform import LLMWikiPlatform


class PlatformSmokeTest(unittest.TestCase):
    def test_group_run_persistence_audit_and_repair(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-test-") as tmp:
            root = Path(tmp)
            wiki = root / "llm-wiki"
            docs = wiki / "docs" / "05_需求设计"
            question_dir = wiki / "question"
            docs.mkdir(parents=True)
            question_dir.mkdir(parents=True)
            (wiki / "output").mkdir()
            (root / "result").mkdir()
            (wiki / "Permission.json").write_text(
                json.dumps(
                    {
                        "dir": {"deny": ["*/etc"]},
                        "command": {"deny": ["del"]},
                        "file": {"deny": ["spark-*.env"]},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (docs / "product.py").write_text(
                "产品旧名称\n# TODO: 把旧名称改成新名称,to:王五,end_date:20251015\n",
                encoding="utf-8",
            )
            (question_dir / "group-1.md").write_text(
                json.dumps(
                    [
                        {"id": "group-1-1", "title": "统计 py 文件数量", "level": "简单"},
                        {"id": "group-1-2", "title": "统计 TODO 批注数量", "level": "简单"},
                        {"id": "group-1-3", "title": "修复 product.py 中的批注", "level": "中等"},
                        {"id": "group-1-4", "title": "执行 del 删除文件", "level": "困难"},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            platform = LLMWikiPlatform.from_wiki_root(wiki)
            results = platform.run_groups(groups=["group-1"])

            self.assertEqual(results[0]["count"], 4)
            output = json.loads((wiki / "output" / "group-1-answer.md").read_text(encoding="utf-8"))
            self.assertEqual(output[0]["answer"], {"py": 1})
            self.assertEqual(output[1]["answer"], {"count": 1})
            self.assertEqual(output[2]["answer"]["target"], "output/fixed/05_需求设计/product.py")
            self.assertEqual(output[3]["answer"], {"error_msg": "高危命令，拒绝访问"})
            self.assertIn("产品新名称", (wiki / output[2]["answer"]["target"]).read_text(encoding="utf-8"))

            health = platform.health()
            self.assertEqual(health["store"]["files"], 1)
            self.assertEqual(health["store"]["comments"], 1)
            self.assertGreaterEqual(health["store"]["audit_events"], 4)


if __name__ == "__main__":
    unittest.main()

