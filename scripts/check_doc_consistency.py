from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DOCS = [
    Path("DESIGN.md"),
    Path("work/stonehenge_wiki/DESIGN.md"),
    Path("INSTRUCTION.md"),
    Path("stonehenge-wiki/README.md"),
]

DOC_FILES = [path for path in DOCS if path.exists()]

DOC_FLAG_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(--[A-Za-z][A-Za-z0-9_-]*[A-Za-z0-9])(?=\s|$|[\"'`\)]|\]|\})"
)
DOC_ROUTE_PATTERN = re.compile(r"(?<![A-Za-z0-9_])(/[A-Za-z][A-Za-z0-9_./-]*)")
PYTHON_CLI_PATH = Path("work/stonehenge_wiki/cli.py")
RUST_CLI_PATH = Path("work/skills/stonehenge-wiki/cli/src/lib.rs")
CONTRACT_PATH = Path("work/stonehenge_wiki/api_contract.py")
IGNORE_TOOLING_FLAGS = {
    "--all-targets",
    "--bin",
    "--check",
    "--format",
    "--manifest-path",
    "--pure",
    "--release",
}


def _normalize_route(path: str) -> str | None:
    if not path.startswith("/"):
        return None

    parsed = urlparse(path)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None
    route = parsed.path
    if not route:
        return None
    if "." in route:
        return None

    parts = [segment for segment in route.split("/") if segment]
    if not parts:
        return None

    first_level = parts[0]
    if first_level in {"work", "api.deepseek.com", "localhost", "127.0.0.1", "http"}:
        return None

    if first_level == "files":
        return "/files/{path}"
    if first_level == "assets":
        return "/assets/{path}"
    if len(parts) == 1:
        return f"/{first_level}"
    if len(parts) == 2:
        return f"/{first_level}/{parts[1]}"
    if first_level in {"wiki", "reports", "sources", "jobs", "wiki", "audit", "llm", "explain", "ask", "slides"}:
        return route

    return route


def _extract_code_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    in_fence = False
    fence = ""
    current_fence: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            marker = stripped.split()[0]
            if not in_fence:
                in_fence = True
                fence = marker
                current_fence = []
                continue
            if marker == fence or marker == "```":
                in_fence = False
                tokens.append("\n".join(current_fence))
                current_fence = []
                fence = ""
                continue
        if in_fence:
            current_fence.append(line)
            continue
        for match in re.finditer(r"`([^`]+)`", line):
            tokens.append(match.group(1))

    if current_fence:
        tokens.append("\n".join(current_fence))
    return tokens


def _extract_markdown_link_routes(text: str) -> list[str]:
    return [match.group(1) for match in re.finditer(r"\[[^]]*\]\(([^)\s]+)\)", text)]


def extract_python_cli_flags(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    flags: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "add_argument"):
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("--"):
                    flags.add(arg.value)
    return flags


def extract_rust_cli_flags(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r'"(--[A-Za-z][A-Za-z0-9_-]*[A-Za-z0-9])"', text))


def extract_contract_paths(path: Path) -> set[str]:
    namespace: dict[str, Any] = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    routes = [route for route in namespace["ROUTES"] if isinstance(route, dict)]
    return {route["path"] for route in routes if isinstance(route.get("path"), str)}


def extract_docs_flags(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    flags: set[str] = set()
    for chunk in _extract_code_tokens(text):
        flags.update(DOC_FLAG_PATTERN.findall(chunk))
    return {flag for flag in flags if flag not in IGNORE_TOOLING_FLAGS}


def extract_docs_routes(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    routes: set[str] = set()
    for chunk in _extract_code_tokens(text):
        for raw in DOC_ROUTE_PATTERN.findall(chunk):
            normalized = _normalize_route(raw)
            if normalized:
                routes.add(normalized)

    for raw in _extract_markdown_link_routes(text):
        normalized = _normalize_route(raw)
        if normalized:
            routes.add(normalized)
    return routes


def _is_api_like_route(route: str, top_level: set[str]) -> bool:
    parts = [segment for segment in route.split("/") if segment]
    return bool(parts and parts[0] in top_level)


def main() -> int:
    python_flags = extract_python_cli_flags(PYTHON_CLI_PATH)
    rust_flags = extract_rust_cli_flags(RUST_CLI_PATH)
    all_flags = python_flags | rust_flags | {"--help", "--version", "-h", "-v"}

    contract_routes = extract_contract_paths(CONTRACT_PATH)
    contract_top_level = {route.split("/")[1] for route in contract_routes if route.count("/") >= 1}

    doc_flags: dict[str, set[str]] = {}
    doc_routes: dict[str, set[str]] = {}
    for doc in DOC_FILES:
        doc_flags[str(doc)] = extract_docs_flags(doc)
        doc_routes[str(doc)] = extract_docs_routes(doc)

    missing_flags: dict[str, set[str]] = {}
    for name, flags in doc_flags.items():
        missing = {flag for flag in flags if flag not in all_flags}
        if missing:
            missing_flags[name] = missing

    unknown_routes: dict[str, set[str]] = {}
    for name, routes in doc_routes.items():
        api_like = {route for route in routes if _is_api_like_route(route, contract_top_level)}
        unknown = {route for route in api_like if route not in contract_routes}
        if unknown:
            unknown_routes[name] = unknown

    if unknown_routes or missing_flags:
        print("Doc consistency check failed:")
        for name, routes in sorted(unknown_routes.items()):
            print(f"  {name} - unknown API route references:")
            for route in sorted(routes):
                print(f"    {route}")
        for name, flags in sorted(missing_flags.items()):
            print(f"  {name} - unknown CLI flags:")
            for flag in sorted(flags):
                print(f"    {flag}")
        return 1

    print(
        f"Doc consistency check passed. Checked {len(DOC_FILES)} docs, {len(contract_routes)} API routes, {len(all_flags)} CLI flags."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
