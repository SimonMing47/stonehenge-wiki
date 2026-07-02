from __future__ import annotations

import unittest

from stonehenge_wiki.api_contract import api_contract
from stonehenge_wiki.contract_checks import extract_server_routes, validate_contract_shape, verify_api_contract


class ApiContractTest(unittest.TestCase):
    def test_api_contract_matches_server_and_cli(self) -> None:
        result = verify_api_contract()

        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["summary"]["errors"], 0)
        self.assertEqual(result["summary"]["warnings"], 0)
        self.assertGreaterEqual(result["summary"]["contract_routes"], 30)

    def test_contract_shape_rejects_duplicate_routes(self) -> None:
        contract = api_contract()
        duplicated_routes = contract["routes"] + [contract["routes"][0]]
        errors = validate_contract_shape(contract | {"route_count": len(duplicated_routes)}, duplicated_routes)

        self.assertTrue(any("duplicate route contract entry" in error for error in errors))

    def test_server_route_extraction_tracks_parameterized_routes(self) -> None:
        routes = extract_server_routes()

        self.assertIn(("GET", "/api/contract"), routes)
        self.assertIn(("GET", "/assets/{path}"), routes)
        self.assertIn(("GET", "/files/{path}"), routes)
        self.assertIn(("POST", "/llm/test"), routes)


if __name__ == "__main__":
    unittest.main()
