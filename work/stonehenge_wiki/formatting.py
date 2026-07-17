from __future__ import annotations

from pathlib import Path
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
        answer = {str(key): int(value or 0) for key, value in dict(raw_data or {}).items()}
    elif data_type == "comment_count":
        answer = {"count": int(raw_data or 0)}
    elif data_type == "fix":
        source, target = raw_data
        answer = {"source": path_text(source), "target": path_text(target)}
    elif data_type in {"paths", "list"}:
        answer = {"datas": normalize_datas(raw_data)}
    else:
        if raw_data is None:
            raw_data = []
        answer = {"datas": normalize_datas(raw_data)}

    return {
        "id": q_id,
        "title": title,
        "level": level,
        "answer": answer,
    }


def normalize_datas(raw_data: Any) -> list[Any]:
    if raw_data is None:
        return []
    if isinstance(raw_data, (list, tuple, set)):
        values = list(raw_data)
    else:
        values = [raw_data]
    return [json_value(value) for value in values]


def json_value(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, tuple):
        return [json_value(item) for item in value]
    if isinstance(value, list):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def path_text(value: Any) -> str:
    return value.as_posix() if isinstance(value, Path) else str(value).replace("\\", "/")
