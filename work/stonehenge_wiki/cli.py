from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from .platform import StonehengeWikiPlatform
from .readiness import readiness_exit_code
from .server import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=os.environ.get("STONEHENGE_WIKI_CLI_NAME") or None,
        description="Enterprise Stonehenge Wiki platform CLI",
    )
    parser.add_argument("--wiki-root", type=Path, default=default_wiki_root(), help="Path to stonehenge-wiki directory")
    parser.add_argument("--question", type=Path, action="append", help="Question group file path")
    parser.add_argument("--group", action="append", help="Group stem such as group-1")
    parser.add_argument("--ask", help="Answer one ad-hoc question and print JSON to stdout")
    parser.add_argument("--explain-ask", help="Print retrieval and safety evidence for one ad-hoc question")
    parser.add_argument("--dump-index", action="store_true", help="Print indexed paths/comments as JSON")
    parser.add_argument("--list-sources", action="store_true", help="Print source registry records as JSON")
    parser.add_argument("--include-missing-sources", action="store_true", help="Include missing source registry records")
    parser.add_argument("--list-source-versions", action="store_true", help="Print source version history records as JSON")
    parser.add_argument("--source-history", help="Print version history for one source registry path")
    parser.add_argument("--source-history-limit", type=int, default=50, help="Version record count for source history")
    parser.add_argument("--source-risk-report", action="store_true", help="Print source risk scan report as JSON")
    parser.add_argument("--list-source-reviews", action="store_true", help="Print source review events as JSON")
    parser.add_argument("--source-review-path", help="Filter source review events by path")
    parser.add_argument("--set-source-status", help="Set source status for one registry path")
    parser.add_argument("--source-status", choices=["active", "quarantined"], help="Status for --set-source-status")
    parser.add_argument("--source-status-reason", default="", help="Reason for --set-source-status")
    parser.add_argument("--source-status-actor", default="cli", help="Actor for --set-source-status")
    parser.add_argument("--list-wiki-sections", action="store_true", help="Print compiled wiki sections as JSON")
    parser.add_argument("--wiki-section-source", help="Filter compiled wiki sections by source registry path")
    parser.add_argument("--wiki-section-limit", type=int, default=50, help="Compiled wiki section count")
    parser.add_argument("--search-wiki", help="Search the compiled Markdown wiki layer")
    parser.add_argument("--reindex", action="store_true", help="Rebuild and persist the wiki index")
    parser.add_argument("--import-source", help="Import a local file or public URL into docs/00_inbox")
    parser.add_argument("--import-title", default="", help="Optional title used for the imported filename")
    parser.add_argument("--import-category", default="00_inbox", help="Target docs category for --import-source")
    parser.add_argument("--compile-wiki", action="store_true", help="Compile docs into the Markdown wiki layer")
    parser.add_argument("--lint-wiki", action="store_true", help="Validate the compiled Markdown wiki layer")
    parser.add_argument("--generate-ppt", help="Generate a PPTX brief for a topic")
    parser.add_argument("--slide-count", type=int, default=6, help="Slide count for --generate-ppt")
    parser.add_argument("--audit-log", action="store_true", help="Print recent audit events")
    parser.add_argument("--audit-limit", type=int, default=50, help="Audit event count for --audit-log")
    parser.add_argument("--governance-report", action="store_true", help="Print governance report JSON")
    parser.add_argument("--export-governance-report", action="store_true", help="Write governance report Markdown")
    parser.add_argument("--evaluation-report", action="store_true", help="Evaluate question groups and print a quality report")
    parser.add_argument("--export-evaluation-report", action="store_true", help="Write question evaluation reports")
    parser.add_argument("--readiness-report", action="store_true", help="Print enterprise readiness gates as JSON")
    parser.add_argument("--export-readiness-report", action="store_true", help="Write enterprise readiness report files")
    parser.add_argument("--readiness-fail-on", choices=["never", "fail", "warn"], default="never", help="Return exit code 2 when readiness reaches this severity")
    parser.add_argument("--export-release-bundle", action="store_true", help="Write a metadata-only enterprise release bundle")
    parser.add_argument("--release-include-evaluation", action="store_true", help="Include a freshly generated evaluation report in the release bundle")
    parser.add_argument("--serve", action="store_true", help="Start the HTTP API service")
    parser.add_argument("--host", help="HTTP API host override")
    parser.add_argument("--port", type=int, help="HTTP API port override")
    parser.add_argument("--self-test", action="store_true", help="Run a built-in smoke test in a temporary wiki")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    wiki_root = args.wiki_root.resolve()
    if args.serve:
        serve(wiki_root, host=args.host, port=args.port)
        return 0

    platform = StonehengeWikiPlatform.from_wiki_root(wiki_root)

    if args.reindex:
        print_json(platform.rebuild_index())
        return 0

    if args.import_source:
        print_json(platform.ingest_source(args.import_source, title=args.import_title, category=args.import_category))
        return 0

    if args.compile_wiki:
        print_json(platform.compile_wiki())
        return 0

    if args.lint_wiki:
        print_json(platform.lint_wiki())
        return 0

    if args.dump_index:
        print_json(platform.dump_index())
        return 0

    if args.list_sources:
        print_json({"sources": platform.list_sources(include_missing=args.include_missing_sources)})
        return 0

    if args.list_source_versions:
        print_json({"versions": platform.list_source_versions(limit=args.source_history_limit)})
        return 0

    if args.source_history:
        print_json({"versions": platform.list_source_versions(rel_path=args.source_history, limit=args.source_history_limit)})
        return 0

    if args.source_risk_report:
        print_json(platform.source_risk_report())
        return 0

    if args.list_source_reviews:
        print_json({"reviews": platform.list_source_reviews(rel_path=args.source_review_path, limit=args.source_history_limit)})
        return 0

    if args.set_source_status:
        print_json(
            platform.set_source_status(
                args.set_source_status,
                args.source_status or "active",
                reason=args.source_status_reason,
                actor=args.source_status_actor,
            )
        )
        return 0

    if args.list_wiki_sections:
        print_json(
            {
                "sections": platform.list_wiki_sections(
                    source_path=args.wiki_section_source,
                    limit=args.wiki_section_limit,
                )
            }
        )
        return 0

    if args.search_wiki:
        print_json(platform.search_wiki(args.search_wiki, limit=args.wiki_section_limit))
        return 0

    if args.audit_log:
        print_json({"events": platform.audit_events(args.audit_limit)})
        return 0

    if args.governance_report:
        print_json(platform.governance_report())
        return 0

    if args.export_governance_report:
        print_json(platform.export_governance_report())
        return 0

    if args.evaluation_report:
        print_json(platform.evaluation_report(explicit_files=args.question, groups=args.group))
        return 0

    if args.export_evaluation_report:
        print_json(platform.export_evaluation_report(explicit_files=args.question, groups=args.group))
        return 0

    if args.readiness_report:
        result = platform.readiness_report(explicit_files=args.question, groups=args.group)
        print_json(result)
        return readiness_exit_code(result["report"]["summary"], args.readiness_fail_on)

    if args.export_readiness_report:
        result = platform.export_readiness_report(explicit_files=args.question, groups=args.group)
        print_json(result)
        return readiness_exit_code(result["report"]["summary"], args.readiness_fail_on)

    if args.export_release_bundle:
        print_json(
            platform.export_release_bundle(
                explicit_files=args.question,
                groups=args.group,
                include_evaluation=args.release_include_evaluation,
            )
        )
        return 0

    if args.ask:
        print_json(platform.ask(args.ask))
        return 0

    if args.explain_ask:
        print_json(platform.explain_question(args.explain_ask))
        return 0

    if args.generate_ppt:
        print_json(platform.generate_presentation(args.generate_ppt, slide_count=args.slide_count))
        return 0

    platform.run_groups(explicit_files=args.question, groups=args.group)
    return 0


def default_wiki_root() -> Path:
    return Path(__file__).resolve().parents[2] / "stonehenge-wiki"


def print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="stonehenge-wiki-selftest-") as tmp:
        root = Path(tmp)
        wiki = root / "stonehenge-wiki"
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
        print_json(StonehengeWikiPlatform.from_wiki_root(wiki).health())
        return code


if __name__ == "__main__":
    raise SystemExit(main())
