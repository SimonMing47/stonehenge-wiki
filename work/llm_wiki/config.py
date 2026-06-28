from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = False
    provider: str = ""
    model: str = ""
    base_url: str = ""
    api_key_env: str = ""
    env_file: Path | None = None
    timeout_seconds: int = 60
    max_context_chars: int = 12000
    max_tokens: int = 800
    temperature: float = 0.1


@dataclass(frozen=True)
class PlatformConfig:
    wiki_root: Path
    state_dir: Path
    database_path: Path
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    api_token_env: str = "LLM_WIKI_API_TOKEN"
    api_read_token_env: str = "LLM_WIKI_READ_TOKEN"
    audit_enabled: bool = True
    persist_index: bool = True
    snippet_limit: int = 8
    llm: LLMConfig = LLMConfig()
    llm_agents: dict[str, LLMConfig] = field(default_factory=dict)
    llm_default_agent: str = "default"
    llm_category_agents: dict[str, str] = field(default_factory=dict)

    @property
    def api_token(self) -> str | None:
        token = os.environ.get(self.api_token_env, "").strip()
        return token or None

    @property
    def api_read_token(self) -> str | None:
        token = os.environ.get(self.api_read_token_env, "").strip()
        return token or None

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_token or self.api_read_token)


def load_config(wiki_root: Path) -> PlatformConfig:
    wiki_root = wiki_root.resolve()
    config_path = wiki_root / "config.json"
    data: dict[str, Any] = {}
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))

    api = data.get("api", {}) if isinstance(data.get("api", {}), dict) else {}
    load_env_files(wiki_root, data, api)

    state_dir = resolve_under_wiki(wiki_root, data.get("state_dir", ".state"))
    database_path = resolve_under_wiki(wiki_root, data.get("database_path", str(state_dir / "wiki.sqlite")))

    llm = data.get("llm", {}) if isinstance(data.get("llm", {}), dict) else {}
    base_profile = _build_llm_config(llm, {})
    raw_agents = llm.get("agents", {})
    if isinstance(raw_agents, dict) and raw_agents:
        llm_agents = {
            str(agent_name): _build_llm_config(value, base_profile.__dict__)
            for agent_name, value in raw_agents.items()
            if isinstance(value, dict)
        }
    else:
        llm_agents = {}
    if not llm_agents:
        llm_agents["default"] = base_profile
    if "default" not in llm_agents:
        llm_agents["default"] = base_profile
    raw_default_agent = str(llm.get("default_agent", "default"))
    if raw_default_agent not in llm_agents:
        raw_default_agent = "default"
    raw_category_agents = llm.get("category_agents", llm.get("source_agents", {}))
    llm_category_agents = {}
    if isinstance(raw_category_agents, dict):
        for raw_category, raw_agent in raw_category_agents.items():
            if isinstance(raw_category, str) and isinstance(raw_agent, str):
                llm_category_agents[raw_category.strip()] = raw_agent.strip()
    return PlatformConfig(
        wiki_root=wiki_root,
        state_dir=state_dir,
        database_path=database_path,
        api_host=str(api.get("host", data.get("api_host", "127.0.0.1"))),
        api_port=int(api.get("port", data.get("api_port", 8765))),
        api_token_env=str(api.get("token_env", data.get("api_token_env", "LLM_WIKI_API_TOKEN"))),
        api_read_token_env=str(api.get("read_token_env", data.get("api_read_token_env", "LLM_WIKI_READ_TOKEN"))),
        audit_enabled=bool(data.get("audit_enabled", True)),
        persist_index=bool(data.get("persist_index", True)),
        snippet_limit=int(data.get("snippet_limit", 8)),
        llm=LLMConfig(
            enabled=bool(llm.get("enabled", False)),
            provider=str(llm.get("provider", "")),
            model=str(llm.get("model", "")),
            base_url=str(llm.get("base_url", "")),
            api_key_env=str(llm.get("api_key_env", "")),
            env_file=Path(str(llm["env_file"])).expanduser() if llm.get("env_file") else None,
            timeout_seconds=int(llm.get("timeout_seconds", 60)),
            max_context_chars=int(llm.get("max_context_chars", 12000)),
            max_tokens=int(llm.get("max_tokens", 800)),
            temperature=float(llm.get("temperature", 0.1)),
        ),
        llm_agents=llm_agents,
        llm_default_agent=raw_default_agent,
        llm_category_agents=llm_category_agents,
    )


def load_env_files(wiki_root: Path, data: dict[str, Any], api: dict[str, Any]) -> None:
    env_files = [wiki_root / ".env"]
    for value in [data.get("env_file"), api.get("env_file")]:
        if value:
            env_files.append(resolve_config_path(wiki_root, value))
    for path in env_files:
        load_env_file(path)


def load_env_file(path: Path) -> None:
    try:
        lines = path.expanduser().read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_config_path(wiki_root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return wiki_root / path


def resolve_under_wiki(wiki_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return wiki_root / path


def _build_llm_config(payload: dict[str, Any], fallback: dict[str, Any]) -> LLMConfig:
    merged = {
        **fallback,
        **{str(key): value for key, value in payload.items() if isinstance(key, str)},
    }
    return LLMConfig(
        enabled=bool(merged.get("enabled", fallback.get("enabled", False))),
        provider=str(merged.get("provider", fallback.get("provider", ""))),
        model=str(merged.get("model", fallback.get("model", ""))),
        base_url=str(merged.get("base_url", fallback.get("base_url", ""))),
        api_key_env=str(merged.get("api_key_env", fallback.get("api_key_env", ""))),
        env_file=Path(str(merged.get("env_file"))).expanduser() if merged.get("env_file") else None,
        timeout_seconds=int(merged.get("timeout_seconds", fallback.get("timeout_seconds", 60))),
        max_context_chars=int(merged.get("max_context_chars", fallback.get("max_context_chars", 12000))),
        max_tokens=int(merged.get("max_tokens", fallback.get("max_tokens", 800))),
        temperature=float(merged.get("temperature", fallback.get("temperature", 0.1))),
    )


def llm_config_to_dict(name: str, config: LLMConfig) -> dict[str, Any]:
    return {
        "agent_name": name,
        "enabled": config.enabled,
        "provider": config.provider,
        "model": config.model,
        "base_url": config.base_url,
        "api_key_env": config.api_key_env,
        "env_file": str(config.env_file) if config.env_file else "",
        "timeout_seconds": config.timeout_seconds,
        "max_context_chars": config.max_context_chars,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
    }
