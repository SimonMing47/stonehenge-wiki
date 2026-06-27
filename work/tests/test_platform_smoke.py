from __future__ import annotations

import json
import threading
import tempfile
import unittest
import urllib.request
import zipfile
from pathlib import Path

from llm_wiki.extractors import extract_docx
from llm_wiki.answerer import QuestionAnswerer
from llm_wiki.llm import LLMAnswer, build_context
from llm_wiki.indexer import WikiIndex
from llm_wiki.models import Question
from llm_wiki.office_bridge import convert_office, has_soffice
from llm_wiki.platform import LLMWikiPlatform
from llm_wiki.security import PermissionGuard
from llm_wiki.server import build_server


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

    def test_compile_and_lint_markdown_wiki_layer(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-compile-test-") as tmp:
            root = Path(tmp)
            wiki = root / "llm-wiki"
            docs = wiki / "docs" / "04_常用命令"
            docs.mkdir(parents=True)
            (wiki / "question").mkdir(parents=True)
            (wiki / "output").mkdir()
            (root / "result").mkdir()
            (wiki / "Permission.json").write_text("{}", encoding="utf-8")
            (docs / "gauss.md").write_text(
                "高斯数据库连接命令：gsql -h 127.0.0.1 -p 8000 -U app\n"
                "# TODO: 补充只读账号,to:张三,end_date:20260101\n",
                encoding="utf-8",
            )

            platform = LLMWikiPlatform.from_wiki_root(wiki)
            compiled = platform.compile_wiki()
            lint = platform.lint_wiki()

            self.assertEqual(compiled["source_pages"], 1)
            self.assertEqual(lint["status"], "ok")
            self.assertTrue((wiki / "wiki" / "index.md").exists())
            self.assertTrue((wiki / "wiki" / "log.md").exists())
            source_pages = list((wiki / "wiki" / "sources").glob("*.md"))
            self.assertEqual(len(source_pages), 1)
            source_text = source_pages[0].read_text(encoding="utf-8")
            self.assertIn("source_path:", source_text)
            self.assertIn("Comments And TODOs", source_text)

    def test_http_console_assets_and_health(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-web-test-") as tmp:
            root = Path(tmp)
            wiki = root / "llm-wiki"
            (wiki / "docs").mkdir(parents=True)
            (wiki / "question").mkdir()
            (wiki / "output").mkdir()
            (root / "result").mkdir()
            (wiki / "Permission.json").write_text("{}", encoding="utf-8")

            platform = LLMWikiPlatform.from_wiki_root(wiki)
            httpd = build_server(platform, "127.0.0.1", 0)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{httpd.server_address[1]}"
                index_html = http_get(base + "/")
                app_js = http_get(base + "/assets/app.js")
                health = json.loads(http_get(base + "/health"))
                lint = json.loads(http_get(base + "/wiki/lint"))
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)

            self.assertIn("LLM Wiki Control Plane", index_html)
            self.assertIn("refreshAll", app_js)
            self.assertEqual(health["status"], "ok")
            self.assertIn(lint["status"], {"ok", "error"})

    def test_knowledge_answers_use_llm_without_sending_password_queries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-llm-test-") as tmp:
            root = Path(tmp)
            wiki = root / "llm-wiki"
            docs = wiki / "docs" / "02_环境信息"
            docs.mkdir(parents=True)
            (wiki / "Permission.json").write_text("{}", encoding="utf-8")
            (docs / "gauss.md").write_text(
                "连接命令: gsql -h gaussdb.demo.local -p 8000 -U wiki_reader -d knowledge\n"
                "数据库密码: env-secret\n",
                encoding="utf-8",
            )

            llm = FakeLLMClient()
            answerer = QuestionAnswerer(WikiIndex(wiki).build(), PermissionGuard(wiki), llm)
            normal = answerer.answer(Question("q1", "如何在控制台连接高斯数据库", "中等"))
            secret = answerer.answer(Question("q2", "数据库密码是什么", "困难"))

            self.assertIn("llm:fake/fake-model", normal["answer"]["datas"])
            self.assertEqual(llm.calls, ["如何在控制台连接高斯数据库"])
            self.assertIn("数据库密码: env-secret", "\n".join(secret["answer"]["datas"]))

    def test_llm_context_redacts_secret_values(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-redact-test-") as tmp:
            root = Path(tmp)
            record = make_document_record(
                root,
                "docs/02_环境信息/gauss.md",
                "连接命令: gsql -h gaussdb.demo.local -U wiki_reader\n数据库密码: env-secret\nAPI_KEY=abc123\n",
            )
            context = build_context(
                [record],
                ["docs/02_环境信息/gauss.md: password=snippet-secret"],
                max_chars=4000,
            )

            self.assertIn("gsql -h gaussdb.demo.local", context)
            self.assertIn("[REDACTED]", context)
            self.assertNotIn("env-secret", context)
            self.assertNotIn("abc123", context)
            self.assertNotIn("snippet-secret", context)

    def test_llm_failure_falls_back_to_deterministic_snippets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-fallback-test-") as tmp:
            root = Path(tmp)
            wiki = root / "llm-wiki"
            docs = wiki / "docs" / "04_常用命令"
            docs.mkdir(parents=True)
            (wiki / "Permission.json").write_text("{}", encoding="utf-8")
            (docs / "database.md").write_text(
                "sqlite-select: SELECT * FROM documents WHERE topic = 'rag';\n",
                encoding="utf-8",
            )

            answerer = QuestionAnswerer(WikiIndex(wiki).build(), PermissionGuard(wiki), FailingLLMClient())
            answer = answerer.answer(Question("q1", "SQLite SELECT 命令是什么", "中等"))

            text = "\n".join(answer["answer"]["datas"])
            self.assertIn("SELECT * FROM documents", text)
            self.assertNotIn("llm:", text)

    @unittest.skipUnless(has_soffice(), "LibreOffice/soffice is not installed")
    def test_legacy_doc_repair_via_libreoffice_bridge(self) -> None:
        with tempfile.TemporaryDirectory(prefix="llm-wiki-legacy-test-") as tmp:
            root = Path(tmp)
            source_docx = root / "source.docx"
            make_minimal_docx(
                source_docx,
                "产品旧名称\nTODO: 把旧名称改成新名称,to:王五,end_date:20251015",
            )
            legacy_doc = convert_office(source_docx, "doc", root / "converted")
            self.assertIsNotNone(legacy_doc)

            wiki = root / "llm-wiki"
            docs = wiki / "docs" / "05_需求设计"
            question_dir = wiki / "question"
            docs.mkdir(parents=True)
            question_dir.mkdir(parents=True)
            (wiki / "output").mkdir()
            (root / "result").mkdir()
            (wiki / "Permission.json").write_text("{}", encoding="utf-8")
            target_source = docs / "legacy.doc"
            target_source.write_bytes(Path(legacy_doc).read_bytes())
            (question_dir / "group-legacy.md").write_text(
                json.dumps(
                    [{"id": "group-legacy-1", "title": "修复 legacy.doc 中的批注", "level": "困难"}],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            platform = LLMWikiPlatform.from_wiki_root(wiki)
            platform.run_groups(groups=["group-legacy"])
            fixed_doc = wiki / "output" / "fixed" / "05_需求设计" / "legacy.doc"
            self.assertTrue(fixed_doc.exists())

            fixed_docx = convert_office(fixed_doc, "docx", root / "verified")
            self.assertIsNotNone(fixed_docx)
            text, _ = extract_docx(Path(fixed_docx), "docs/05_需求设计/legacy.doc")
            self.assertIn("产品新名称", text)

def make_minimal_docx(path: Path, text: str) -> None:
    paragraphs = "".join(f"<w:p><w:r><w:t>{escape_xml(line)}</w:t></w:r></w:p>" for line in text.splitlines())
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        zf.writestr(
            "word/document.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>{paragraphs}</w:body>
</w:document>""",
        )


def escape_xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def http_get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def make_document_record(root: Path, rel_path: str, text: str):
    from llm_wiki.models import DocumentRecord

    full_path = root / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(text, encoding="utf-8")
    return DocumentRecord(full_path, rel_path, full_path.suffix.lstrip("."), text)


class FakeLLMClient:
    provider = "fake"
    model = "fake-model"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def answer(self, question, records, snippets):
        self.calls.append(question)
        return LLMAnswer(
            text="LLM synthesized answer",
            provider=self.provider,
            model=self.model,
            sources=[record.rel_path for record in records],
        )


class FailingLLMClient:
    def answer(self, question, records, snippets):
        raise RuntimeError("simulated llm outage")


if __name__ == "__main__":
    unittest.main()
