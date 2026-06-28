from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .models import CommentRecord


@dataclass(frozen=True)
class GovernanceReport:
    summary: dict[str, Any]
    risks: list[dict[str, Any]]
    source_risks: dict[str, Any]
    source_status: dict[str, int]
    categories: dict[str, int]
    suffixes: dict[str, int]
    todo: dict[str, Any]
    latest_jobs: list[dict[str, Any]]
    latest_audit: list[dict[str, Any]]
    markdown: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "risks": self.risks,
            "source_risks": self.source_risks,
            "source_status": self.source_status,
            "categories": self.categories,
            "suffixes": self.suffixes,
            "todo": self.todo,
            "latest_jobs": self.latest_jobs,
            "latest_audit": self.latest_audit,
        }


def build_governance_report(
    health: dict[str, Any],
    sources: list[dict[str, Any]],
    comments: list[CommentRecord],
    audit_events: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    today: date | None = None,
    source_risk_report: dict[str, Any] | None = None,
) -> GovernanceReport:
    today = today or datetime.now(timezone.utc).date()
    source_risk_report = source_risk_report or empty_source_risk_report()
    source_status = Counter(str(item.get("status") or "unknown") for item in sources)
    categories = Counter(str(item.get("category") or "uncategorized") for item in sources)
    suffixes = Counter(str(item.get("suffix") or Path(str(item.get("rel_path") or "")).suffix.lstrip(".") or "unknown") for item in sources)
    todo = todo_summary(comments, today)
    blocked_events = [event for event in audit_events if event.get("blocked")]
    failed_jobs = [job for job in jobs if job.get("status") not in {"ok", "success"}]
    risks = build_risks(source_status, todo, blocked_events, failed_jobs, source_risk_report)
    source_risk_summary = source_risk_report.get("summary", {})
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "attention" if risks else "ok",
        "files": int(health.get("files") or 0),
        "comments": int(health.get("comments") or 0),
        "sources": int(health.get("store", {}).get("sources") or len([s for s in sources if s.get("status") != "missing"])),
        "missing_sources": int(health.get("store", {}).get("missing_sources") or source_status.get("missing", 0)),
        "audit_events": int(health.get("store", {}).get("audit_events") or 0),
        "jobs": int(health.get("store", {}).get("jobs") or 0),
        "llm_ready": bool(health.get("llm", {}).get("ready")),
        "auth_enabled": bool(health.get("auth", {}).get("enabled")),
        "source_risks": int(source_risk_summary.get("risk_count") or 0),
        "critical_source_risks": int(source_risk_summary.get("critical") or 0),
        "sources_with_risks": int(source_risk_summary.get("sources_with_risks") or 0),
    }
    markdown = render_markdown(
        summary,
        risks,
        source_risk_report,
        source_status,
        categories,
        suffixes,
        todo,
        jobs,
        audit_events,
    )
    return GovernanceReport(
        summary=summary,
        risks=risks,
        source_risks=source_risk_report,
        source_status=dict(source_status),
        categories=dict(categories),
        suffixes=dict(suffixes),
        todo=todo,
        latest_jobs=jobs[:10],
        latest_audit=audit_events[:10],
        markdown=markdown,
    )


def todo_summary(comments: list[CommentRecord], today: date) -> dict[str, Any]:
    structured = [comment for comment in comments if comment.todo]
    overdue: list[dict[str, Any]] = []
    due_soon: list[dict[str, Any]] = []
    unassigned = 0
    by_assignee: Counter[str] = Counter()
    for comment in structured:
        assignee = comment.assignee or "unassigned"
        by_assignee[assignee] += 1
        if not comment.assignee:
            unassigned += 1
        due_date = parse_yyyymmdd(comment.end_date)
        item = {
            "source_path": comment.source_path,
            "todo": comment.todo,
            "assignee": comment.assignee,
            "end_date": comment.end_date,
        }
        if due_date and due_date < today:
            overdue.append(item)
        elif due_date and (due_date - today).days <= 30:
            due_soon.append(item)
    return {
        "total": len(structured),
        "overdue": len(overdue),
        "due_soon": len(due_soon),
        "unassigned": unassigned,
        "by_assignee": dict(by_assignee),
        "overdue_items": overdue[:10],
        "due_soon_items": due_soon[:10],
    }


def build_risks(
    source_status: Counter[str],
    todo: dict[str, Any],
    blocked_events: list[dict[str, Any]],
    failed_jobs: list[dict[str, Any]],
    source_risk_report: dict[str, Any],
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    if source_status.get("missing", 0):
        risks.append({"severity": "high", "code": "missing_sources", "count": source_status["missing"]})
    if todo["overdue"]:
        risks.append({"severity": "high", "code": "overdue_todos", "count": todo["overdue"]})
    if todo["unassigned"]:
        risks.append({"severity": "medium", "code": "unassigned_todos", "count": todo["unassigned"]})
    if blocked_events:
        risks.append({"severity": "medium", "code": "blocked_events", "count": len(blocked_events)})
    if failed_jobs:
        risks.append({"severity": "medium", "code": "failed_jobs", "count": len(failed_jobs)})
    source_summary = source_risk_report.get("summary", {})
    critical = int(source_summary.get("critical") or 0)
    high = int(source_summary.get("high") or 0)
    risk_count = int(source_summary.get("risk_count") or 0)
    if critical:
        risks.append({"severity": "critical", "code": "critical_source_risks", "count": critical})
    if high:
        risks.append({"severity": "high", "code": "high_source_risks", "count": high})
    elif risk_count:
        risks.append({"severity": "medium", "code": "source_risks", "count": risk_count})
    return risks


def render_markdown(
    summary: dict[str, Any],
    risks: list[dict[str, Any]],
    source_risk_report: dict[str, Any],
    source_status: dict[str, int],
    categories: dict[str, int],
    suffixes: dict[str, int],
    todo: dict[str, Any],
    jobs: list[dict[str, Any]],
    audit_events: list[dict[str, Any]],
) -> str:
    lines = [
        "# LLM Wiki Governance Report",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Status: {summary['status']}",
        f"- Files: {summary['files']}",
        f"- Sources: {summary['sources']} active / {summary['missing_sources']} missing",
        f"- Comments: {summary['comments']}",
        f"- Audit events: {summary['audit_events']}",
        f"- Jobs: {summary['jobs']}",
        f"- LLM ready: {summary['llm_ready']}",
        f"- Auth enabled: {summary['auth_enabled']}",
        f"- Source risks: {summary['source_risks']} across {summary['sources_with_risks']} sources",
        "",
        "## Risks",
        "",
    ]
    if risks:
        lines.extend(f"- {risk['severity']}: {risk['code']} ({risk['count']})" for risk in risks)
    else:
        lines.append("- No active risks detected.")
    lines.extend(["", "## Source Risk Review", ""])
    lines.extend(source_risk_lines(source_risk_report))
    lines.extend(["", "## Source Status", ""])
    lines.extend(counter_lines(source_status))
    lines.extend(["", "## Categories", ""])
    lines.extend(counter_lines(categories))
    lines.extend(["", "## File Types", ""])
    lines.extend(counter_lines(suffixes))
    lines.extend(
        [
            "",
            "## TODO",
            "",
            f"- Total: {todo['total']}",
            f"- Overdue: {todo['overdue']}",
            f"- Due soon: {todo['due_soon']}",
            f"- Unassigned: {todo['unassigned']}",
            "",
            "## Latest Jobs",
            "",
        ]
    )
    lines.extend(job_lines(jobs[:10]))
    lines.extend(["", "## Latest Audit", ""])
    lines.extend(audit_lines(audit_events[:10]))
    return "\n".join(lines) + "\n"


def empty_source_risk_report() -> dict[str, Any]:
    return {
        "status": "ok",
        "summary": {
            "status": "ok",
            "sources_scanned": 0,
            "sources_with_risks": 0,
            "risk_count": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        },
        "by_severity": {},
        "by_code": {},
        "sources": [],
        "findings": [],
    }


def source_risk_lines(source_risk_report: dict[str, Any]) -> list[str]:
    findings = source_risk_report.get("findings", [])
    if not findings:
        return ["- No source risks detected."]
    lines: list[str] = []
    for finding in findings[:15]:
        location = finding.get("source_path") or "source"
        if finding.get("line"):
            location = f"{location}:{finding['line']}"
        lines.append(
            f"- {finding.get('severity')}: {finding.get('code')} / {location} / {finding.get('message')}"
        )
    return lines


def counter_lines(counter: dict[str, int]) -> list[str]:
    if not counter:
        return ["- none"]
    return [f"- {key}: {value}" for key, value in sorted(counter.items())]


def job_lines(jobs: list[dict[str, Any]]) -> list[str]:
    if not jobs:
        return ["- none"]
    return [f"- {job.get('created_at')}: {job.get('job_type')} / {job.get('status')}" for job in jobs]


def audit_lines(events: list[dict[str, Any]]) -> list[str]:
    if not events:
        return ["- none"]
    return [
        f"- {event.get('created_at')}: {event.get('event_type')} / {event.get('status')} / {event.get('subject')}"
        for event in events
    ]


def parse_yyyymmdd(value: str | None) -> date | None:
    if not value or len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None
