from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from .api_contract import ROUTES, api_contract

VALID_METHODS = {"GET", "POST"}
VALID_SCOPES = {"public", "read", "admin"}
PATH_PARAM_PREFIXES = {
    "/assets/{path}": "/assets/",
    "/files/{path}": "/files/",
}


def verify_api_contract(repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    contract = api_contract()
    routes = contract["routes"]
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(validate_contract_shape(contract, routes))

    server_routes = extract_server_routes(root / "work" / "stonehenge_wiki" / "server.py")
    server_scopes = extract_server_scopes(root / "work" / "stonehenge_wiki" / "server.py")
    contract_routes = {(route["method"], route["path"]) for route in routes}
    missing_in_contract = sorted(server_routes - contract_routes)
    missing_in_server = sorted(contract_routes - server_routes)
    for method, path in missing_in_contract:
        errors.append(f"server route {method} {path} is missing from api_contract.ROUTES")
    for method, path in missing_in_server:
        errors.append(f"contract route {method} {path} is missing from server.py")
    for route in routes:
        key = (route["method"], route["path"])
        server_scope = server_scopes.get(key)
        if server_scope is None:
            continue
        if route["scope"] != server_scope:
            errors.append(
                f"contract scope mismatch for {route['method']} {route['path']}: "
                f"contract={route['scope']} server={server_scope}"
            )

    rust_cli = (root / "work" / "skills" / "stonehenge-wiki" / "cli" / "src" / "lib.rs").read_text(encoding="utf-8")
    contract_flags = sorted(extract_contract_cli_flags(routes))
    missing_flags = [flag for flag in contract_flags if flag not in rust_cli]
    for flag in missing_flags:
        errors.append(f"contract CLI flag {flag} is not present in Rust CLI source")

    rust_paths = extract_rust_cli_paths(rust_cli)
    contract_path_values = {path for _method, path in contract_routes}
    missing_rust_paths = sorted(path for path in rust_paths if path not in contract_path_values)
    for path in missing_rust_paths:
        warnings.append(f"Rust CLI references {path}, but it is not a standalone contract path")

    return {
        "status": "ok" if not errors else "error",
        "summary": {
            "contract_routes": len(contract_routes),
            "server_routes": len(server_routes),
            "server_scopes": len(server_scopes),
            "contract_cli_flags": len(contract_flags),
            "rust_cli_paths": len(rust_paths),
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "errors": errors,
        "warnings": warnings,
    }


def validate_contract_shape(contract: dict[str, Any], routes: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if contract.get("route_count") != len(routes):
        errors.append("contract.route_count does not match len(contract.routes)")
    if contract.get("architecture", {}).get("rag") is not False:
        errors.append("contract.architecture.rag must be false")
    if contract.get("architecture", {}).get("knowledge_mode") != "compiled_wiki":
        errors.append("contract.architecture.knowledge_mode must be compiled_wiki")
    if ROUTES is routes:
        errors.append("api_contract() must return a defensive copy, not ROUTES itself")

    seen: set[tuple[str, str]] = set()
    for index, route in enumerate(routes, start=1):
        method = route.get("method")
        path = route.get("path")
        scope = route.get("scope")
        summary = str(route.get("summary", "")).strip()
        if method not in VALID_METHODS:
            errors.append(f"route #{index} has invalid method: {method!r}")
        if not isinstance(path, str) or not path.startswith("/"):
            errors.append(f"route #{index} has invalid path: {path!r}")
        if scope not in VALID_SCOPES:
            errors.append(f"route #{index} has invalid scope: {scope!r}")
        if not route.get("category"):
            errors.append(f"route #{index} {method} {path} is missing category")
        if not summary:
            errors.append(f"route #{index} {method} {path} is missing summary")
        key = (str(method), str(path))
        if key in seen:
            errors.append(f"duplicate route contract entry: {method} {path}")
        seen.add(key)
    return errors


def extract_server_routes(server_path: Path | None = None) -> set[tuple[str, str]]:
    return set(extract_server_scopes(server_path).keys())


def extract_server_scopes(server_path: Path | None = None) -> dict[tuple[str, str], str]:
    if server_path is None:
        server_path = Path(__file__).resolve().with_name("server.py")
    tree = ast.parse(server_path.read_text(encoding="utf-8"))
    scopes: dict[tuple[str, str], str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "do_GET":
            for statement in node.body:
                if isinstance(statement, ast.If):
                    paths = extract_paths_from_test(statement.test)
                    if not paths:
                        continue
                    scope = extract_ensure_authorized_scope(statement.body) or "public"
                    for path in paths:
                        scopes[("GET", path)] = scope
        if isinstance(node, ast.FunctionDef) and node.name == "do_POST":
            read_paths = extract_post_read_scope_paths(node)
            for statement in node.body:
                if isinstance(statement, ast.If):
                    for path in extract_paths_from_test(statement.test):
                        scopes[("POST", path)] = "read" if path in read_paths else "admin"
    return scopes


def extract_ensure_authorized_scope(statements: list[ast.stmt]) -> str | None:
    for statement in statements:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "ensure_authorized" and node.args:
                    return constant_string(node.args[0])
    return None


def extract_post_read_scope_paths(function: ast.FunctionDef) -> set[str]:
    for statement in function.body:
        if not isinstance(statement, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "required_scope" for target in statement.targets):
            continue
        if not isinstance(statement.value, ast.IfExp):
            continue
        if constant_string(statement.value.body) != "read":
            continue
        if constant_string(statement.value.orelse) != "admin":
            continue
        return extract_paths_from_test(statement.value.test)
    return set()


def extract_paths_from_test(node: ast.AST) -> set[str]:
    paths: set[str] = set()
    if isinstance(node, ast.BoolOp):
        for value in node.values:
            paths.update(extract_paths_from_test(value))
        return paths
    if isinstance(node, ast.Compare) and is_parsed_path(node.left):
        for comparator in node.comparators:
            paths.update(strings_from_ast(comparator))
        return paths
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "startswith" and is_parsed_path(node.func.value) and node.args:
            prefix = constant_string(node.args[0])
            if prefix:
                paths.add(path_for_prefix(prefix))
    return paths


def is_parsed_path(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "path"


def constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def strings_from_ast(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        return {value for element in node.elts if (value := constant_string(element))}
    return set()


def path_for_prefix(prefix: str) -> str:
    for contract_path, server_prefix in PATH_PARAM_PREFIXES.items():
        if prefix == server_prefix:
            return contract_path
    return prefix.rstrip("/") + "/{path}"


def extract_contract_cli_flags(routes: list[dict[str, Any]]) -> set[str]:
    flags: set[str] = set()
    for route in routes:
        cli = route.get("cli")
        if isinstance(cli, str):
            flags.update(re.findall(r"--[a-zA-Z0-9-]+", cli))
    return flags


def extract_rust_cli_paths(source: str) -> set[str]:
    paths = {
        match.group(1)
        for match in re.finditer(r'(?:get|post)\(\s*(?:&format!\(\s*)?"([^"]+)"', source)
        if match.group(1).startswith("/")
    }
    return {path.split("?", 1)[0] for path in paths if not path.startswith("/assets/")}


def main() -> int:
    result = verify_api_contract()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
