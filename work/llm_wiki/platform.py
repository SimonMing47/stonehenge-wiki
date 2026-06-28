from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .answerer import QuestionAnswerer
from .cli_io import load_questions, output_path_for_question_file, resolve_question_files, write_result_log
from .config import PlatformConfig, load_config
from .evaluation import build_evaluation_report
from .indexer import WikiIndex
from .importer import SourceImportError, import_source
from .llm import LLMClient
from .models import Question
from .presentations import create_presentation
from .reports import build_governance_report
from .security import PermissionGuard
from .source_risk import MANDATORY_QUARANTINE_CODES, scan_source_risks
from .store import SQLiteStore
from .wiki_compiler import WikiCompiler


class LLMWikiPlatform:
    def __init__(self, wiki_root: Path, config: PlatformConfig | None = None):
        self.config = config or load_config(wiki_root)
        self.wiki_root = self.config.wiki_root
        self.full_index = WikiIndex(self.wiki_root).build()
        self.guard = PermissionGuard(self.wiki_root)
        self.llm_client = LLMClient(self.config.llm) if self.config.llm.enabled else None
        self.store = SQLiteStore(self.config.database_path)
        policy_result: dict[str, Any] = {"quarantined": []}
        if self.config.persist_index:
            self.store.save_index(self.full_index)
            policy_result = self.apply_source_policy_quarantine()
        self.index = self.active_index()
        self.answerer = QuestionAnswerer(self.index, self.guard, self.llm_client)
        if self.config.persist_index:
            if policy_result.get("quarantined"):
                self.compiler.compile()
            self.store.save_wiki_sections(self.wiki_root / "wiki")

    @property
    def compiler(self) -> WikiCompiler:
        return WikiCompiler(self.wiki_root, self.index)

    @classmethod
    def from_wiki_root(cls, wiki_root: Path) -> "LLMWikiPlatform":
        return cls(wiki_root)

    def rebuild_index(self) -> dict[str, Any]:
        self.full_index.build()
        policy_result: dict[str, Any] = {"quarantined": []}
        if self.config.persist_index:
            self.store.save_index(self.full_index)
            policy_result = self.apply_source_policy_quarantine()
        self.refresh_runtime_index()
        if self.config.persist_index and policy_result.get("quarantined"):
            self.compiler.compile()
            self.store.save_wiki_sections(self.wiki_root / "wiki")
        elif self.config.persist_index:
            self.store.save_wiki_sections(self.wiki_root / "wiki")
        result = self.health()
        self.store.record_job("reindex", "ok", {"wiki_root": str(self.wiki_root)}, result)
        return result

    def compile_wiki(self) -> dict[str, Any]:
        result = self.compiler.compile()
        if self.config.persist_index:
            self.store.save_wiki_sections(self.wiki_root / "wiki")
            result["wiki_sections"] = self.store.stats()["wiki_sections"]
        self.store.record_job("wiki_compile", "ok", {"wiki_root": str(self.wiki_root)}, result)
        self.audit(
            event_type="wiki.compile",
            request_id=new_request_id(),
            subject="wiki",
            status="ok",
            payload=result,
        )
        return result

    def lint_wiki(self) -> dict[str, Any]:
        result = self.compiler.lint()
        self.store.record_job("wiki_lint", result["status"], {"wiki_root": str(self.wiki_root)}, result)
        self.audit(
            event_type="wiki.lint",
            request_id=new_request_id(),
            subject="wiki",
            status=result["status"],
            blocked=result["status"] == "error",
            payload=result,
        )
        return result

    def answer_question(self, question: Question, request_id: str | None = None) -> dict[str, Any]:
        request_id = request_id or new_request_id()
        answer = self.answerer.answer(question)
        blocked = "error_msg" in answer.get("answer", {})
        self.audit(
            event_type="question.answer",
            request_id=request_id,
            subject=question.id,
            status="blocked" if blocked else "ok",
            blocked=blocked,
            payload={"title": question.title, "answer": answer.get("answer")},
        )
        return answer

    def ask(self, title: str, q_id: str = "adhoc-1", level: str = "") -> dict[str, Any]:
        return self.answer_question(Question(id=q_id, title=title, level=level))

    def explain_question(self, title: str, q_id: str = "explain-1", level: str = "") -> dict[str, Any]:
        result = self.answerer.explain(Question(id=q_id, title=title, level=level))
        wiki_match = self.search_wiki(title, limit=8)
        result["wiki"] = {
            "mode": "compiled_wiki",
            "sections": wiki_match["sections"],
            "section_count": len(wiki_match["sections"]),
        }
        self.store.record_job(
            "question_explain",
            result["status"],
            {"id": q_id, "title": title, "level": level},
            result,
        )
        self.audit(
            event_type="question.explain",
            request_id=new_request_id(),
            subject=q_id,
            status=result["status"],
            blocked=result["status"] == "blocked",
            payload={"title": title, "route": result.get("route"), "records": result.get("records", [])[:5]},
        )
        return result

    def ingest_source(self, source: str, title: str = "", category: str = "00_inbox") -> dict[str, Any]:
        request_id = new_request_id()
        try:
            imported = import_source(self.wiki_root, source, self.guard, title=title, category=category)
        except SourceImportError as exc:
            result = {"error_msg": str(exc), "reason": exc.reason}
            self.audit("source.import", request_id, source or "source", "blocked", True, result)
            self.store.record_job("source_import", "blocked", {"source": source, "title": title, "category": category}, result)
            return result

        self.store.record_source_provenance(
            imported.rel_path,
            imported.source_type,
            imported.source,
            title or Path(imported.rel_path).stem,
            category,
            imported.sha256,
            imported.size,
        )
        health = self.rebuild_index()
        result = {
            "status": "ok",
            "source": imported.source,
            "source_type": imported.source_type,
            "path": imported.rel_path,
            "size": imported.size,
            "sha256": imported.sha256,
            "files": health["files"],
            "comments": health["comments"],
            "registry_status": "active",
        }
        self.store.record_job("source_import", "ok", {"source": source, "title": title, "category": category}, result)
        self.audit("source.import", request_id, imported.rel_path, "ok", False, result)
        return result

    def generate_presentation(self, topic: str, slide_count: int = 6) -> dict[str, Any]:
        request_id = new_request_id()
        blocked, reason = self.guard.check_question(topic)
        if blocked:
            result = {"error_msg": "高危命令，拒绝访问", "reason": reason}
            self.audit("slides.generate", request_id, topic or "presentation", "blocked", True, result)
            return result

        records = self.index.search(topic, limit=8)
        answer = self.answer_question(Question(id="slides-brief", title=topic, level="中等"), request_id=request_id)
        answer_datas = list(answer.get("answer", {}).get("datas", []) or [])
        deck_rel, slides = create_presentation(self.wiki_root, topic, answer_datas, records, slide_count=slide_count)
        result = {
            "status": "ok",
            "topic": topic,
            "deck": deck_rel,
            "download_url": "/files/" + quote(deck_rel, safe="/"),
            "slide_count": len(slides),
            "sources": [record.rel_path for record in records],
        }
        self.store.record_job("slides_generate", "ok", {"topic": topic}, result)
        self.audit("slides.generate", request_id, deck_rel, "ok", False, result)
        return result

    def run_group_file(self, question_file: Path) -> dict[str, Any]:
        questions = load_questions(question_file)
        request_id = new_request_id()
        answers = [self.answer_question(question, request_id=request_id) for question in questions]
        output_file = output_path_for_question_file(self.wiki_root, question_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")
        result = {
            "question_file": str(question_file),
            "output_file": str(output_file),
            "count": len(answers),
            "answers": answers,
        }
        self.store.record_job("question_group", "ok", {"question_file": str(question_file)}, result)
        return result

    def run_groups(
        self,
        explicit_files: list[Path] | None = None,
        groups: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        question_files = resolve_question_files(self.wiki_root, explicit_files, groups)
        results = [self.run_group_file(question_file) for question_file in question_files]
        total = sum(result["count"] for result in results)
        write_result_log(self.wiki_root, f"成功解析{len(question_files)}个题组、{total}道题目，已成功输出答案。")
        return results

    def evaluation_report(
        self,
        explicit_files: list[Path] | None = None,
        groups: list[str] | None = None,
    ) -> dict[str, Any]:
        question_files = resolve_question_files(self.wiki_root, explicit_files, groups)
        batches = [(question_file, load_questions(question_file)) for question_file in question_files]
        report = build_evaluation_report(
            self.health(),
            batches,
            self.answerer.answer,
            self.answerer.explain,
        )
        result = {"status": "ok", "report": without_markdown(report)}
        self.store.record_job(
            "evaluation_report",
            report["summary"]["status"],
            {"question_files": [str(path) for path in question_files]},
            result,
        )
        self.audit(
            "evaluation.report",
            new_request_id(),
            "evaluation",
            report["summary"]["status"],
            report["summary"]["status"] != "ok",
            {"summary": report["summary"], "risks": report["risks"]},
        )
        return result

    def export_evaluation_report(
        self,
        explicit_files: list[Path] | None = None,
        groups: list[str] | None = None,
    ) -> dict[str, Any]:
        question_files = resolve_question_files(self.wiki_root, explicit_files, groups)
        batches = [(question_file, load_questions(question_file)) for question_file in question_files]
        report = build_evaluation_report(
            self.health(),
            batches,
            self.answerer.answer,
            self.answerer.explain,
        )
        output_dir = self.wiki_root / "output" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_target = output_dir / "evaluation-report.md"
        json_target = output_dir / "evaluation-report.json"
        markdown_target.write_text(report["markdown"], encoding="utf-8")
        json_target.write_text(json.dumps(without_markdown(report), ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_rel = markdown_target.relative_to(self.wiki_root).as_posix()
        json_rel = json_target.relative_to(self.wiki_root).as_posix()
        result = {
            "status": "ok",
            "report": without_markdown(report),
            "path": markdown_rel,
            "json_path": json_rel,
            "download_url": "/files/" + quote(markdown_rel, safe="/"),
            "json_download_url": "/files/" + quote(json_rel, safe="/"),
        }
        self.store.record_job(
            "evaluation_report_export",
            report["summary"]["status"],
            {"question_files": [str(path) for path in question_files]},
            result,
        )
        self.audit(
            "evaluation.report",
            new_request_id(),
            markdown_rel,
            report["summary"]["status"],
            report["summary"]["status"] != "ok",
            {"summary": report["summary"], "risks": report["risks"]},
        )
        return result

    def dump_index(self) -> dict[str, Any]:
        source_risk_report = self.source_risk_report()
        risk_by_path = {item["source_path"]: item for item in source_risk_report["sources"]}
        return {
            "files": [
                {
                    "path": record.rel_path,
                    "suffix": record.suffix,
                    "tags": sorted(record.tags),
                    "comment_count": len(record.comments),
                    "risk": risk_by_path.get(record.rel_path, {"risk_count": 0, "max_severity": "none", "codes": []}),
                }
                for record in self.full_index.records
            ],
            "comments": [comment.summary() for comment in self.index.comments],
            "presentations": self.list_presentations(),
            "source_registry": self.list_sources(),
            "source_risks": source_risk_report,
            "store": self.store.stats(),
        }

    def list_sources(self, include_missing: bool = False) -> list[dict[str, Any]]:
        return self.store.list_sources(include_missing=include_missing)

    def list_source_versions(self, rel_path: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list_source_versions(rel_path=rel_path, limit=limit)

    def list_source_reviews(self, rel_path: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list_source_reviews(rel_path=rel_path, limit=limit)

    def set_source_status(
        self,
        rel_path: str,
        status: str,
        reason: str = "",
        actor: str = "api",
    ) -> dict[str, Any]:
        request_id = new_request_id()
        normalized_status = status.strip().lower()
        if normalized_status not in {"active", "quarantined"}:
            result = {"error": "invalid_status", "allowed": ["active", "quarantined"]}
            self.audit("source.review", request_id, rel_path, "blocked", True, result)
            return result
        if normalized_status == "active":
            policy_reason = self.source_policy_quarantine_reason(rel_path)
            if policy_reason:
                result = {
                    "error": "policy_quarantine_required",
                    "path": rel_path,
                    "reason": policy_reason,
                }
                self.audit("source.review", request_id, rel_path, "blocked", True, result)
                return result
        updated = self.store.update_source_status(rel_path, normalized_status, reason=reason, actor=actor)
        if updated is None:
            result = {"error": "not_found", "path": rel_path}
            self.audit("source.review", request_id, rel_path, "blocked", True, result)
            return result

        self.refresh_runtime_index()
        compile_result = self.compile_wiki()
        result = {
            "status": "ok",
            "path": rel_path,
            "source_status": normalized_status,
            "reason": reason,
            "actor": actor,
            "active_files": len(self.index.records),
            "all_files": len(self.full_index.records),
            "wiki_sections": compile_result.get("wiki_sections", 0),
        }
        self.store.record_job(
            "source_review",
            "ok",
            {"path": rel_path, "status": normalized_status, "reason": reason, "actor": actor},
            result,
        )
        self.audit("source.review", request_id, rel_path, "ok", False, result)
        return result

    def list_wiki_sections(self, source_path: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list_wiki_sections(source_path=source_path, limit=limit)

    def search_wiki(self, query: str, limit: int = 10) -> dict[str, Any]:
        return {
            "status": "ok",
            "query": query,
            "sections": self.store.search_wiki_sections(query, limit=limit),
        }

    def source_risk_report(self) -> dict[str, Any]:
        return scan_source_risks(self.full_index, self.guard)

    def source_policy_quarantine_reason(self, rel_path: str) -> str:
        risk_report = self.source_risk_report()
        codes = {
            str(finding.get("code") or "")
            for finding in risk_report.get("findings", [])
            if finding.get("source_path") == rel_path
        }
        mandatory = sorted(codes & MANDATORY_QUARANTINE_CODES)
        return ",".join(mandatory)

    def apply_source_policy_quarantine(self) -> dict[str, Any]:
        risk_report = self.source_risk_report()
        current = {
            source["rel_path"]: source
            for source in self.store.list_sources(include_missing=True)
            if source.get("status") != "missing"
        }
        by_path: dict[str, set[str]] = {}
        for finding in risk_report.get("findings", []):
            code = str(finding.get("code") or "")
            if code not in MANDATORY_QUARANTINE_CODES:
                continue
            rel_path = str(finding.get("source_path") or "")
            if not rel_path:
                continue
            by_path.setdefault(rel_path, set()).add(code)

        quarantined: list[dict[str, Any]] = []
        for rel_path, codes in sorted(by_path.items()):
            source = current.get(rel_path)
            if not source or source.get("status") == "quarantined":
                continue
            reason = "policy:" + ",".join(sorted(codes))
            updated = self.store.update_source_status(rel_path, "quarantined", reason=reason, actor="policy")
            if updated:
                quarantined.append({"path": rel_path, "reason": reason})

        result = {
            "status": "ok",
            "quarantined": quarantined,
            "count": len(quarantined),
        }
        if quarantined:
            self.store.record_job("source_policy_quarantine", "ok", {"codes": sorted(MANDATORY_QUARANTINE_CODES)}, result)
            self.audit("source.policy", new_request_id(), "source_registry", "ok", False, result)
        return result

    def governance_report(self) -> dict[str, Any]:
        source_risk_report = self.source_risk_report()
        report = build_governance_report(
            self.health(),
            self.list_sources(include_missing=True),
            self.full_index.comments,
            self.audit_events(100),
            self.store.list_jobs(50),
            source_risk_report=source_risk_report,
        )
        return {"status": "ok", "report": report.as_dict()}

    def export_governance_report(self) -> dict[str, Any]:
        source_risk_report = self.source_risk_report()
        report = build_governance_report(
            self.health(),
            self.list_sources(include_missing=True),
            self.full_index.comments,
            self.audit_events(100),
            self.store.list_jobs(50),
            source_risk_report=source_risk_report,
        )
        output_dir = self.wiki_root / "output" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / "governance-report.md"
        target.write_text(report.markdown, encoding="utf-8")
        rel = target.relative_to(self.wiki_root).as_posix()
        result = {
            "status": "ok",
            "report": report.as_dict(),
            "path": rel,
            "download_url": "/files/" + quote(rel, safe="/"),
        }
        self.store.record_job("governance_report", "ok", {"wiki_root": str(self.wiki_root)}, result)
        self.audit("governance.report", new_request_id(), rel, "ok", False, {"summary": report.summary})
        return result

    def list_presentations(self) -> list[dict[str, Any]]:
        output_dir = self.wiki_root / "output" / "presentations"
        if not output_dir.exists():
            return []
        decks = []
        for path in sorted(output_dir.glob("*.pptx"), key=lambda item: item.stat().st_mtime, reverse=True):
            rel = path.relative_to(self.wiki_root).as_posix()
            decks.append(
                {
                    "deck": rel,
                    "name": path.name,
                    "download_url": "/files/" + quote(rel, safe="/"),
                    "size": path.stat().st_size,
                }
            )
        return decks[:10]

    def audit_events(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list_audit_events(limit)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "wiki_root": str(self.wiki_root),
            "database_path": str(self.config.database_path),
            "compiled_wiki": str(self.wiki_root / "wiki"),
            "knowledge_mode": "compiled_wiki",
            "rag": {
                "enabled": False,
                "vector_store": False,
                "retrieval_surface": "wiki_sections",
            },
            "files": len(self.index.records),
            "all_files": len(self.full_index.records),
            "comments": len(self.index.comments),
            "all_comments": len(self.full_index.comments),
            "llm": {
                "enabled": self.config.llm.enabled,
                "ready": bool(self.llm_client and self.llm_client.ready),
                "provider": self.config.llm.provider,
                "model": self.config.llm.model,
            },
            "auth": {
                "enabled": self.config.auth_enabled,
                "admin_token_env": self.config.api_token_env,
                "read_token_env": self.config.api_read_token_env,
            },
            "store": self.store.stats(),
        }

    def active_index(self) -> WikiIndex:
        quarantined = {
            source["rel_path"]
            for source in self.store.list_sources(include_missing=True)
            if source.get("status") == "quarantined"
        }
        records = [record for record in self.full_index.records if record.rel_path not in quarantined]
        return self.full_index.with_records(records)

    def refresh_runtime_index(self) -> None:
        self.index = self.active_index()
        self.answerer = QuestionAnswerer(self.index, self.guard, self.llm_client)

    def audit(
        self,
        event_type: str,
        request_id: str,
        subject: str,
        status: str,
        blocked: bool = False,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self.config.audit_enabled:
            self.store.record_audit(event_type, request_id, subject, status, blocked, payload)


def new_request_id() -> str:
    return uuid.uuid4().hex


def without_markdown(report: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in report.items() if key != "markdown"}
