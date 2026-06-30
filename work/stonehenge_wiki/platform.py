from __future__ import annotations

import json
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .answerer import QuestionAnswerer
from .cli_io import load_questions, output_path_for_question_file, resolve_question_files, write_result_log
from .config import LLMConfig, PlatformConfig, llm_config_to_dict, load_config
from .evaluation import build_evaluation_report
from .indexer import WikiIndex
from .importer import SourceImportError, import_source
from .llm import LLMClient
from .models import Question
from .presentations import create_presentation
from .readiness import build_readiness_report
from .reports import build_governance_report
from .security import PermissionGuard
from .source_risk import MANDATORY_QUARANTINE_CODES, scan_source_risks
from .store import SQLiteStore
from .wiki_compiler import WikiCompiler


class StonehengeWikiPlatform:
    def __init__(self, wiki_root: Path, config: PlatformConfig | None = None):
        self.config = config or load_config(wiki_root)
        self.wiki_root = self.config.wiki_root
        self.full_index = WikiIndex(self.wiki_root).build()
        self.guard = PermissionGuard(self.wiki_root)
        self.llm_default_agent = self.config.llm_default_agent
        self.llm_category_agents = dict(self.config.llm_category_agents)
        self.llm_clients = self.build_llm_clients()
        self.llm_client = self.llm_clients.get(self.llm_default_agent) or self.llm_clients.get("default")
        self.store = SQLiteStore(self.config.database_path)
        policy_result: dict[str, Any] = {"quarantined": []}
        if self.config.persist_index:
            self.store.save_index(self.full_index)
            policy_result = self.apply_source_policy_quarantine()
        self.index = self.active_index()
        self.answerer = self._build_answerer()
        if self.config.persist_index:
            if policy_result.get("quarantined"):
                self.compiler.compile()
            self.store.save_wiki_sections(self.wiki_root / "wiki")

    @property
    def compiler(self) -> WikiCompiler:
        return WikiCompiler(self.wiki_root, self.index)

    @classmethod
    def from_wiki_root(cls, wiki_root: Path) -> "StonehengeWikiPlatform":
        return cls(wiki_root)

    def build_llm_clients(self) -> dict[str, LLMClient]:
        clients: dict[str, LLMClient] = {}
        for name, agent in self.config.llm_agents.items():
            clients[name] = LLMClient(agent)
        return clients

    def _build_answerer(self) -> QuestionAnswerer:
        return QuestionAnswerer(
            self.index,
            self.guard,
            llm_client=self.llm_client,
            llm_clients=self.llm_clients,
            default_agent=self.llm_default_agent,
            source_agent_map=self.llm_category_agents,
        )

    def default_llm_config(self) -> LLMConfig:
        return self.config.llm_agents.get(self.llm_default_agent, self.config.llm)

    def _coerce_int(self, value: Any, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def _coerce_float(self, value: Any, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

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

    def readiness_report(
        self,
        explicit_files: list[Path] | None = None,
        groups: list[str] | None = None,
    ) -> dict[str, Any]:
        question_files = resolve_question_files(self.wiki_root, explicit_files, groups)
        report = build_readiness_report(
            self.wiki_root,
            self.health(),
            self.list_sources(include_missing=True),
            self.source_risk_report(),
            self.compiler.lint(),
            self.guard,
            question_files,
        )
        return {"status": "ok", "report": without_markdown(report)}

    def export_readiness_report(
        self,
        explicit_files: list[Path] | None = None,
        groups: list[str] | None = None,
    ) -> dict[str, Any]:
        question_files = resolve_question_files(self.wiki_root, explicit_files, groups)
        report = build_readiness_report(
            self.wiki_root,
            self.health(),
            self.list_sources(include_missing=True),
            self.source_risk_report(),
            self.compiler.lint(),
            self.guard,
            question_files,
        )
        output_dir = self.wiki_root / "output" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / "readiness-report.md"
        json_target = output_dir / "readiness-report.json"
        target.write_text(report["markdown"], encoding="utf-8")
        json_target.write_text(json.dumps(without_markdown(report), ensure_ascii=False, indent=2), encoding="utf-8")
        rel = target.relative_to(self.wiki_root).as_posix()
        json_rel = json_target.relative_to(self.wiki_root).as_posix()
        result = {
            "status": "ok",
            "report": without_markdown(report),
            "path": rel,
            "json_path": json_rel,
            "download_url": "/files/" + quote(rel, safe="/"),
            "json_download_url": "/files/" + quote(json_rel, safe="/"),
        }
        self.store.record_job(
            "readiness_report_export",
            report["summary"]["status"],
            {"question_files": [str(path) for path in question_files]},
            result,
        )
        self.audit(
            "readiness.report",
            new_request_id(),
            rel,
            report["summary"]["status"],
            report["summary"]["fail"] > 0,
            {"summary": report["summary"]},
        )
        return result

    def export_release_bundle(
        self,
        explicit_files: list[Path] | None = None,
        groups: list[str] | None = None,
        include_evaluation: bool = False,
    ) -> dict[str, Any]:
        question_files = resolve_question_files(self.wiki_root, explicit_files, groups)
        readiness = self.export_readiness_report(explicit_files=explicit_files, groups=groups)
        governance = self.export_governance_report()
        evaluation = None
        if include_evaluation:
            evaluation = self.export_evaluation_report(explicit_files=explicit_files, groups=groups)

        output_dir = self.wiki_root / "output" / "releases"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = output_dir / f"stonehenge-wiki-release-{timestamp}.zip"
        manifest = self.release_manifest(question_files, readiness, governance, evaluation)

        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            bundle.writestr(
                "reports/governance-report.json",
                json.dumps(governance.get("report", {}), ensure_ascii=False, indent=2),
            )
            add_if_exists(bundle, self.wiki_root / readiness["path"], "reports/readiness-report.md")
            add_if_exists(bundle, self.wiki_root / readiness["json_path"], "reports/readiness-report.json")
            add_if_exists(bundle, self.wiki_root / governance["path"], "reports/governance-report.md")
            if evaluation:
                add_if_exists(bundle, self.wiki_root / evaluation["path"], "reports/evaluation-report.md")
                add_if_exists(bundle, self.wiki_root / evaluation["json_path"], "reports/evaluation-report.json")
            for rel in ["README.md", "AGENTS.md", "Permission.json", "config.json"]:
                add_if_exists(bundle, self.wiki_root / rel, rel)
            for question_file in question_files:
                if question_file.exists():
                    arcname = "question/" + question_file.name
                    add_if_exists(bundle, question_file, arcname)
                answer_path = output_path_for_question_file(self.wiki_root, question_file)
                if answer_path.exists():
                    add_if_exists(bundle, answer_path, "output/" + answer_path.name)
            add_tree(bundle, self.wiki_root / "wiki", "wiki")

        rel = target.relative_to(self.wiki_root).as_posix()
        result = {
            "status": "ok",
            "path": rel,
            "download_url": "/files/" + quote(rel, safe="/"),
            "manifest": manifest,
            "size": target.stat().st_size,
        }
        self.store.record_job(
            "release_bundle_export",
            "ok",
            {
                "question_files": [str(path) for path in question_files],
                "include_evaluation": include_evaluation,
            },
            result,
        )
        self.audit(
            "release.export",
            new_request_id(),
            rel,
            "ok",
            False,
            {"manifest": manifest},
        )
        return result

    def release_manifest(
        self,
        question_files: list[Path],
        readiness: dict[str, Any],
        governance: dict[str, Any],
        evaluation: dict[str, Any] | None,
    ) -> dict[str, Any]:
        health = self.health()
        answer_files = [
            output_path_for_question_file(self.wiki_root, path).relative_to(self.wiki_root).as_posix()
            for path in question_files
            if output_path_for_question_file(self.wiki_root, path).exists()
        ]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "wiki_root": str(self.wiki_root),
            "knowledge_mode": health.get("knowledge_mode"),
            "rag": health.get("rag", {}),
            "llm": health.get("llm", {}),
            "reports": {
                "readiness": readiness.get("path"),
                "governance": governance.get("path"),
                "evaluation": evaluation.get("path") if evaluation else None,
            },
            "question_files": [
                path.relative_to(self.wiki_root).as_posix() if self.wiki_root in path.resolve().parents else str(path)
                for path in question_files
                if path.exists()
            ],
            "answer_files": answer_files,
            "included": {
                "compiled_wiki": True,
                "raw_docs": False,
                "sqlite_state": False,
                "screenshots": False,
            },
        }

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

    def llm_config(self) -> dict[str, Any]:
        default_config = self.default_llm_config()
        return {
            "llm": {
                "enabled": bool(default_config.enabled if isinstance(default_config, LLMConfig) else self.config.llm.enabled),
                "default_agent": self.llm_default_agent,
                "agents": {
                    name: llm_config_to_dict(name, agent)
                    for name, agent in sorted(self.config.llm_agents.items())
                },
                "category_agents": self.llm_category_agents,
                "provider": default_config.provider,
                "model": default_config.model,
            },
            "source_categories": sorted({
                source.get("category", "uncategorized")
                for source in self.list_sources(include_missing=True)
            }),
        }

    def update_llm_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"status": "error", "error": "invalid_payload"}

        enabled = bool(payload.get("enabled", self.config.llm.enabled))
        default_agent = str(payload.get("default_agent", self.config.llm_default_agent) or self.config.llm_default_agent)
        category_agents = payload.get("category_agents", self.config.llm_category_agents)
        if not isinstance(category_agents, dict):
            return {"status": "error", "error": "invalid_category_agents"}

        normalized_category_agents: dict[str, str] = {}
        for raw_category, raw_agent in category_agents.items():
            if not isinstance(raw_category, str) or not isinstance(raw_agent, str):
                continue
            category = raw_category.strip()
            agent = raw_agent.strip()
            if not category or not agent:
                continue
            normalized_category_agents[category] = agent

        agents = payload.get("agents")
        if not isinstance(agents, dict) or not agents:
            return {"status": "error", "error": "invalid_agents"}
        serialized_agents: dict[str, dict[str, Any]] = {}
        for agent_name, agent_body in agents.items():
            if not isinstance(agent_name, str) or not isinstance(agent_body, dict):
                continue
            raw_enabled = bool(agent_body.get("enabled", enabled))
            raw_env_file = agent_body.get("env_file", "")
            serialized = llm_config_to_dict(
                agent_name,
                LLMConfig(
                    enabled=raw_enabled,
                    provider=str(agent_body.get("provider", "")),
                    model=str(agent_body.get("model", "")),
                    base_url=str(agent_body.get("base_url", "")),
                    api_key_env=str(agent_body.get("api_key_env", "")),
                    env_file=Path(str(raw_env_file)).expanduser() if raw_env_file else None,
                    timeout_seconds=self._coerce_int(agent_body.get("timeout_seconds", 60), 60),
                    max_context_chars=self._coerce_int(agent_body.get("max_context_chars", 12000), 12000),
                    max_tokens=self._coerce_int(agent_body.get("max_tokens", 800), 800),
                    temperature=self._coerce_float(agent_body.get("temperature", 0.1), 0.1),
                ),
            )
            serialized["enabled"] = bool(serialized.get("enabled"))
            serialized_agents[agent_name] = serialized

        if not serialized_agents:
            return {"status": "error", "error": "invalid_agents"}

        if default_agent not in serialized_agents:
            if default_agent != "default" and "default" in serialized_agents:
                default_agent = "default"
            elif serialized_agents:
                default_agent = next(iter(serialized_agents))
            else:
                return {"status": "error", "error": "no_valid_agents"}

        normalized_category_agents = {
            category: agent for category, agent in normalized_category_agents.items() if agent in serialized_agents
        }

        config_path = self.wiki_root / "config.json"
        existing: dict[str, Any] = {}
        if config_path.exists():
            existing = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            existing = {}
        base = dict(existing.get("llm", {})) if isinstance(existing.get("llm", {}), dict) else {}
        cleaned_agents = {}
        for name, data in serialized_agents.items():
            cleaned_agents[name] = {
                key: value
                for key, value in data.items()
                if key != "agent_name"
            }
        default_client = cleaned_agents.get(default_agent, {})
        base.update({
            "enabled": enabled,
            "agents": cleaned_agents,
            "default_agent": default_agent,
            "category_agents": normalized_category_agents,
            "provider": default_client.get("provider", base.get("provider", "")),
            "model": default_client.get("model", base.get("model", "")),
            "base_url": default_client.get("base_url", base.get("base_url", "")),
            "api_key_env": default_client.get("api_key_env", base.get("api_key_env", "")),
            "env_file": default_client.get("env_file", base.get("env_file", "")),
            "timeout_seconds": default_client.get("timeout_seconds", base.get("timeout_seconds", 60)),
            "max_context_chars": default_client.get("max_context_chars", base.get("max_context_chars", 12000)),
            "max_tokens": default_client.get("max_tokens", base.get("max_tokens", 800)),
            "temperature": default_client.get("temperature", base.get("temperature", 0.1)),
        })
        existing["llm"] = base
        config_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

        self.config = load_config(self.wiki_root)
        self.llm_default_agent = self.config.llm_default_agent
        self.llm_category_agents = dict(self.config.llm_category_agents)
        self.llm_clients = self.build_llm_clients()
        self.llm_client = self.llm_clients.get(self.llm_default_agent) or self.llm_clients.get("default")
        self.refresh_runtime_index()
        self.audit(
            event_type="llm.config",
            request_id=new_request_id(),
            subject="llm",
            status="ok",
            payload={
                "agent_count": len(self.llm_clients),
                "default_agent": self.llm_default_agent,
            },
        )
        return {
            "status": "ok",
            "llm": self.llm_config()["llm"],
        }

    def list_wiki_pages(self, limit: int = 200) -> dict[str, Any]:
        compiled_root = self.wiki_root / "wiki"
        pages: list[dict[str, Any]] = []
        if compiled_root.exists():
            for path in sorted(compiled_root.rglob("*.md"), key=wiki_page_sort_key):
                page = read_wiki_page_summary(compiled_root, path)
                pages.append(page)
                if len(pages) >= limit:
                    break
        return {"status": "ok", "pages": pages, "count": len(pages)}

    def get_wiki_page(self, page_path: str) -> dict[str, Any]:
        compiled_root = (self.wiki_root / "wiki").resolve()
        safe_path = Path(page_path.strip("/"))
        if safe_path.is_absolute() or ".." in safe_path.parts:
            return {"error": "invalid_path"}
        target = (compiled_root / safe_path).resolve()
        if compiled_root not in target.parents and target != compiled_root:
            return {"error": "invalid_path"}
        if not target.is_file() or target.suffix.lower() != ".md":
            return {"error": "not_found"}
        return {
            "status": "ok",
            "page": read_wiki_page_summary(compiled_root, target),
            "markdown": strip_front_matter(target.read_text(encoding="utf-8", errors="ignore")),
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
        default_llm = self.default_llm_config()
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
                "enabled": bool(default_llm.enabled),
                "ready": bool(self.llm_client and self.llm_client.ready),
                "provider": default_llm.provider,
                "model": default_llm.model,
                "agents": len(self.llm_clients),
                "default_agent": self.llm_default_agent,
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
        self.answerer = self._build_answerer()

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


def add_if_exists(bundle: zipfile.ZipFile, path: Path, arcname: str) -> None:
    if path.is_file():
        bundle.write(path, arcname)


def add_tree(bundle: zipfile.ZipFile, root: Path, arc_root: str) -> None:
    if not root.exists():
        return
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        bundle.write(path, f"{arc_root}/{path.relative_to(root).as_posix()}")


def wiki_page_sort_key(path: Path) -> tuple[int, str]:
    rel = path.as_posix()
    if rel.endswith("/index.md"):
        return (0, rel)
    if "/sources/" in rel:
        return (1, rel)
    if "/topics/" in rel:
        return (2, rel)
    return (3, rel)


def read_wiki_page_summary(compiled_root: Path, path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    meta, body = split_front_matter(raw)
    title = meta.get("title") or first_heading(body) or path.stem
    rel = path.relative_to(compiled_root).as_posix()
    return {
        "path": rel,
        "title": title,
        "kind": meta.get("kind") or infer_wiki_page_kind(rel),
        "source_path": meta.get("source_path", ""),
        "file_type": meta.get("file_type", ""),
        "excerpt": first_paragraph(body),
    }


def split_front_matter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---\n"):
        return {}, raw
    lines = raw.splitlines()
    end = next((idx for idx, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end is None:
        return {}, raw
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    return meta, "\n".join(lines[end + 1 :]).strip()


def strip_front_matter(raw: str) -> str:
    return split_front_matter(raw)[1]


def infer_wiki_page_kind(rel_path: str) -> str:
    if rel_path == "index.md":
        return "index"
    if rel_path == "log.md":
        return "log"
    if rel_path.startswith("sources/"):
        return "source"
    if rel_path.startswith("topics/"):
        return "topic"
    return "page"


def first_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return ""


def first_paragraph(markdown: str) -> str:
    for line in markdown.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#") or cleaned.startswith("- "):
            continue
        return cleaned[:220]
    return ""
