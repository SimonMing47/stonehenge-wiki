from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def default_opencode_config() -> dict[str, Any]:
    """Runtime defaults for evaluation roots that do not ship config.json."""
    provider = os.environ.get("OPENCODE_PROVIDER", "zhipu").strip() or "zhipu"
    model = os.environ.get("OPENCODE_MODEL", "glm-5.2").strip() or "glm-5.2"
    runtime_command = (
        os.environ.get("OPENCODE_RUNTIME_COMMAND", "opencode run --pure --format json").strip()
        or "opencode run --pure --format json"
    )
    profile = {
        "enabled": True,
        "provider": provider,
        "model": model,
        "timeout_seconds": 120,
        "max_context_chars": 16000,
        "max_tokens": 900,
        "temperature": 0.1,
        "runtime_mode": "opencode",
        "runtime_command": runtime_command,
    }
    return {
        **profile,
        "default_agent": "opencode",
        "agents": {"opencode": dict(profile)},
        "category_agents": {},
    }


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = False
    provider: str = ""
    model: str = ""
    timeout_seconds: int = 60
    max_context_chars: int = 12000
    max_tokens: int = 800
    temperature: float = 0.1
    runtime_mode: str = "opencode"
    runtime_command: str = ""


@dataclass(frozen=True)
class PlatformConfig:
    wiki_root: Path
    state_dir: Path
    database_path: Path
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    api_token_env: str = "STONEHENGE_WIKI_API_TOKEN"
    api_read_token_env: str = "STONEHENGE_WIKI_READ_TOKEN"
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
    if config_path.is_symlink():
        raise ValueError("wiki config must not be a symbolic link")
    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            data = loaded if isinstance(loaded, dict) else {}
        except (OSError, UnicodeError, json.JSONDecodeError):
            data = {}

    api = data.get("api", {}) if isinstance(data.get("api", {}), dict) else {}

    # State paths are fixed below the wiki root. Judge-provided config cannot
    # redirect SQLite writes into the host filesystem.
    state_dir = wiki_root / ".state"
    database_path = state_dir / "wiki.sqlite"
    if state_dir.is_symlink() or database_path.is_symlink():
        raise ValueError("wiki state path must not be a symbolic link")

    # The wiki root is judge-provided, untrusted input. It may tune harmless
    # limits or disable the model for an offline fixture, but it must never
    # select an executable, env file, credential source, or direct API mode.
    # OpenCode provider/model/command settings come only from trusted process
    # environment defaults and the user-level OpenCode configuration.
    raw_llm = data.get("llm") if isinstance(data.get("llm"), dict) else {}
    trusted_llm = default_opencode_config()
    trusted_profile = dict(trusted_llm["agents"]["opencode"])
    formal_judge_root = wiki_root == Path("/app/code/judge-assets/01_01_llm_wiki").resolve()
    if not formal_judge_root:
        trusted_profile["enabled"] = bool(raw_llm.get("enabled", trusted_profile["enabled"]))
    for key, minimum, maximum in (
        ("timeout_seconds", 10, 600),
        ("max_context_chars", 2000, 64000),
        ("max_tokens", 64, 4096),
    ):
        try:
            trusted_profile[key] = max(minimum, min(int(raw_llm.get(key, trusted_profile[key])), maximum))
        except (TypeError, ValueError):
            pass
    base_profile = _build_llm_config(trusted_profile, {})
    llm_agents = {"opencode": base_profile}
    raw_default_agent = "opencode"
    raw_category_agents = raw_llm.get("category_agents", {})
    llm_category_agents: dict[str, str] = {}
    if isinstance(raw_category_agents, dict):
        for raw_category in raw_category_agents:
            if isinstance(raw_category, str) and raw_category.strip():
                llm_category_agents[raw_category.strip()] = "opencode"
    return PlatformConfig(
        wiki_root=wiki_root,
        state_dir=state_dir,
        database_path=database_path,
        api_host="127.0.0.1",
        api_port=bounded_int(api.get("port", data.get("api_port", 8765)), 8765, 1, 65535),
        api_token_env=str(api.get("token_env", data.get("api_token_env", "STONEHENGE_WIKI_API_TOKEN"))),
        api_read_token_env=str(api.get("read_token_env", data.get("api_read_token_env", "STONEHENGE_WIKI_READ_TOKEN"))),
        audit_enabled=True,
        persist_index=True,
        snippet_limit=bounded_int(data.get("snippet_limit", 8), 8, 1, 100),
        llm=LLMConfig(
            enabled=base_profile.enabled,
            provider=base_profile.provider,
            model=base_profile.model,
            timeout_seconds=base_profile.timeout_seconds,
            max_context_chars=base_profile.max_context_chars,
            max_tokens=base_profile.max_tokens,
            temperature=base_profile.temperature,
            runtime_mode="opencode",
            runtime_command=base_profile.runtime_command,
        ),
        llm_agents=llm_agents,
        llm_default_agent=raw_default_agent,
        llm_category_agents=llm_category_agents,
    )


def bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, min(parsed, maximum))


def _build_llm_config(payload: dict[str, Any], fallback: dict[str, Any]) -> LLMConfig:
    merged = {
        **fallback,
        **{str(key): value for key, value in payload.items() if isinstance(key, str)},
    }
    return LLMConfig(
        enabled=bool(merged.get("enabled", fallback.get("enabled", False))),
        provider=str(merged.get("provider", fallback.get("provider", ""))),
        model=str(merged.get("model", fallback.get("model", ""))),
        timeout_seconds=int(merged.get("timeout_seconds", fallback.get("timeout_seconds", 60))),
        max_context_chars=int(merged.get("max_context_chars", fallback.get("max_context_chars", 12000))),
        max_tokens=int(merged.get("max_tokens", fallback.get("max_tokens", 800))),
        temperature=float(merged.get("temperature", fallback.get("temperature", 0.1))),
        runtime_mode="opencode",
        runtime_command=str(merged.get("runtime_command", fallback.get("runtime_command", ""))).strip(),
    )


def llm_config_to_dict(name: str, config: LLMConfig) -> dict[str, Any]:
    return {
        "agent_name": name,
        "enabled": config.enabled,
        "provider": config.provider,
        "model": config.model,
        "timeout_seconds": config.timeout_seconds,
        "max_context_chars": config.max_context_chars,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "runtime_mode": config.runtime_mode,
        "runtime_command": config.runtime_command,
    }
