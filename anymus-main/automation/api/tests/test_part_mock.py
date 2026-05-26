"""
ANYMUS — Mock API Tests (Differentiator D2)
MOCK-P-001 to MOCK-P-010

Runs against recorded fixture responses in automation/api/mocks/
when MOCK_MODE=true. No live InvenTree instance required.

This enables:
  - Offline development and testing
  - Fast CI feedback without infrastructure dependencies
  - Isolation of test logic from server availability

Run: MOCK_MODE=true pytest tests/test_part_mock.py -v
"""
import json
import os
from pathlib import Path

import pytest
import responses as responses_lib
import requests

# Path to mock fixtures
MOCKS_DIR = Path(__file__).parent.parent / "mocks"

MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"
BASE_URL = os.getenv("INVENTREE_URL", "http://localhost:8000")


def load_fixture(filename: str) -> dict:
    with open(MOCKS_DIR / filename) as f:
        return json.load(f)


pytestmark = pytest.mark.skipif(
    not MOCK_MODE,
    reason="Mock tests require MOCK_MODE=true. Run: MOCK_MODE=true pytest tests/test_part_mock.py",
)


@pytest.mark.mock
class TestPartListMock:

    @responses_lib.activate
    def test_get_part_list_returns_count_and_results(self):
        """MOCK-P-001: GET /api/part/ returns expected pagination envelope."""
        fixture = load_fixture("part_list.json")
        responses_lib.add(
            responses_lib.GET,
            f"{BASE_URL}/api/part/",
            json=fixture,
            status=200,
        )
        r = requests.get(f"{BASE_URL}/api/part/", headers={"Authorization": "Token mock"})
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 3
        assert len(body["results"]) == 3

    @responses_lib.activate
    def test_part_list_fields_are_present(self):
        """MOCK-P-002: Each part in the list has all required fields."""
        fixture = load_fixture("part_list.json")
        responses_lib.add(
            responses_lib.GET, f"{BASE_URL}/api/part/", json=fixture, status=200
        )
        r = requests.get(f"{BASE_URL}/api/part/", headers={"Authorization": "Token mock"})
        part = r.json()["results"][0]

        required_fields = [
            "pk", "name", "IPN", "description", "active", "assembly",
            "component", "purchaseable", "salable", "trackable", "virtual",
            "is_template", "in_stock", "total_in_stock", "category",
        ]
        for field in required_fields:
            assert field in part, f"Field '{field}' missing from part list response"

    @responses_lib.activate
    def test_assembly_part_has_correct_flags(self):
        """MOCK-P-003: Assembly part (pk=3) has assembly=True, salable=True."""
        fixture = load_fixture("part_list.json")
        responses_lib.add(
            responses_lib.GET, f"{BASE_URL}/api/part/", json=fixture, status=200
        )
        r = requests.get(f"{BASE_URL}/api/part/", headers={"Authorization": "Token mock"})
        assembly_part = next(p for p in r.json()["results"] if p["assembly"] is True)
        assert assembly_part["salable"] is True
        assert assembly_part["trackable"] is True


@pytest.mark.mock
class TestPartDetailMock:

    @responses_lib.activate
    def test_get_part_detail_has_notes_field(self):
        """MOCK-P-004: Detail endpoint includes 'notes' field (absent in list)."""
        fixture = load_fixture("part_detail.json")
        responses_lib.add(
            responses_lib.GET, f"{BASE_URL}/api/part/1/", json=fixture, status=200
        )
        r = requests.get(f"{BASE_URL}/api/part/1/", headers={"Authorization": "Token mock"})
        assert r.status_code == 200
        assert "notes" in r.json(), "'notes' field must be present in detail response"

    @responses_lib.activate
    def test_part_detail_pk_matches_url(self):
        """MOCK-P-005: Returned pk matches the requested resource ID."""
        fixture = load_fixture("part_detail.json")
        responses_lib.add(
            responses_lib.GET, f"{BASE_URL}/api/part/1/", json=fixture, status=200
        )
        r = requests.get(f"{BASE_URL}/api/part/1/", headers={"Authorization": "Token mock"})
        assert r.json()["pk"] == 1


@pytest.mark.mock
class TestPartCreateMock:

    @responses_lib.activate
    def test_create_part_success_returns_201(self):
        """MOCK-P-006: Successful POST returns 201 with full part object."""
        fixture = load_fixture("part_create_201.json")
        responses_lib.add(
            responses_lib.POST, f"{BASE_URL}/api/part/", json=fixture, status=201
        )
        r = requests.post(
            f"{BASE_URL}/api/part/",
            json={"name": "ANYMUS New Part"},
            headers={"Authorization": "Token mock"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["pk"] == 999
        assert body["name"] == "ANYMUS New Part"
        assert body["active"] is True

    @responses_lib.activate
    def test_create_part_missing_name_returns_400(self):
        """MOCK-P-007: POST without name returns 400 with field error."""
        fixture = load_fixture("part_create_400.json")
        responses_lib.add(
            responses_lib.POST, f"{BASE_URL}/api/part/", json=fixture, status=400
        )
        r = requests.post(
            f"{BASE_URL}/api/part/",
            json={},
            headers={"Authorization": "Token mock"},
        )
        assert r.status_code == 400
        assert "name" in r.json()


@pytest.mark.mock
class TestCategoryListMock:

    @responses_lib.activate
    def test_category_list_has_hierarchy_fields(self):
        """MOCK-P-008: Category list includes level, parent, pathstring fields."""
        fixture = load_fixture("category_list.json")
        responses_lib.add(
            responses_lib.GET, f"{BASE_URL}/api/part/category/", json=fixture, status=200
        )
        r = requests.get(
            f"{BASE_URL}/api/part/category/", headers={"Authorization": "Token mock"}
        )
        assert r.status_code == 200
        cat = r.json()["results"][0]
        for field in ["pk", "name", "level", "parent", "pathstring", "subcategories", "part_count"]:
            assert field in cat, f"Category missing field: {field}"

    @responses_lib.activate
    def test_category_hierarchy_depth_reflected_in_level(self):
        """MOCK-P-009: Nested categories have increasing level values."""
        fixture = load_fixture("category_list.json")
        responses_lib.add(
            responses_lib.GET, f"{BASE_URL}/api/part/category/", json=fixture, status=200
        )
        r = requests.get(
            f"{BASE_URL}/api/part/category/", headers={"Authorization": "Token mock"}
        )
        results = r.json()["results"]
        # Electronics (level 0) → Passives (level 1) → Resistors (level 2)
        levels = [c["level"] for c in results]
        assert levels == sorted(levels), "Categories should be ordered by hierarchy level"

    @responses_lib.activate
    def test_pathstring_contains_parent_names(self):
        """MOCK-P-010: Pathstring for nested category includes all ancestor names."""
        fixture = load_fixture("category_list.json")
        responses_lib.add(
            responses_lib.GET, f"{BASE_URL}/api/part/category/", json=fixture, status=200
        )
        r = requests.get(
            f"{BASE_URL}/api/part/category/", headers={"Authorization": "Token mock"}
        )
        # Resistors pathstring should be "Electronics/Passives/Resistors"
        resistors = next(c for c in r.json()["results"] if c["name"] == "Resistors")
        assert "Electronics" in resistors["pathstring"]
        assert "Passives" in resistors["pathstring"]
        assert "Resistors" in resistors["pathstring"]
