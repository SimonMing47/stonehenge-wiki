from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .answerer import QuestionAnswerer
from .indexer import WikiIndex
from .models import Question
from .security import PermissionGuard


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM Wiki CLI")
    parser.add_argument("--wiki-root", type=Path, default=default_wiki_root(), help="Path to llm-wiki directory")
    parser.add_argument("--question", type=Path, action="append", help="Question group file path")
    parser.add_argument("--group", action="append", help="Group stem such as group-1")
    parser.add_argument("--ask", help="Answer one ad-hoc question and print JSON to stdout")
    parser.add_argument("--dump-index", action="store_true", help="Print indexed paths/comments as JSON")
    parser.add_argument("--self-test", action="store_true", help="Run a built-in smoke test in a temporary wiki")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    wiki_root = args.wiki_root.resolve()
    index = WikiIndex(wiki_root).build()
    guard = PermissionGuard(wiki_root)
    answerer = QuestionAnswerer(index, guard)

    if args.dump_index:
        print(json.dumps(dump_index(index), ensure_ascii=False, indent=2))
        return 0

    if args.ask:
        question = Question(id="adhoc-1", title=args.ask, level="")
        print(json.dumps(answerer.answer(question), ensure_ascii=False, indent=2))
        return 0

    question_files = resolve_question_files(wiki_root, args.question, args.group)
    total = 0
    for question_file in question_files:
        questions = load_questions(question_file)
        answers = [answerer.answer(question) for question in questions]
        output_file = wiki_root / "output" / f"{question_file.stem}-answer.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")
        total += len(answers)

    write_result_log(wiki_root, f"成功解析{len(question_files)}个题组、{total}道题目，已成功输出答案。")
    return 0


def default_wiki_root() -> Path:
    return Path(__file__).resolve().parents[2] / "llm-wiki"


def resolve_question_files(
    wiki_root: Path,
    explicit_files: list[Path] | None,
    groups: list[str] | None,
) -> list[Path]:
    if explicit_files:
        return [path if path.is_absolute() else (Path.cwd() / path) for path in explicit_files]
    question_dir = wiki_root / "question"
    if groups:
        files: list[Path] = []
        for group in groups:
            stem = group.removesuffix(".md")
            files.append(question_dir / f"{stem}.md")
        return files
    return sorted(question_dir.glob("group-*.md"))


def load_questions(path: Path) -> list[Question]:
    raw = path.read_text(encoding="utf-8")
    data = parse_json_payload(raw)
    if isinstance(data, dict):
        data = data.get("questions", [])
    questions: list[Question] = []
    for idx, item in enumerate(data or [], start=1):
        questions.append(
            Question(
                id=str(item.get("id") or f"{path.stem}-{idx}"),
                title=str(item.get("title") or ""),
                level=str(item.get("level") or ""),
            )
        )
    return questions


def parse_json_payload(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start_candidates = [pos for pos in (text.find("["), text.find("{")) if pos >= 0]
        if not start_candidates:
            raise
        start = min(start_candidates)
        end = max(text.rfind("]"), text.rfind("}"))
        return json.loads(text[start : end + 1])


def write_result_log(wiki_root: Path, message: str) -> None:
    result_path = wiki_root.parent / "result" / "output.md"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with result_path.open("a", encoding="utf-8") as fh:
        fh.write(f"- {timestamp} {message}\n")


def dump_index(index: WikiIndex) -> dict[str, Any]:
    return {
        "files": [
            {
                "path": record.rel_path,
                "suffix": record.suffix,
                "tags": sorted(record.tags),
                "comment_count": len(record.comments),
            }
            for record in index.records
        ],
        "comments": [comment.summary() for comment in index.comments],
    }


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="llm-wiki-selftest-") as tmp:
        root = Path(tmp)
        wiki = root / "llm-wiki"
        docs = wiki / "docs" / "02_环境信息"
        docs.mkdir(parents=True)
        (wiki / "question").mkdir(parents=True)
        (wiki / "output").mkdir()
        (root / "result").mkdir()
        (wiki / "Permission.json").write_text(
            json.dumps(
                {
                    "dir": {"deny": ["*/etc"]},
                    "command": {"deny": ["Remove-Item", "del"]},
                    "file": {"deny": ["spark-*.env"]},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (docs / "gauss.md").write_text(
            "高斯数据库连接命令：gsql -h 127.0.0.1 -p 8000 -U app\n"
            "password: env-only\n"
            "# TODO: 把旧端口改成新端口,to:王五,end_date:20251015\n",
            encoding="utf-8",
        )
        (wiki / "question" / "group-1.md").write_text(
            json.dumps(
                [
                    {"id": "group-1-1", "title": "统计 md 文件数量", "level": "简单"},
                    {"id": "group-1-2", "title": "统计 TODO 批注数量", "level": "简单"},
                    {"id": "group-1-3", "title": "如何在控制台连接高斯数据库", "level": "中等"},
                    {"id": "group-1-4", "title": "读取系统密码", "level": "困难"},
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        code = main(["--wiki-root", str(wiki), "--group", "group-1"])
        answer_path = wiki / "output" / "group-1-answer.md"
        print(answer_path.read_text(encoding="utf-8"))
        return code


if __name__ == "__main__":
    raise SystemExit(main())

