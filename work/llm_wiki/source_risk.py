from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from .indexer import WikiIndex
from .models import CommentRecord, DocumentRecord
from .security import SYSTEM_SECRET_RE, PermissionGuard

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b[\w.-]*(?:password|passwd|secret|token|credential|api[_-]?key)[\w.-]*\b)\s*[:=]\s*([^,\s;<>]+)"
)
CN_SECRET_ASSIGNMENT_RE = re.compile(r"(密码|密钥|秘钥|口令)\s*[:：=]\s*([^,\s;<>]+)")


@dataclass(frozen=True)
class SourceRiskFinding:
    source_path: str
    severity: str
    code: str
    message: str
    line: int | None = None
    evidence: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "line": self.line,
            "evidence": self.evidence,
        }


def scan_source_risks(
    index: WikiIndex,
    guard: PermissionGuard,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    findings: list[SourceRiskFinding] = []
    for record in index.records:
        findings.extend(scan_record(record, guard, today))
    findings.sort(key=lambda item: (-SEVERITY_ORDER[item.severity], item.source_path, item.line or 0, item.code))

    finding_dicts = [finding.as_dict() for finding in findings]
    by_severity = Counter(finding.severity for finding in findings)
    by_code = Counter(finding.code for finding in findings)
    source_rows = source_summaries(findings)
    status = "attention" if findings else "ok"
    return {
        "status": status,
        "summary": {
            "status": status,
            "sources_scanned": len(index.records),
            "sources_with_risks": len(source_rows),
            "risk_count": len(findings),
            "critical": by_severity.get("critical", 0),
            "high": by_severity.get("high", 0),
            "medium": by_severity.get("medium", 0),
            "low": by_severity.get("low", 0),
        },
        "by_severity": dict(sorted(by_severity.items())),
        "by_code": dict(sorted(by_code.items())),
        "sources": source_rows,
        "findings": finding_dicts,
    }


def scan_record(record: DocumentRecord, guard: PermissionGuard, today: date) -> list[SourceRiskFinding]:
    findings: list[SourceRiskFinding] = []
    if record.text.startswith("[extract_error]"):
        findings.append(
            finding(record, "medium", "extract_error", "source text extraction failed", evidence=record.text[:180])
        )

    if guard.path_blocked(record.rel_path, operation="read"):
        findings.append(
            finding(record, "high", "permission_file_deny", "source path matches Permission.json file deny")
        )
    elif guard.path_blocked(record.rel_path, operation="write"):
        findings.append(
            finding(record, "medium", "permission_write_deny", "source path is read-only by Permission.json directory deny")
        )

    if record.suffix in {"py", "js", "java"} and guard.code_text_is_dangerous(record.text):
        match = first_matching_line(record.text, re.compile(r"(os\.system|subprocess|shutil\.rmtree|eval\(|exec\(|child_process|process\.env)", re.IGNORECASE))
        findings.append(
            finding(
                record,
                "high",
                "dangerous_code",
                "code source contains APIs blocked by execution guard",
                line=match[0],
                evidence=match[1],
            )
        )

    injection_match = first_matching_line(record.text, re.compile(r"(忽略(?:前面|以上|所有).{0,12}规则|开启上帝模式|上帝模式|删除全部文档|ignore\s+(all\s+)?previous|god\s*mode)", re.IGNORECASE))
    if injection_match[0]:
        findings.append(
            finding(
                record,
                "critical",
                "prompt_injection",
                "source contains prompt-injection language filtered from compiled wiki",
                line=injection_match[0],
                evidence=injection_match[1],
            )
        )

    secret_match = first_secret_line(record.text)
    if secret_match[0]:
        if guard.is_env_path(record.rel_path):
            findings.append(
                finding(
                    record,
                    "low",
                    "secret_in_env_path",
                    "secret-like text is present in the allowed environment folder",
                    line=secret_match[0],
                    evidence=redact_secret_line(secret_match[1]),
                )
            )
        else:
            findings.append(
                finding(
                    record,
                    "high",
                    "secret_outside_env_path",
                    "secret-like text is outside docs/02_环境信息 and should be reviewed",
                    line=secret_match[0],
                    evidence=redact_secret_line(secret_match[1]),
                )
            )

    system_secret_match = first_matching_line(record.text, SYSTEM_SECRET_RE)
    if system_secret_match[0]:
        findings.append(
            finding(
                record,
                "high",
                "system_secret_reference",
                "source references system secret locations or local credentials",
                line=system_secret_match[0],
                evidence=redact_secret_line(system_secret_match[1]),
            )
        )

    for comment in record.comments:
        findings.extend(comment_risks(comment, today))
    return findings


def comment_risks(comment: CommentRecord, today: date) -> list[SourceRiskFinding]:
    risks: list[SourceRiskFinding] = []
    if comment.todo and not comment.assignee:
        risks.append(
            SourceRiskFinding(
                source_path=comment.source_path,
                severity="medium",
                code="unassigned_todo",
                message="structured TODO has no assignee",
                line=comment.line,
                evidence=comment.summary(),
            )
        )
    due = parse_yyyymmdd(comment.end_date)
    if comment.todo and due and due < today:
        risks.append(
            SourceRiskFinding(
                source_path=comment.source_path,
                severity="high",
                code="overdue_todo",
                message="structured TODO is past due",
                line=comment.line,
                evidence=comment.summary(),
            )
        )
    return risks


def source_summaries(findings: list[SourceRiskFinding]) -> list[dict[str, Any]]:
    grouped: dict[str, list[SourceRiskFinding]] = defaultdict(list)
    for finding_item in findings:
        grouped[finding_item.source_path].append(finding_item)
    rows: list[dict[str, Any]] = []
    for source_path, source_findings in grouped.items():
        max_severity = max(source_findings, key=lambda item: SEVERITY_ORDER[item.severity]).severity
        rows.append(
            {
                "source_path": source_path,
                "risk_count": len(source_findings),
                "max_severity": max_severity,
                "codes": sorted({item.code for item in source_findings}),
            }
        )
    rows.sort(key=lambda item: (-SEVERITY_ORDER[item["max_severity"]], -item["risk_count"], item["source_path"]))
    return rows


def finding(
    record: DocumentRecord,
    severity: str,
    code: str,
    message: str,
    line: int | None = None,
    evidence: str = "",
) -> SourceRiskFinding:
    return SourceRiskFinding(
        source_path=record.rel_path,
        severity=severity,
        code=code,
        message=message,
        line=line,
        evidence=clean_evidence(evidence),
    )


def first_matching_line(text: str, pattern: re.Pattern[str]) -> tuple[int | None, str]:
    for line_no, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            return line_no, line
    return None, ""


def redact_secret_line(line: str) -> str:
    redacted = SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}: [REDACTED]", line)
    return CN_SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}: [REDACTED]", redacted)


def clean_evidence(text: str) -> str:
    return " ".join(redact_secret_line(text).split())[:220]


def first_secret_line(text: str) -> tuple[int | None, str]:
    for line_no, line in enumerate(text.splitlines(), start=1):
        if SECRET_ASSIGNMENT_RE.search(line) or CN_SECRET_ASSIGNMENT_RE.search(line):
            return line_no, line
    return None, ""


def parse_yyyymmdd(value: str | None) -> date | None:
    if not value or len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None
