from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from .platform import LLMWikiPlatform


def serve(wiki_root: Path, host: str | None = None, port: int | None = None) -> None:
    platform = LLMWikiPlatform.from_wiki_root(wiki_root)
    server_host = host or platform.config.api_host
    server_port = port or platform.config.api_port
    httpd = build_server(platform, server_host, server_port)
    print(f"LLM Wiki API listening on http://{server_host}:{server_port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("LLM Wiki API stopped")
    finally:
        httpd.server_close()


def build_server(platform: LLMWikiPlatform, host: str, port: int) -> ThreadingHTTPServer:
    class Handler(PlatformHandler):
        llm_wiki_platform = platform

    return ThreadingHTTPServer((host, port), Handler)


class PlatformHandler(BaseHTTPRequestHandler):
    llm_wiki_platform: LLMWikiPlatform

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/console"}:
            return self.write_static("index.html")
        if parsed.path == "/favicon.ico":
            return self.write_no_content()
        if parsed.path.startswith("/assets/"):
            return self.write_static(parsed.path.removeprefix("/assets/"))
        if parsed.path == "/health":
            return self.write_json(self.llm_wiki_platform.health())
        if parsed.path.startswith("/files/"):
            if not self.ensure_authorized("read"):
                return
            return self.write_wiki_file(parsed.path.removeprefix("/files/"))
        if parsed.path == "/index":
            if not self.ensure_authorized("read"):
                return
            return self.write_json(self.llm_wiki_platform.dump_index())
        if parsed.path == "/sources":
            if not self.ensure_authorized("read"):
                return
            include_missing = parse_qs(parsed.query).get("include_missing", ["0"])[0] in {"1", "true", "yes"}
            return self.write_json({"sources": self.llm_wiki_platform.list_sources(include_missing=include_missing)})
        if parsed.path == "/sources/history":
            if not self.ensure_authorized("read"):
                return
            query = parse_qs(parsed.query)
            rel_path = query.get("path", [""])[0] or None
            limit = int(query.get("limit", ["50"])[0])
            return self.write_json({"versions": self.llm_wiki_platform.list_source_versions(rel_path=rel_path, limit=limit)})
        if parsed.path == "/sources/risk":
            if not self.ensure_authorized("read"):
                return
            return self.write_json(self.llm_wiki_platform.source_risk_report())
        if parsed.path == "/sources/reviews":
            if not self.ensure_authorized("read"):
                return
            query = parse_qs(parsed.query)
            rel_path = query.get("path", [""])[0] or None
            limit = int(query.get("limit", ["50"])[0])
            return self.write_json({"reviews": self.llm_wiki_platform.list_source_reviews(rel_path=rel_path, limit=limit)})
        if parsed.path == "/audit":
            if not self.ensure_authorized("read"):
                return
            limit = int(parse_qs(parsed.query).get("limit", ["50"])[0])
            return self.write_json({"events": self.llm_wiki_platform.audit_events(limit)})
        if parsed.path == "/wiki/lint":
            if not self.ensure_authorized("read"):
                return
            return self.write_json(self.llm_wiki_platform.lint_wiki())
        if parsed.path == "/wiki/sections":
            if not self.ensure_authorized("read"):
                return
            query = parse_qs(parsed.query)
            source_path = query.get("source_path", query.get("path", [""]))[0] or None
            limit = int(query.get("limit", ["50"])[0])
            return self.write_json(
                {
                    "sections": self.llm_wiki_platform.list_wiki_sections(
                        source_path=source_path,
                        limit=limit,
                    )
                }
            )
        if parsed.path == "/wiki/search":
            if not self.ensure_authorized("read"):
                return
            query = parse_qs(parsed.query)
            title = query.get("q", query.get("query", [""]))[0]
            limit = int(query.get("limit", ["10"])[0])
            return self.write_json(self.llm_wiki_platform.search_wiki(title, limit=limit))
        if parsed.path == "/reports/governance":
            if not self.ensure_authorized("read"):
                return
            return self.write_json(self.llm_wiki_platform.governance_report())
        if parsed.path == "/reports/readiness":
            if not self.ensure_authorized("read"):
                return
            query = parse_qs(parsed.query)
            groups = query.get("groups") or query.get("group")
            return self.write_json(self.llm_wiki_platform.readiness_report(groups=groups))
        return self.write_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        required_scope = "read" if parsed.path in {"/ask", "/explain"} else "admin"
        if not self.ensure_authorized(required_scope):
            return
        body = self.read_json()
        if parsed.path == "/ask":
            title = str(body.get("title", ""))
            q_id = str(body.get("id", "api-1"))
            level = str(body.get("level", ""))
            return self.write_json(self.llm_wiki_platform.ask(title, q_id=q_id, level=level))
        if parsed.path == "/explain":
            title = str(body.get("title", ""))
            q_id = str(body.get("id", "explain-1"))
            level = str(body.get("level", ""))
            return self.write_json(self.llm_wiki_platform.explain_question(title, q_id=q_id, level=level))
        if parsed.path == "/reindex":
            return self.write_json(self.llm_wiki_platform.rebuild_index())
        if parsed.path == "/sources/import":
            source = str(body.get("source", ""))
            title = str(body.get("title", ""))
            category = str(body.get("category", "00_inbox"))
            return self.write_json(self.llm_wiki_platform.ingest_source(source, title=title, category=category))
        if parsed.path == "/sources/status":
            rel_path = str(body.get("path", body.get("rel_path", "")))
            status = str(body.get("status", ""))
            reason = str(body.get("reason", ""))
            actor = str(body.get("actor", "api"))
            return self.write_json(self.llm_wiki_platform.set_source_status(rel_path, status, reason=reason, actor=actor))
        if parsed.path == "/wiki/compile":
            return self.write_json(self.llm_wiki_platform.compile_wiki())
        if parsed.path == "/groups/run":
            groups = body.get("groups")
            if isinstance(groups, str):
                groups = [groups]
            results = self.llm_wiki_platform.run_groups(groups=groups)
            return self.write_json({"results": without_answers(results)})
        if parsed.path == "/slides/generate":
            topic = str(body.get("topic", ""))
            slide_count = int(body.get("slide_count", 6) or 6)
            return self.write_json(self.llm_wiki_platform.generate_presentation(topic, slide_count=slide_count))
        if parsed.path == "/reports/governance/export":
            return self.write_json(self.llm_wiki_platform.export_governance_report())
        if parsed.path == "/reports/evaluation":
            groups = body.get("groups")
            if isinstance(groups, str):
                groups = [groups]
            return self.write_json(self.llm_wiki_platform.evaluation_report(groups=groups))
        if parsed.path == "/reports/evaluation/export":
            groups = body.get("groups")
            if isinstance(groups, str):
                groups = [groups]
            return self.write_json(self.llm_wiki_platform.export_evaluation_report(groups=groups))
        if parsed.path == "/reports/readiness":
            groups = body.get("groups")
            if isinstance(groups, str):
                groups = [groups]
            return self.write_json(self.llm_wiki_platform.readiness_report(groups=groups))
        if parsed.path == "/reports/readiness/export":
            groups = body.get("groups")
            if isinstance(groups, str):
                groups = [groups]
            return self.write_json(self.llm_wiki_platform.export_readiness_report(groups=groups))
        return self.write_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def ensure_authorized(self, required_scope: str) -> bool:
        status = self.auth_error_status(required_scope)
        if status is None:
            return True
        error = "forbidden" if status == HTTPStatus.FORBIDDEN else "unauthorized"
        self.write_json({"error": error, "required_scope": required_scope}, status)
        return False

    def auth_error_status(self, required_scope: str) -> HTTPStatus | None:
        config = self.llm_wiki_platform.config
        admin_token = config.api_token
        read_token = config.api_read_token
        if not admin_token and not read_token:
            return None

        provided = self.headers.get("X-LLM-WIKI-TOKEN", "")
        if admin_token and provided == admin_token:
            return None
        if required_scope == "read" and read_token and provided == read_token:
            return None
        if provided and read_token and provided == read_token:
            return HTTPStatus.FORBIDDEN
        return HTTPStatus.UNAUTHORIZED

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if not length:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def write_json(self, data: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def write_no_content(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def write_static(self, rel_name: str) -> None:
        static_root = Path(__file__).resolve().parent / "web"
        target = (static_root / rel_name).resolve()
        if not target.is_file() or static_root.resolve() not in target.parents:
            return self.write_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        payload = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def write_wiki_file(self, rel_name: str) -> None:
        safe_rel = unquote(rel_name).strip("/")
        if not safe_rel.startswith("output/"):
            return self.write_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
        root = self.llm_wiki_platform.wiki_root.resolve()
        output_root = (root / "output").resolve()
        target = (root / safe_rel).resolve()
        if output_root not in target.parents:
            return self.write_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
        if not target.is_file():
            return self.write_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        payload = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        encoded_name = quote(target.name)
        self.send_header("Content-Disposition", f"attachment; filename=\"download.pptx\"; filename*=UTF-8''{encoded_name}")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def without_answers(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in result.items() if key != "answers"} for result in results]
