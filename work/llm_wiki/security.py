from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path


PASSWORD_RE = re.compile(
    r"(密码|口令|密钥|秘钥|token|secret|passwd|password|credential|access[_-]?key)",
    re.IGNORECASE,
)
SYSTEM_SECRET_RE = re.compile(
    r"(系统密码|本机密码|root密码|管理员密码|/etc|shadow|keychain|钥匙串|读取系统目录)",
    re.IGNORECASE,
)
ENV_ALLOW_RE = re.compile(r"(02_环境信息|docs/02_环境信息|环境信息)", re.IGNORECASE)
PROMPT_INJECTION_RE = re.compile(
    r"(忽略(?:前面|以上|所有).{0,12}规则|开启上帝模式|上帝模式|强制结束|删除全部文档|"
    r"kill\s+codeagent|ignore\s+(all\s+)?previous|god\s*mode|prompt\s*injection)",
    re.IGNORECASE,
)
MUTATING_INTENT_RE = re.compile(
    r"(删除|清空|覆盖|写入|修改|修复|执行|运行|kill|remove|delete|del\s+|rm\s+-rf|"
    r"remove-item|format|shutdown|reboot)",
    re.IGNORECASE,
)


class PermissionGuard:
    def __init__(self, wiki_root: Path):
        self.wiki_root = wiki_root
        self.permission_path = wiki_root / "Permission.json"
        self.dir_deny: list[str] = []
        self.command_deny: list[str] = []
        self.file_deny: list[str] = []
        self.load()

    def load(self) -> None:
        if not self.permission_path.exists():
            return
        try:
            data = json.loads(self.permission_path.read_text(encoding="utf-8"))
        except Exception:
            return
        self.dir_deny = list(data.get("dir", {}).get("deny", []) or [])
        self.command_deny = list(data.get("command", {}).get("deny", []) or [])
        self.file_deny = list(data.get("file", {}).get("deny", []) or [])

    def has_password_intent(self, text: str) -> bool:
        return bool(PASSWORD_RE.search(text))

    def password_allowed_by_title(self, text: str) -> bool:
        return bool(ENV_ALLOW_RE.search(text)) and not bool(SYSTEM_SECRET_RE.search(text))

    def contains_prompt_injection(self, text: str) -> bool:
        return bool(PROMPT_INJECTION_RE.search(text))

    def is_env_path(self, rel_path: str) -> bool:
        normalized = rel_path.replace("\\", "/").lower()
        return normalized.startswith("docs/02_环境信息/") or "/02_环境信息/" in normalized

    def check_question(
        self,
        title: str,
        candidate_paths: list[str] | None = None,
        operation: str = "read",
    ) -> tuple[bool, str]:
        text = title or ""
        if self.contains_prompt_injection(text):
            return True, "prompt_injection"
        if self.has_password_intent(text) and SYSTEM_SECRET_RE.search(text):
            return True, "password"
        if self._text_hits_any(text, self.command_deny):
            return True, "denied_command"
        if self._text_hits_any(text, self.file_deny):
            return True, "denied_file"
        if MUTATING_INTENT_RE.search(text) and self._text_hits_any(text, self.dir_deny):
            return True, "denied_dir"
        for rel_path in candidate_paths or []:
            if self.path_blocked(rel_path, operation):
                return True, "permission_path"
        return False, ""

    def path_blocked(self, rel_path: str, operation: str = "read") -> bool:
        normalized = rel_path.replace("\\", "/")
        basename = Path(normalized).name
        for pattern in self.file_deny:
            if self._pattern_matches_path(pattern, normalized, basename):
                return True
        if operation != "read":
            for pattern in self.dir_deny:
                if self._pattern_matches_path(pattern, normalized, basename):
                    return True
        return False

    def code_text_is_dangerous(self, text: str) -> bool:
        danger = re.compile(
            r"(os\.system|subprocess|shutil\.rmtree|os\.remove|os\.unlink|Path\(.+unlink|"
            r"eval\(|exec\(|open\(.+['\"]w|socket|requests\.|urllib\.request|Runtime\.getRuntime|"
            r"ProcessBuilder|child_process|require\(['\"]fs|process\.env)",
            re.IGNORECASE | re.DOTALL,
        )
        return bool(danger.search(text))

    def _text_hits_any(self, text: str, patterns: list[str]) -> bool:
        low = text.lower()
        tokens = re.findall(r"[\w./\\:*?-]+", low)
        for pattern in patterns:
            if not pattern:
                continue
            p = pattern.lower()
            if "*" in p:
                if fnmatch.fnmatch(low, f"*{p}*"):
                    return True
                if any(fnmatch.fnmatch(token, p) for token in tokens):
                    return True
            elif p in low:
                return True
        return False

    def _pattern_matches_path(self, pattern: str, normalized: str, basename: str) -> bool:
        p = pattern.replace("\\", "/")
        return (
            fnmatch.fnmatch(normalized, p)
            or fnmatch.fnmatch(basename, p)
            or fnmatch.fnmatch(normalized, f"*{p}*")
        )
