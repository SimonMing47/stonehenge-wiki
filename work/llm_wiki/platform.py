from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .answerer import QuestionAnswerer
from .cli_io import load_questions, output_path_for_question_file, resolve_question_files, write_result_log
from .config import PlatformConfig, load_config
from .indexer import WikiIndex
from .llm import LLMClient
from .models import Question
from .security import PermissionGuard
from .store import SQLiteStore
from .wiki_compiler import WikiCompiler


class LLMWikiPlatform:
    def __init__(self, wiki_root: Path, config: PlatformConfig | None = None):
        self.config = config or load_config(wiki_root)
        self.wiki_root = self.config.wiki_root
        self.index = WikiIndex(self.wiki_root).build()
        self.guard = PermissionGuard(self.wiki_root)
        self.llm_client = LLMClient(self.config.llm) if self.config.llm.enabled else None
        self.answerer = QuestionAnswerer(self.index, self.guard, self.llm_client)
        self.store = SQLiteStore(self.config.database_path)
        if self.config.persist_index:
            self.store.save_index(self.index)

    @property
    def compiler(self) -> WikiCompiler:
        return WikiCompiler(self.wiki_root, self.index)

    @classmethod
    def from_wiki_root(cls, wiki_root: Path) -> "LLMWikiPlatform":
        return cls(wiki_root)

    def rebuild_index(self) -> dict[str, Any]:
        self.index.build()
        self.answerer = QuestionAnswerer(self.index, self.guard, self.llm_client)
        if self.config.persist_index:
            self.store.save_index(self.index)
        result = self.health()
        self.store.record_job("reindex", "ok", {"wiki_root": str(self.wiki_root)}, result)
        return result

    def compile_wiki(self) -> dict[str, Any]:
        result = self.compiler.compile()
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

    def dump_index(self) -> dict[str, Any]:
        return {
            "files": [
                {
                    "path": record.rel_path,
                    "suffix": record.suffix,
                    "tags": sorted(record.tags),
                    "comment_count": len(record.comments),
                }
                for record in self.index.records
            ],
            "comments": [comment.summary() for comment in self.index.comments],
            "store": self.store.stats(),
        }

    def audit_events(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list_audit_events(limit)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "wiki_root": str(self.wiki_root),
            "database_path": str(self.config.database_path),
            "compiled_wiki": str(self.wiki_root / "wiki"),
            "files": len(self.index.records),
            "comments": len(self.index.comments),
            "llm": {
                "enabled": self.config.llm.enabled,
                "ready": bool(self.llm_client and self.llm_client.ready),
                "provider": self.config.llm.provider,
                "model": self.config.llm.model,
            },
            "store": self.store.stats(),
        }

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
