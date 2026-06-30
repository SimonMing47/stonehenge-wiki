from __future__ import annotations

import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .security import PermissionGuard

SAFE_BUILTINS = {
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "float",
    "int",
    "len",
    "list",
    "max",
    "min",
    "print",
    "range",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
}
UNSAFE_PY_NAMES = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
}
UNSAFE_IMPORTS = {"os", "subprocess", "shutil", "socket", "requests", "urllib", "pathlib"}


def run_code_file(path: Path, suffix: str, guard: PermissionGuard) -> tuple[bool, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if guard.code_text_is_dangerous(text):
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
        target = Path(tmp) / path.name
        target.write_text(text, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-I", str(target)],
            cwd=tmp,
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    output = (result.stdout or result.stderr).strip()
    return True, output


def python_ast_is_safe(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name.split(".")[0] in UNSAFE_IMPORTS:
                    return False
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in UNSAFE_PY_NAMES:
                return False
            if isinstance(node.func, ast.Attribute) and node.func.attr.startswith("__"):
                return False
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            return False
    return True


def run_js(path: Path, text: str) -> tuple[bool, str]:
    node = shutil.which("node")
    if not node:
        return True, "node 未安装，无法执行 JS"
    unsafe = ("require(", "process.", "child_process", "fs.", "eval(", "Function(")
    if any(item in text for item in unsafe):
        return False, ""
    with tempfile.TemporaryDirectory(prefix="stonehenge-wiki-js-") as tmp:
        target = Path(tmp) / path.name
        target.write_text(text, encoding="utf-8")
        result = subprocess.run([node, str(target)], cwd=tmp, text=True, capture_output=True, timeout=3, check=False)
    return True, (result.stdout or result.stderr).strip()


def run_java(path: Path, text: str) -> tuple[bool, str]:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        return True, "javac/java 未安装，无法执行 Java"
    unsafe = ("Runtime.getRuntime", "ProcessBuilder", "java.io.File", ".delete(", "Socket", "Files.")
    if any(item in text for item in unsafe):
        return False, ""
    with tempfile.TemporaryDirectory(prefix="stonehenge-wiki-java-") as tmp:
        target = Path(tmp) / path.name
        target.write_text(text, encoding="utf-8")
        compile_result = subprocess.run([javac, target.name], cwd=tmp, text=True, capture_output=True, timeout=5, check=False)
        if compile_result.returncode != 0:
            return True, compile_result.stderr.strip()
        class_name = path.stem
        result = subprocess.run([java, class_name], cwd=tmp, text=True, capture_output=True, timeout=3, check=False)
    return True, (result.stdout or result.stderr).strip()

