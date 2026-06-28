from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .extractors import SUPPORTED_EXTENSIONS
from .formatting import BLOCKED_MESSAGE
from .models import Question

AnswerFn = Callable[[Question], dict[str, Any]]
ExplainFn = Callable[[Question], dict[str, Any]]


def build_evaluation_report(
    health: dict[str, Any],
    question_batches: list[tuple[Path, list[Question]]],
    answer_fn: AnswerFn,
    explain_fn: ExplainFn,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for question_file, questions in question_batches:
        for question in questions:
            answer = answer_fn(question)
            explanation = explain_fn(question)
            results.append(evaluate_one(question_file, question, answer, explanation))

    summary = summarize(results)
    risks = build_risks(summary, results)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "wiki_root": health.get("wiki_root"),
        "llm": health.get("llm", {}),
        "store": health.get("store", {}),
        "summary": summary,
        "risks": risks,
        "results": results,
        "markdown": render_markdown(summary, risks, results),
    }


def evaluate_one(
    question_file: Path,
    question: Question,
    answer: dict[str, Any],
    explanation: dict[str, Any],
) -> dict[str, Any]:
    answer_payload = answer.get("answer", {}) if isinstance(answer, dict) else {}
    datas = answer_payload.get("datas", []) if isinstance(answer_payload, dict) else []
    if not isinstance(datas, list):
        datas = []
    schema = validate_answer_schema(answer)
    blocked = answer_payload.get("error_msg") == BLOCKED_MESSAGE if isinstance(answer_payload, dict) else False
    evidence = explanation.get("evidence", []) if isinstance(explanation, dict) else []
    records = explanation.get("records", []) if isinstance(explanation, dict) else []
    trace_covered = bool(blocked or evidence or records or explanation.get("summary"))
    llm_markers = [item for item in datas if isinstance(item, str) and item.startswith("llm:")]
    source_markers = [item for item in datas if isinstance(item, str) and item.startswith("sources:")]
    return {
        "question_file": question_file.as_posix(),
        "id": question.id,
        "title": question.title,
        "level": question.level,
        "route": explanation.get("route", "unknown"),
        "status": "blocked" if blocked else "ok",
        "schema_valid": schema["valid"],
        "schema_reason": schema["reason"],
        "trace_covered": trace_covered,
        "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
        "record_count": len(records) if isinstance(records, list) else 0,
        "llm_used": bool(llm_markers),
        "source_cited": bool(source_markers),
        "empty_answer": is_empty_answer(answer_payload),
        "answer_shape": sorted(answer_payload.keys()) if isinstance(answer_payload, dict) else [],
        "top_sources": [record.get("path") for record in records[:5] if isinstance(record, dict)],
    }


def validate_answer_schema(answer: dict[str, Any]) -> dict[str, Any]:
    if set(answer.keys()) != {"id", "title", "level", "answer"}:
        return {"valid": False, "reason": "top_level_shape"}
    payload = answer.get("answer")
    if not isinstance(payload, dict):
        return {"valid": False, "reason": "answer_not_object"}
    keys = set(payload.keys())
    if keys == {"error_msg"}:
        return {"valid": payload.get("error_msg") == BLOCKED_MESSAGE, "reason": "blocked"}
    if keys == {"count"}:
        return {"valid": isinstance(payload.get("count"), int), "reason": "comment_count"}
    if keys == {"source", "target"}:
        valid = isinstance(payload.get("source"), str) and isinstance(payload.get("target"), str)
        return {"valid": valid, "reason": "fix"}
    if keys == {"datas"}:
        return {"valid": isinstance(payload.get("datas"), list), "reason": "datas"}
    if keys and keys.issubset(SUPPORTED_EXTENSIONS):
        return {"valid": all(isinstance(value, int) for value in payload.values()), "reason": "file_count"}
    return {"valid": False, "reason": "unknown_answer_shape"}


def is_empty_answer(answer_payload: Any) -> bool:
    if not isinstance(answer_payload, dict):
        return True
    if "datas" in answer_payload:
        return len(answer_payload.get("datas") or []) == 0
    return False


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    schema_valid = sum(1 for result in results if result["schema_valid"])
    trace_covered = sum(1 for result in results if result["trace_covered"])
    blocked = sum(1 for result in results if result["status"] == "blocked")
    empty_answers = sum(1 for result in results if result["empty_answer"])
    llm_used = sum(1 for result in results if result["llm_used"])
    source_cited = sum(1 for result in results if result["source_cited"])
    score = 100.0
    if total:
        score = round(((schema_valid + trace_covered) / (total * 2)) * 100, 2)
    status = "ok" if total and schema_valid == total and trace_covered == total else "attention"
    if not total:
        status = "empty"
    return {
        "status": status,
        "score": score,
        "total_questions": total,
        "schema_valid": schema_valid,
        "trace_covered": trace_covered,
        "blocked": blocked,
        "empty_answers": empty_answers,
        "llm_used": llm_used,
        "source_cited": source_cited,
        "routes": dict(Counter(str(result.get("route") or "unknown") for result in results)),
        "levels": dict(Counter(str(result.get("level") or "unknown") for result in results)),
    }


def build_risks(summary: dict[str, Any], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    invalid = [result["id"] for result in results if not result["schema_valid"]]
    missing_trace = [result["id"] for result in results if not result["trace_covered"]]
    empty = [result["id"] for result in results if result["empty_answer"]]
    if invalid:
        risks.append({"severity": "high", "code": "schema_invalid", "count": len(invalid), "question_ids": invalid[:20]})
    if missing_trace:
        risks.append({"severity": "medium", "code": "missing_trace", "count": len(missing_trace), "question_ids": missing_trace[:20]})
    if empty:
        risks.append({"severity": "medium", "code": "empty_answers", "count": len(empty), "question_ids": empty[:20]})
    if summary["total_questions"] == 0:
        risks.append({"severity": "high", "code": "no_questions", "count": 0, "question_ids": []})
    return risks


def render_markdown(summary: dict[str, Any], risks: list[dict[str, Any]], results: list[dict[str, Any]]) -> str:
    lines = [
        "# LLM Wiki Evaluation Report",
        "",
        "## Summary",
        "",
        f"- Status: {summary['status']}",
        f"- Score: {summary['score']}",
        f"- Questions: {summary['total_questions']}",
        f"- Schema valid: {summary['schema_valid']}",
        f"- Trace covered: {summary['trace_covered']}",
        f"- Blocked: {summary['blocked']}",
        f"- LLM used: {summary['llm_used']}",
        f"- Source cited: {summary['source_cited']}",
        "",
        "## Risks",
        "",
    ]
    if risks:
        for risk in risks:
            lines.append(f"- {risk['severity']} {risk['code']}: {risk['count']}")
    else:
        lines.append("- No evaluation risks detected.")
    lines.extend(["", "## Questions", "", "| ID | Route | Schema | Trace | Evidence | Status |", "| --- | --- | --- | --- | ---: | --- |"])
    for result in results:
        schema = "ok" if result["schema_valid"] else result["schema_reason"]
        trace = "ok" if result["trace_covered"] else "missing"
        lines.append(
            f"| {result['id']} | {result['route']} | {schema} | {trace} | "
            f"{result['evidence_count']} | {result['status']} |"
        )
    return "\n".join(lines) + "\n"
