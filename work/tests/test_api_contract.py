from __future__ import annotations

import unittest

from stonehenge_wiki.api_contract import api_contract
from stonehenge_wiki.contract_checks import (
    extract_server_request_fields,
    extract_server_routes,
    extract_server_scopes,
    validate_contract_shape,
    verify_api_contract,
)


class ApiContractTest(unittest.TestCase):
    def test_api_contract_matches_server_and_cli(self) -> None:
        result = verify_api_contract()

        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["summary"]["errors"], 0)
        self.assertEqual(result["summary"]["warnings"], 0)
        self.assertGreaterEqual(result["summary"]["contract_routes"], 30)
        self.assertGreaterEqual(result["summary"]["contract_field_metadata"], 40)

    def test_api_contract_fields_are_machine_readable(self) -> None:
        contract = api_contract()
        routes = {(route["method"], route["path"]): route for route in contract["routes"]}

        self.assertEqual(contract["schema_version"], 2)
        self.assertEqual(routes[("GET", "/sources/detail")]["query"]["path"]["required"], True)
        self.assertEqual(routes[("GET", "/sources/detail")]["query"]["preview_chars"]["type"], "int")
        self.assertEqual(routes[("GET", "/wiki/search")]["query"]["query"]["alias_for"], "q")
        self.assertEqual(routes[("GET", "/reports/readiness")]["query"]["groups"]["type"], "string[]")
        self.assertEqual(routes[("POST", "/sources/status")]["body"]["rel_path"]["alias_for"], "path")
        self.assertEqual(routes[("POST", "/sources/status")]["body"]["status"]["enum"], ["active", "quarantined"])
        self.assertEqual(routes[("POST", "/llm/test")]["body"]["agent"]["alias_for"], "agent_name")

    def test_contract_shape_rejects_duplicate_routes(self) -> None:
        contract = api_contract()
        duplicated_routes = contract["routes"] + [contract["routes"][0]]
        errors = validate_contract_shape(contract | {"route_count": len(duplicated_routes)}, duplicated_routes)

        self.assertTrue(any("duplicate route contract entry" in error for error in errors))

    def test_contract_shape_rejects_unstructured_field_metadata(self) -> None:
        contract = api_contract()
        route = dict(contract["routes"][0])
        route["query"] = {"bad": "optional string"}
        routes = [route]
        errors = validate_contract_shape(contract | {"route_count": len(routes)}, routes)

        self.assertTrue(any("query.bad must use structured metadata" in error for error in errors))

    def test_contract_shape_rejects_broken_alias_metadata(self) -> None:
        contract = api_contract()
        route = dict(contract["routes"][0])
        route["query"] = {
            "alias": {
                "required": False,
                "type": "string",
                "alias_for": "missing",
            }
        }
        routes = [route]
        errors = validate_contract_shape(contract | {"route_count": len(routes)}, routes)

        self.assertTrue(any("alias_for points to missing field" in error for error in errors))

    def test_server_route_extraction_tracks_parameterized_routes(self) -> None:
        routes = extract_server_routes()

        self.assertIn(("GET", "/api/contract"), routes)
        self.assertIn(("GET", "/assets/{path}"), routes)
        self.assertIn(("GET", "/files/{path}"), routes)
        self.assertIn(("POST", "/llm/test"), routes)

    def test_server_scope_extraction_tracks_public_read_and_admin(self) -> None:
        scopes = extract_server_scopes()

        self.assertEqual(scopes[("GET", "/health")], "public")
        self.assertEqual(scopes[("GET", "/api/contract")], "read")
        self.assertEqual(scopes[("GET", "/llm/config")], "admin")
        self.assertEqual(scopes[("POST", "/ask")], "public")
        self.assertEqual(scopes[("POST", "/explain")], "public")
        self.assertEqual(scopes[("POST", "/llm/test")], "admin")

    def test_server_request_field_extraction_tracks_aliases(self) -> None:
        fields = extract_server_request_fields()

        self.assertEqual(fields[("GET", "/wiki/sections")]["query"], {"source_path", "path", "limit"})
        self.assertEqual(fields[("GET", "/wiki/search")]["query"], {"q", "query", "limit"})
        self.assertEqual(fields[("GET", "/reports/readiness")]["query"], {"groups", "group"})
        self.assertEqual(fields[("POST", "/sources/status")]["body"], {"path", "rel_path", "status", "reason", "actor"})
        self.assertEqual(fields[("POST", "/llm/test")]["body"], {"agent_name", "agent", "live"})


if __name__ == "__main__":
    unittest.main()
