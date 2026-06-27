from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PlatformConfig:
    wiki_root: Path
    state_dir: Path
    database_path: Path
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    api_token_env: str = "LLM_WIKI_API_TOKEN"
    audit_enabled: bool = True
    persist_index: bool = True
    snippet_limit: int = 8

    @property
    def api_token(self) -> str | None:
        token = os.environ.get(self.api_token_env, "").strip()
        return token or None


def load_config(wiki_root: Path) -> PlatformConfig:
    wiki_root = wiki_root.resolve()
    config_path = wiki_root / "config.json"
    data: dict[str, Any] = {}
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))

    state_dir = resolve_under_wiki(wiki_root, data.get("state_dir", ".state"))
    database_path = resolve_under_wiki(wiki_root, data.get("database_path", str(state_dir / "wiki.sqlite")))

    api = data.get("api", {}) if isinstance(data.get("api", {}), dict) else {}
    return PlatformConfig(
        wiki_root=wiki_root,
        state_dir=state_dir,
        database_path=database_path,
        api_host=str(api.get("host", data.get("api_host", "127.0.0.1"))),
        api_port=int(api.get("port", data.get("api_port", 8765))),
        api_token_env=str(api.get("token_env", data.get("api_token_env", "LLM_WIKI_API_TOKEN"))),
        audit_enabled=bool(data.get("audit_enabled", True)),
        persist_index=bool(data.get("persist_index", True)),
        snippet_limit=int(data.get("snippet_limit", 8)),
    )


def resolve_under_wiki(wiki_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return wiki_root / path

