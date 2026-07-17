from __future__ import annotations

import json
import re
import unicodedata
from html import unescape
from pathlib import Path, PurePosixPath
from urllib.parse import unquote


# Secret *intent* is deliberately broader than assignment detection.  A question
# asking for any credential must stay on the deterministic path and may only read
# sources under docs/02_环境信息.
PASSWORD_RE = re.compile(
    r"(密码|口令|密钥|秘钥|凭据|令牌|token|secret|passwd|password|credential|"
    r"api[_\s-]?key|access[_\s-]?key|private[_\s-]?key|pwd)",
    re.IGNORECASE,
)
SYSTEM_SECRET_RE = re.compile(
    r"(系统密码|本机密码|root.{0,8}(?:密码|口令)|管理员.{0,8}(?:密码|口令)|系统密钥|本机密钥|"
    r"/etc/(?:passwd|shadow)|sam\s*数据库|keychain|钥匙串|读取系统目录|"
    r"99_mock_system_dir.{0,80}(?:密码|口令|密钥)|"
    r"(?:\.ssh|ssh)[/\\](?:id_rsa|id_ed25519))",
    re.IGNORECASE,
)
ENV_ALLOW_RE = re.compile(r"(?:^|[/\\])02_环境信息(?:[/\\]|$)|docs[/\\]02_环境信息|环境信息", re.IGNORECASE)

# The expressions are evaluated both on normalized text and on a compact form
# which joins string literals.  This catches constructs such as
# "ignore " + "previous instructions" without attempting to execute code.
PROMPT_INJECTION_PATTERNS = (
    re.compile(
        r"(?:忽略|无视|不要理会|跳过|绕过)(?:前面|之前|此前|前述|以上|上述|先前|原有|所有|全部|安全){0,2}"
        r"(?:的)?(?:所有|全部)?(?:规则|指令|要求|提示词|提示|约束|策略|政策)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:开启|打开|进入|切换到?)(?:上帝|开发者|无限制|超级管理员)模式", re.IGNORECASE),
    re.compile(r"(?:删除|清空|销毁)(?:全部|所有|整个)(?:文档|文件|数据|目录|知识库)", re.IGNORECASE),
    re.compile(r"(?:强制)?(?:kill|结束|终止|停止)(?:codeagent|opencode|代理|进程|任务)", re.IGNORECASE),
    re.compile(
        r"(?:ignore|disregard|forget|bypass|override)(?:all|any|the)?"
        r"(?:previous|prior|above|earlier|old|system)?"
        r"(?:instructions?|rules?|prompts?|constraints?|messages?|polic(?:y|ies))",
        re.IGNORECASE,
    ),
    re.compile(r"(?:ignore|disregard|forget)(?:everything|anything)(?:above|before|previously)", re.IGNORECASE),
    re.compile(r"(?:enable|enter|activate|switchto)(?:god|developer|unrestricted|root|admin)mode", re.IGNORECASE),
    re.compile(r"(?:reveal|print|leak|show)(?:the)?(?:hidden|system|developer)(?:prompt|instructions?)", re.IGNORECASE),
    re.compile(r"(?:jailbreak|doanythingnow|danmode)", re.IGNORECASE),
)

MUTATING_INTENT_RE = re.compile(
    r"(删除|清空|覆盖|写入|修改|修复|执行|运行|重命名|移动|复制|创建|"
    r"kill|remove|delete|erase|write|modify|execute|run|move|rename|copy|truncate|"
    r"remove-item|format|shutdown|reboot|poweroff|mkfs)",
    re.IGNORECASE,
)
HOST_FILE_ACCESS_RE = re.compile(
    r"(?:"
    r"[a-zA-Z]:[/\\]|"
    r"[a-zA-Z]\s*盘\s*(?:根目录|根路径|目录|文件)|"
    r"(?:drive\s+)?[a-zA-Z]\s+drive\b|"
    r"/(?:etc|root|home|Users|proc|sys|dev|var|usr|opt|boot|run)(?:[/\\]|\s|$)|"
    r"/(?:var[/\\](?:run|lib)[/\\](?:secrets?|kubelet))(?:[/\\]|\s|$)|"
    r"(?:~|\$HOME|%USERPROFILE%)[/\\](?:\.ssh|\.aws|\.config)(?:[/\\]|\s|$)|"
    r"(?:系统|本机|服务器|Linux|Windows).{0,8}(?:根目录|主目录)|"
    r"\\\\[^\s\\]+[/\\][^\s\\]+|"
    r"\.\.[/\\]"
    r")",
    re.IGNORECASE,
)
HOST_FILE_ACCESS_INTENT_RE = re.compile(
    r"(读取|查看|列出|遍历|扫描|打开|访问|输出|获取|告诉|"
    r"read|list|scan|open|access|dump|cat|get-content|type\s+|ls\b|dir\b)",
    re.IGNORECASE,
)
HIGH_RISK_COMMAND_RE = re.compile(
    r"(?:"
    r"\brm\s+[^\r\n]+|"
    r"\bremove-item\b|"
    r"(?:^|[;&|]\s*|(?:使用|执行|运行)\s+)del\s+(?:/[A-Za-z]+\s+)?[^\r\n]+|"
    r"\brmdir\b[^\r\n]*(?:/s|--ignore-fail-on-non-empty)|"
    r"\b(?:shred|sdelete|clear-content)\b|"
    r"\bgit\s+(?:clean\s+-[A-Za-z]*[fd]|reset\s+--hard)\b|"
    r"\bfind\b[^\r\n]+\s-delete\b|"
    r"\b(?:mkfs(?:\.[A-Za-z0-9]+)?|format|shutdown|reboot|poweroff|halt)\b|"
    r"\bdd\s+[^\r\n]*\bof\s*=|"
    r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;\s*:|"
    r"(?:彻底|强制|永久)?(?:删除|清空|销毁)(?:全部|所有|整个)"
    r")",
    re.IGNORECASE,
)
DESTRUCTIVE_FILE_ACTION_RE = re.compile(
    r"(?:删除|清空|销毁).{0,120}(?:docs[/\\]|文件|文档|目录|[\w\u4e00-\u9fff.-]+\.[A-Za-z0-9]{1,12})",
    re.IGNORECASE,
)
DOCUMENT_ACTION_DELEGATION_RE = re.compile(
    r"(?:完成|执行).{0,120}(?:描述的|要求的)(?:工作|任务|操作)",
    re.IGNORECASE,
)

ZERO_WIDTH_RE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_.$~%:\-*/\\?\[\]\u4e00-\u9fff]+")
UNICODE_ESCAPE_RE = re.compile(r"\\u\{([0-9a-fA-F]{1,6})\}|\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})")


def _decode_unicode_escape(match: re.Match[str]) -> str:
    value = next(group for group in match.groups() if group is not None)
    codepoint = int(value, 16)
    return chr(codepoint) if codepoint <= 0x10FFFF else match.group(0)


def normalize_security_text(text: str) -> str:
    """Normalize presentation tricks without interpreting or executing content."""

    value = unicodedata.normalize("NFKC", unescape(unquote(str(text or ""))))
    value = UNICODE_ESCAPE_RE.sub(_decode_unicode_escape, value)
    value = ZERO_WIDTH_RE.sub("", value)
    value = value.replace("\\\r\n", "").replace("\\\n", "")
    return value


def compact_security_text(text: str) -> str:
    """Join common source-code string fragments for signature matching."""

    value = normalize_security_text(text)
    # Quotes, concatenation operators, comments and whitespace are separators an
    # attacker can use to split a dangerous instruction.  Keep path/command
    # punctuation because those characters carry security meaning elsewhere.
    return re.sub(r"[\s'\"`+&|(),;{}]+", "", value)


def contains_prompt_injection_text(text: str) -> bool:
    normalized = normalize_security_text(text)
    compact = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "", normalized)
    return any(pattern.search(normalized) or pattern.search(compact) for pattern in PROMPT_INJECTION_PATTERNS)


def simple_glob_match(value: str, pattern: str) -> bool:
    """Case-insensitive glob matcher where only ``*`` has special meaning."""

    normalized_value = normalize_security_text(value).replace("\\", "/").casefold()
    normalized_pattern = normalize_security_text(pattern).replace("\\", "/").casefold()
    expression = "^" + re.escape(normalized_pattern).replace(r"\*", ".*") + "$"
    return bool(re.match(expression, normalized_value, flags=re.DOTALL))


class PermissionGuard:
    def __init__(self, wiki_root: Path):
        self.wiki_root = wiki_root
        self.permission_path = wiki_root / "Permission.json"
        self.dir_deny: list[str] = []
        self.command_deny: list[str] = []
        self.file_deny: list[str] = []
        self.load()

    def load(self) -> None:
        self.dir_deny = []
        self.command_deny = []
        self.file_deny = []
        if self.permission_path.is_symlink():
            return
        if not self.permission_path.exists():
            return
        try:
            data = json.loads(self.permission_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        self.dir_deny = self._rule_list(data, "dir")
        self.command_deny = self._rule_list(data, "command")
        self.file_deny = self._rule_list(data, "file")

    @staticmethod
    def _rule_list(data: dict, section: str) -> list[str]:
        section_value = data.get(section, {})
        raw = section_value.get("deny", []) if isinstance(section_value, dict) else []
        if not isinstance(raw, list):
            return []
        result: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                continue
            value = normalize_security_text(item).strip()
            if value and value not in result:
                result.append(value)
        return result

    def has_password_intent(self, text: str) -> bool:
        return bool(PASSWORD_RE.search(normalize_security_text(text)))

    def password_allowed_by_title(self, text: str) -> bool:
        normalized = normalize_security_text(text)
        return bool(ENV_ALLOW_RE.search(normalized)) and not bool(SYSTEM_SECRET_RE.search(normalized))

    def password_paths_allowed(self, candidate_paths: list[str] | None) -> bool:
        paths = [path for path in (candidate_paths or []) if str(path).strip()]
        return bool(paths) and all(self.is_env_path(path) and not self.path_blocked(path, "read") for path in paths)

    def contains_prompt_injection(self, text: str) -> bool:
        return contains_prompt_injection_text(text)

    def is_env_path(self, rel_path: str) -> bool:
        normalized = self._normalize_path(rel_path).casefold().lstrip("/")
        parts = PurePosixPath(normalized).parts
        return len(parts) >= 2 and parts[0] == "docs" and parts[1] == "02_环境信息".casefold()

    def check_question(
        self,
        title: str,
        candidate_paths: list[str] | None = None,
        operation: str = "read",
    ) -> tuple[bool, str]:
        text = normalize_security_text(title or "")
        operation = (operation or "read").strip().lower()
        if self.contains_prompt_injection(text):
            return True, "prompt_injection"
        if self._contains_host_file_access(text):
            return True, "system_path"
        if DOCUMENT_ACTION_DELEGATION_RE.search(text):
            return True, "document_action_delegation"
        if self.has_password_intent(text):
            if SYSTEM_SECRET_RE.search(text):
                return True, "password"
            # Candidate paths are authoritative once retrieval has resolved them.
            # Before retrieval, generic credential questions remain eligible only
            # for the caller's environment-folder-only search path.
            if candidate_paths is not None and not self.password_paths_allowed(candidate_paths):
                return True, "password_outside_env_path"
        if self._text_hits_commands(text):
            return True, "denied_command"
        if self._text_hits_paths(text, self.file_deny, kind="file"):
            return True, "denied_file"
        if operation != "read" and self._text_hits_paths(text, self.dir_deny, kind="dir"):
            return True, "denied_dir"
        if (
            DESTRUCTIVE_FILE_ACTION_RE.search(text)
            or HIGH_RISK_COMMAND_RE.search(text)
            or HIGH_RISK_COMMAND_RE.search(compact_security_text(text))
        ):
            return True, "high_risk_command"
        for rel_path in candidate_paths or []:
            if self.path_blocked(rel_path, operation):
                return True, "permission_path"
        return False, ""

    def path_blocked(self, rel_path: str, operation: str = "read") -> bool:
        normalized = self._normalize_path(rel_path)
        if not normalized:
            return False
        if self._path_escapes_wiki_root(normalized):
            return True
        basename = normalized.rstrip("/").rsplit("/", 1)[-1]
        for pattern in self.file_deny:
            if self._pattern_matches_file(pattern, normalized, basename):
                return True
        if (operation or "read").strip().lower() != "read":
            for pattern in self.dir_deny:
                if self._pattern_matches_dir(pattern, normalized):
                    return True
        return False

    def _path_escapes_wiki_root(self, value: str) -> bool:
        root = self.wiki_root.resolve()
        raw = Path(value)
        candidate = raw if raw.is_absolute() else root / raw
        lexically_inside = candidate == root or root in candidate.parents
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            return True
        if resolved != root and root not in resolved.parents:
            # Absolute paths can be legitimate explicit import sources and are
            # still checked against Permission patterns. Relative wiki paths,
            # however, must never escape through `..` or a symlink.
            return not raw.is_absolute() or lexically_inside
        current = candidate
        while current != root:
            if current.is_symlink():
                return True
            parent = current.parent
            if parent == current:
                return True
            current = parent
        return False

    def code_text_is_dangerous(self, text: str) -> bool:
        normalized = normalize_security_text(text)
        if self.contains_prompt_injection(normalized):
            return True
        # Preserve call punctuation for code signatures while joining quoted
        # fragments such as `"requ" + "ire"("fs")`.
        code_compact = re.sub(r"[\s'\"`+]+", "", normalized)
        danger_patterns = (
            r"\bos\s*\.\s*(?:system|remove|unlink|rmdir)\s*\(",
            r"\bsubprocess\b",
            r"\bshutil\s*\.\s*rmtree\s*\(",
            r"\bpath\s*\([^)]*\)\s*\.\s*(?:unlink|rmdir|write_text|write_bytes)\s*\(",
            r"\b(?:eval|exec|compile)\s*\(",
            r"\bopen\s*\([^)]*,\s*['\"](?:w|a|x|\+)",
            r"\b(?:socket|requests|urllib\s*\.\s*request)\b",
            r"runtime\s*\.\s*getruntime\s*\(",
            r"\bprocessbuilder\s*\(",
            r"\bchild_process\b",
            r"\brequire\s*\(\s*['\"](?:fs|child_process)",
            r"\bprocess\s*\.\s*env\b",
            r"\b(?:fetch|xmlhttprequest|websocket)\s*\(",
            r"\b(?:deno|bun)\s*\.",
            r"\bimport\s*\(\s*['\"](?:node:)?(?:fs|child_process|net|http|https)",
            r"\bjava\s*\.\s*(?:io|net|nio\s*\.\s*file)\b",
            r"\bclass\s*\.\s*forname\s*\(",
            r"\b(?:getdeclaredmethod|setaccessible)\s*\(",
            r"\b(?:rm|del|remove-item|mkfs|format)\b[^\r\n]*(?:-rf|-recurse|-force)",
        )
        if any(re.search(pattern, normalized, re.IGNORECASE | re.DOTALL) for pattern in danger_patterns):
            return True
        # Compact checks catch only strong signatures to avoid treating ordinary
        # string concatenation as executable code.
        compact_danger = (
            "os.system(",
            "shutil.rmtree(",
            "runtime.getruntime(",
            "processbuilder(",
            "child_process",
            "process.env",
            "subprocess",
            "require(",
            "[require]",
            "globalthis[",
            "eval(",
            "exec(",
            "import(node:fs",
            "import(fs",
            "java.io",
            "java.net",
            "java.nio.file",
            "class.forname(",
        )
        return "Function(" in code_compact or any(
            signature in code_compact.casefold() for signature in compact_danger
        )

    def prompt_injection_line(self, text: str) -> tuple[int | None, str]:
        """Return the first line participating in an injection, including splits."""

        lines = str(text or "").splitlines()
        for index, line in enumerate(lines):
            if self.contains_prompt_injection(line):
                return index + 1, line
        for index in range(len(lines)):
            window = "\n".join(lines[index : index + 4])
            if self.contains_prompt_injection(window):
                return index + 1, " ".join(part.strip() for part in lines[index : index + 4] if part.strip())
        if self.contains_prompt_injection(text):
            first = next(((index + 1, line) for index, line in enumerate(lines) if line.strip()), (1, ""))
            return first
        return None, ""

    def _contains_host_file_access(self, text: str) -> bool:
        return bool(HOST_FILE_ACCESS_RE.search(text) and HOST_FILE_ACCESS_INTENT_RE.search(text))

    def _text_hits_commands(self, text: str) -> bool:
        normalized = normalize_security_text(text)
        compact = compact_security_text(text)
        for pattern in self.command_deny:
            if self._command_pattern_matches(normalized, pattern) or self._command_pattern_matches(compact, pattern):
                return True
        return False

    def _command_pattern_matches(self, text: str, pattern: str) -> bool:
        p = normalize_security_text(pattern).strip()
        if not p:
            return False
        # Only '*' is a wildcard; whitespace in a configured command tolerates
        # shell formatting differences.  Boundaries prevent `del` matching
        # innocent words such as `model`.
        body = re.escape(p).replace(r"\*", ".*")
        body = re.sub(r"(?:\\\ )+", r"\\s+", body)
        expression = rf"(?<![\w-]){body}(?![\w-])"
        return bool(re.search(expression, text, re.IGNORECASE | re.DOTALL))

    def _text_hits_paths(self, text: str, patterns: list[str], kind: str) -> bool:
        if kind == "file" and any(self._file_pattern_occurs_in_text(text, pattern) for pattern in patterns):
            return True
        candidates = [token.strip(".,;:(){}<>\"'") for token in PATH_TOKEN_RE.findall(text)]
        candidates.extend(match.group(0) for match in re.finditer(r"[^\s'\"`]+[/\\][^\s'\"`]+", text))
        for candidate in candidates:
            normalized = self._normalize_path(candidate)
            if not normalized:
                continue
            basename = normalized.rstrip("/").rsplit("/", 1)[-1]
            for pattern in patterns:
                matched = (
                    self._pattern_matches_file(pattern, normalized, basename)
                    if kind == "file"
                    else self._pattern_matches_dir(pattern, normalized)
                )
                if matched:
                    return True
        return False

    def _file_pattern_occurs_in_text(self, text: str, pattern: str) -> bool:
        p = self._normalize_path(pattern)
        if not p:
            return False
        body = re.escape(p).replace(r"\*", r"[^\s/\\]*")
        # ASCII filename characters define the boundary.  Chinese prose can
        # immediately follow a mentioned filename (e.g. "spark-prod.env中").
        expression = rf"(?<![A-Za-z0-9_.-]){body}(?![A-Za-z0-9_.-])"
        normalized = normalize_security_text(text).replace("\\", "/")
        return bool(re.search(expression, normalized, re.IGNORECASE))

    @staticmethod
    def _normalize_path(value: str) -> str:
        path = normalize_security_text(str(value or "")).strip().strip("\"'").replace("\\", "/")
        path = re.sub(r"(?<!:)/{2,}", "/", path)
        while path.startswith("./"):
            path = path[2:]
        return path.rstrip("/") if path not in {"/", ""} else path

    def _pattern_matches_file(self, pattern: str, normalized: str, basename: str) -> bool:
        p = self._normalize_path(pattern)
        if not p:
            return False
        if "/" in p:
            return simple_glob_match(normalized, p) or simple_glob_match(normalized.lstrip("/"), p.lstrip("/"))
        return simple_glob_match(basename, p)

    def _pattern_matches_dir(self, pattern: str, normalized: str) -> bool:
        p = self._normalize_path(pattern)
        if not p:
            return False
        value = normalized.rstrip("/")
        is_absolute = value.startswith("/")
        parts = [part for part in value.split("/") if part]
        # Match every ancestor so that denying docs/private also protects
        # docs/private/report.md.  A slash-free pattern names a directory
        # component; path patterns match the accumulated ancestor path.
        ancestors: list[str] = []
        for index in range(1, len(parts) + 1):
            ancestor = "/".join(parts[:index])
            ancestors.append("/" + ancestor if is_absolute else ancestor)
        if "/" not in p:
            return any(simple_glob_match(part, p) for part in parts)
        return any(
            simple_glob_match(ancestor, p)
            or simple_glob_match(ancestor.lstrip("/"), p.lstrip("/"))
            for ancestor in ancestors
        )

    # Kept for callers and extensions that used the old internal helpers.
    def _text_hits_any(self, text: str, patterns: list[str]) -> bool:
        return self._text_hits_paths(text, patterns, kind="file")

    def _pattern_matches_path(self, pattern: str, normalized: str, basename: str) -> bool:
        return self._pattern_matches_file(pattern, self._normalize_path(normalized), basename)
