from __future__ import annotations

import ast
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from .security import PermissionGuard, normalize_security_text

try:  # resource is available on the Linux judging platform, not on Windows.
    import resource
except ImportError:  # pragma: no cover - platform-specific fallback
    resource = None  # type: ignore[assignment]


MAX_SOURCE_BYTES = 1_000_000
MAX_OUTPUT_BYTES = 64 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024

SAFE_PY_IMPORTS = {
    "base64",
    "bisect",
    "collections",
    "copy",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "fractions",
    "functools",
    "hashlib",
    "heapq",
    "itertools",
    "json",
    "math",
    "operator",
    "random",
    "re",
    "statistics",
    "string",
    "time",
    "typing",
}
UNSAFE_PY_NAMES = {
    "__builtins__",
    "__import__",
    "breakpoint",
    "builtins",
    "compile",
    "concurrent",
    "ctypes",
    "delattr",
    "dir",
    "eval",
    "exec",
    "exit",
    "getattr",
    "globals",
    "help",
    "importlib",
    "input",
    "inspect",
    "io",
    "locals",
    "memoryview",
    "modules",
    "multiprocessing",
    "open",
    "os",
    "pathlib",
    "pickle",
    "quit",
    "setattr",
    "site",
    "shutil",
    "socket",
    "sqlite3",
    "subprocess",
    "sys",
    "tempfile",
    "threading",
    "type",
    "vars",
}
UNSAFE_PY_ATTRIBUTES = {
    "builtins",
    "connect",
    "environ",
    "getenv",
    "import_module",
    "io",
    "modules",
    "open",
    "os",
    "popen",
    "read_bytes",
    "read_text",
    "recv",
    "rmdir",
    "rmtree",
    "send",
    "spawn",
    "subprocess",
    "sys",
    "system",
    "unlink",
    "write_bytes",
    "write_text",
}

JS_UNSAFE_PATTERNS = (
    r"\brequire\b",
    r"\b(?:process|global|globalThis|module|exports|__dirname|__filename)\b",
    r"\b(?:child_process|worker_threads|cluster|vm|fs|fs/promises|node:fs|node:net)\b",
    r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\b",
    r"\b(?:Deno|Bun)\b",
    r"\bimport\s*\(",
    r"(?:^|[;\r\n])\s*import\s+",
    r"\b(?:eval|Function|WebAssembly|SharedArrayBuffer|Atomics)\b",
    r"\b(?:constructor|__proto__|prototype)\b",
    r"\b(?:Reflect|Proxy)\b",
)

JAVA_SAFE_IMPORT_PREFIXES = (
    "java.lang.",
    "java.math.",
    "java.text.",
    "java.time.",
    "java.util.",
)
JAVA_UNSAFE_PATTERNS = (
    r"\bpackage\s+",
    r"\bimport\s+static\b",
    r"\bjava\s*\.\s*(?:io|net|nio\s*\.\s*file|sql|rmi)\b",
    r"\bjavax\s*\.",
    r"\b(?:sun|jdk)\s*\.\s*(?:misc|internal)\b",
    r"\b(?:Runtime|ProcessBuilder|ProcessHandle|ClassLoader|URLClassLoader|ScriptEngine)\b",
    r"\b(?:MethodHandles?|MethodType|VarHandle|ManagementFactory|Desktop)\b",
    r"\b(?:File|FileInputStream|FileOutputStream|RandomAccessFile|Files|Paths?|URL|URI|Socket|ServerSocket|HttpClient)\b",
    r"\b(?:Class\s*\.\s*forName|getClass|getDeclared\w*|getMethod|getField|setAccessible|invoke)\s*\(",
    r"\bSystem\s*\.\s*(?:getenv|getProperties|getProperty|setProperty|load|loadLibrary|console|setSecurityManager)\s*\(",
    r"\b(?:Thread|Executor|ForkJoinPool|CompletableFuture)\b",
    r"\bnative\b",
)


def run_code_file(path: Path, suffix: str, guard: PermissionGuard) -> tuple[bool, str]:
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            return False, ""
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False, ""
    if guard.path_blocked(path.as_posix(), operation="execute") or guard.code_text_is_dangerous(text):
        return False, ""
    if suffix == "py":
        return run_python(path, text)
    if suffix == "js":
        return run_js(path, text)
    if suffix == "java":
        return run_java(path, text)
    return True, "暂不支持该代码类型的自动执行"


def run_python(path: Path, text: str) -> tuple[bool, str]:
    if not python_ast_is_safe(text):
        return False, ""
    with tempfile.TemporaryDirectory(prefix="stonehenge-wiki-py-") as tmp:
        workdir = Path(tmp)
        target = workdir / safe_source_name(path.name, "snippet.py")
        target.write_text(text, encoding="utf-8")
        result = run_limited_process(
            [sys.executable, "-I", "-S", "-B", str(target)],
            workdir,
            timeout=3,
            memory_mb=256,
        )
    if not result.completed or result.returncode < 0:
        return False, ""
    return True, result.output


def python_ast_is_safe(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, MemoryError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] not in SAFE_PY_IMPORTS for alias in node.names):
                return False
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if node.level or module not in SAFE_PY_IMPORTS or any(alias.name == "*" for alias in node.names):
                return False
        elif isinstance(node, ast.alias):
            imported_name = node.name.split(".")[0].casefold()
            if (
                node.name.startswith("_")
                or imported_name in UNSAFE_PY_NAMES
                or (node.asname and (node.asname.startswith("__") or node.asname.casefold() in UNSAFE_PY_NAMES))
            ):
                return False
        elif isinstance(node, ast.Name):
            if node.id.startswith("__") or node.id.casefold() in UNSAFE_PY_NAMES:
                return False
        elif isinstance(node, ast.Attribute):
            attr = node.attr.casefold()
            if node.attr.startswith("_") or attr in UNSAFE_PY_ATTRIBUTES:
                return False
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id.casefold() in UNSAFE_PY_NAMES:
                return False
            if any(keyword.arg is None for keyword in node.keywords):
                # **kwargs can hide a mode or callable target from simple review.
                return False
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, str) and len(node.value) > 100_000:
                return False
            if isinstance(node.value, str) and re.search(r"__[A-Za-z0-9_]+__", node.value):
                return False
            if isinstance(node.value, (bytes, bytearray)) and len(node.value) > 100_000:
                return False
            if isinstance(node.value, int) and node.value.bit_length() > 16_384:
                return False
    return True


def run_js(path: Path, text: str) -> tuple[bool, str]:
    node = shutil.which("node")
    if not node:
        return True, "node 未安装，无法执行 JS"
    if not js_text_is_safe(text):
        return False, ""
    with tempfile.TemporaryDirectory(prefix="stonehenge-wiki-js-") as tmp:
        workdir = Path(tmp)
        target = workdir / safe_source_name(path.name, "snippet.js")
        target.write_text(text, encoding="utf-8")
        node_args = [node, "--max-old-space-size=128", "--disable-proto=throw"]
        if node_has_permission_model(node):
            node_args.extend(["--permission", f"--allow-fs-read={target}"])
        node_args.append(str(target))
        result = run_limited_process(
            node_args,
            workdir,
            timeout=3,
            # V8 reserves a large virtual code range even with a 128 MiB heap.
            # RLIMIT_AS therefore needs headroom; actual JS heap stays capped.
            memory_mb=2048,
        )
    if not result.completed or result.returncode < 0:
        return False, ""
    return True, result.output


def js_text_is_safe(text: str) -> bool:
    normalized = normalize_security_text(text)
    compact = re.sub(r"[\s'\"`+]+", "", normalized)
    return not any(
        re.search(pattern, normalized, re.MULTILINE)
        or re.search(pattern, compact, re.MULTILINE)
        for pattern in JS_UNSAFE_PATTERNS
    )


def run_java(path: Path, text: str) -> tuple[bool, str]:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        return True, "javac/java 未安装，无法执行 Java"
    if not java_text_is_safe(text):
        return False, ""
    with tempfile.TemporaryDirectory(prefix="stonehenge-wiki-java-") as tmp:
        workdir = Path(tmp)
        target = workdir / safe_source_name(path.name, "Snippet.java")
        target.write_text(text, encoding="utf-8")
        compile_result = run_limited_process(
            [javac, "-J-Xmx128m", "-J-XX:MaxMetaspaceSize=96m", "-proc:none", target.name],
            workdir,
            timeout=6,
            memory_mb=2048,
        )
        if not compile_result.completed or compile_result.returncode < 0:
            return False, ""
        if compile_result.returncode != 0:
            return True, compile_result.output
        class_name = target.stem
        result = run_limited_process(
            [
                java,
                "-Xmx128m",
                "-Xss256k",
                "-XX:MaxMetaspaceSize=96m",
                "-Djava.awt.headless=true",
                "-cp",
                ".",
                class_name,
            ],
            workdir,
            timeout=3,
            memory_mb=2048,
        )
    if not result.completed or result.returncode < 0:
        return False, ""
    return True, result.output


def java_text_is_safe(text: str) -> bool:
    normalized = normalize_security_text(text)
    compact = re.sub(r"[\s'\"+]+", "", normalized)
    for match in re.finditer(r"(?m)^\s*import\s+([A-Za-z0-9_.*]+)\s*;", normalized):
        imported = match.group(1)
        if not any(imported.startswith(prefix) for prefix in JAVA_SAFE_IMPORT_PREFIXES):
            return False
    for match in re.finditer(r"\b(java(?:x)?\.[A-Za-z0-9_.$]+)", normalized):
        qualified = match.group(1)
        if qualified.startswith("javax.") or not any(
            qualified.startswith(prefix) for prefix in JAVA_SAFE_IMPORT_PREFIXES
        ):
            return False
        if qualified.startswith(("java.lang.invoke.", "java.lang.management.")):
            return False
    return not any(
        re.search(pattern, normalized, re.MULTILINE)
        or re.search(pattern, compact, re.MULTILINE)
        for pattern in JAVA_UNSAFE_PATTERNS
    )


class ProcessResult:
    def __init__(self, completed: bool, returncode: int, output: str):
        self.completed = completed
        self.returncode = returncode
        self.output = output


def run_limited_process(
    args: list[str],
    workdir: Path,
    timeout: int,
    memory_mb: int,
) -> ProcessResult:
    stdout_path = workdir / ".stdout"
    stderr_path = workdir / ".stderr"
    completed = True
    returncode = -1
    with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
        popen_kwargs: dict = {
            "cwd": str(workdir),
            "stdin": subprocess.DEVNULL,
            "stdout": stdout_handle,
            "stderr": stderr_handle,
            "env": sandbox_environment(workdir),
            "start_new_session": True,
        }
        if resource is not None:
            popen_kwargs["preexec_fn"] = make_resource_limiter(timeout, memory_mb)
        try:
            proc = subprocess.Popen(args, **popen_kwargs)
        except (OSError, ValueError):
            return ProcessResult(False, -1, "")
        try:
            returncode = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            completed = False
            terminate_process_group(proc)
            returncode = proc.wait(timeout=2)
    stdout = read_limited(stdout_path)
    stderr = read_limited(stderr_path)
    output = (stdout or stderr).strip()
    return ProcessResult(completed, returncode, output)


def make_resource_limiter(timeout: int, memory_mb: int):
    def apply_limits() -> None:
        assert resource is not None
        memory_bytes = memory_mb * 1024 * 1024
        limits = (
            (resource.RLIMIT_CORE, 0, 0),
            (resource.RLIMIT_FSIZE, MAX_FILE_BYTES, MAX_FILE_BYTES),
            (resource.RLIMIT_NOFILE, 32, 32),
            (resource.RLIMIT_NPROC, 128, 128),
            (resource.RLIMIT_CPU, max(1, timeout), max(2, timeout + 1)),
            (resource.RLIMIT_AS, memory_bytes, memory_bytes),
        )
        for key, soft, hard in limits:
            try:
                resource.setrlimit(key, (soft, hard))
            except (OSError, ValueError):
                continue

    return apply_limits


def terminate_process_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()


def sandbox_environment(workdir: Path) -> dict[str, str]:
    # Do not inherit API keys, database credentials, proxy credentials, HOME, or
    # any application-specific environment values from the judging process.
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(workdir),
        "TMPDIR": str(workdir),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "NO_COLOR": "1",
    }


def read_limited(path: Path) -> str:
    try:
        data = path.read_bytes()[: MAX_OUTPUT_BYTES + 1]
    except OSError:
        return ""
    truncated = len(data) > MAX_OUTPUT_BYTES
    text = data[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    return text + ("\n[output truncated]" if truncated else "")


def safe_source_name(name: str, fallback: str) -> str:
    basename = Path(name).name
    return basename if basename and basename not in {".", ".."} else fallback


def node_has_permission_model(node: str) -> bool:
    try:
        result = subprocess.run(
            [node, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
            env={"PATH": os.environ.get("PATH", os.defpath)},
        )
        match = re.match(r"v?(\d+)", result.stdout.strip())
        return bool(match and int(match.group(1)) >= 22)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False
