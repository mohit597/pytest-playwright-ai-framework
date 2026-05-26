"""
ANYMUS — D3 Pre-flight Health Check Tests
HC-001 to HC-006

Runs FIRST (alphabetical sort: test_meta_ < test_part_).
If any critical endpoint is down, the entire session is skipped via the
api_health_gate fixture in conftest.py. These tests provide individual
assertions per endpoint for detailed CI reporting.
"""
import pytest
import requests
from config.settings import BASE_URL, HEALTH_ENDPOINTS, HEALTHY_STATUS_CODES


@pytest.mark.health
class TestAPIHealth:

    @pytest.mark.parametrize("path", HEALTH_ENDPOINTS)
    def test_endpoint_reachable(self, path):
        """HC-001 to HC-006: Each critical endpoint must respond (200 or 401)."""
        url = f"{BASE_URL}{path}"
        try:
            response = requests.get(url, timeout=5)
        except requests.ConnectionError:
            pytest.fail(f"[HC] {path} — CONNECTION REFUSED. Is InvenTree running at {BASE_URL}?")
        except requests.Timeout:
            pytest.fail(f"[HC] {path} — TIMED OUT after 5s.")

        assert response.status_code in HEALTHY_STATUS_CODES, (
            f"[HC] {path} returned {response.status_code}. "
            f"Expected one of {HEALTHY_STATUS_CODES}. "
            f"This indicates a server-side error, not just missing auth."
        )

    def test_part_list_endpoint_schema(self):
        """HC-007: /api/part/ response has expected pagination envelope."""
        response = requests.get(f"{BASE_URL}/api/part/", timeout=5)
        # 401 is fine — we just need the server to be structurally correct
        if response.status_code == 200:
            body = response.json()
            assert "count" in body, "/api/part/ missing 'count' field in response"
            assert "results" in body, "/api/part/ missing 'results' field in response"

    def test_category_tree_returns_array(self):
        """HC-008: /api/part/category/tree/ must return a JSON array."""
        response = requests.get(f"{BASE_URL}/api/part/category/tree/", timeout=5)
        if response.status_code == 200:
            body = response.json()
            assert isinstance(body, list), (
                f"/api/part/category/tree/ should return a list, got {type(body)}"
            )
