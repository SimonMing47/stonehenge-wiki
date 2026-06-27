from __future__ import annotations

from typing import Any

BLOCKED_MESSAGE = "高危命令，拒绝访问"


def make_standard_response(
    q_id: str,
    title: str,
    level: str,
    data_type: str,
    raw_data: Any = None,
    is_blocked: bool = False,
) -> dict[str, Any]:
    if is_blocked or data_type == "blocked":
        answer = {"error_msg": BLOCKED_MESSAGE}
    elif data_type == "file_count":
        answer = raw_data or {}
    elif data_type == "comment_count":
        answer = {"count": int(raw_data or 0)}
    elif data_type == "fix":
        source, target = raw_data
        answer = {"source": source, "target": target}
    elif data_type in {"paths", "list"}:
        answer = {"datas": list(raw_data or [])}
    else:
        if raw_data is None:
            raw_data = []
        answer = {"datas": raw_data if isinstance(raw_data, list) else [raw_data]}

    return {
        "id": q_id,
        "title": title,
        "level": level,
        "answer": answer,
    }

