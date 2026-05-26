"""
ANYMUS — Part Filtering, Pagination & Search Tests
API-P-021 to API-P-040

Tests: query params on GET /api/part/ and /api/part/category/

NOTE (InvenTree v1.3 behaviour):
  Without a 'limit' parameter, /api/part/ returns a plain JSON array.
  With 'limit', it returns the paginated {"count":…,"results":[…]} envelope.
  All tests that need .json()["results"] must pass limit explicitly.
"""
import uuid
import pytest


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.mark.filtering
class TestPartSearch:

    def test_search_by_name(self, api_client, created_part):
        """API-P-021: ?search= matches parts by name."""
        r = api_client.get(
            f"{api_client.base_url}/api/part/",
            params={"search": created_part["name"], "limit": 200},
        )
        assert r.status_code == 200
        pks = [p["pk"] for p in r.json()["results"]]
        assert created_part["pk"] in pks

    def test_search_no_results(self, api_client):
        """API-P-022: ?search= with gibberish returns empty results, not an error."""
        r = api_client.get(
            f"{api_client.base_url}/api/part/",
            params={"search": "ANYMUS_XYZZY_NO_MATCH_12345", "limit": 10},
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0
        assert r.json()["results"] == []

    def test_search_by_ipn(self, api_client, delete_part):
        """API-P-023: ?search= matches against IPN field."""
        uid = _uid()
        ipn = f"ANYMUS-SRCH-IPN-{uid}"
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS IPN Search Part {uid}", "IPN": ipn},
        )
        assert r.status_code == 201
        pk = r.json()["pk"]

        search_r = api_client.get(
            f"{api_client.base_url}/api/part/",
            params={"search": ipn, "limit": 200},
        )
        assert search_r.status_code == 200
        pks = [p["pk"] for p in search_r.json()["results"]]
        assert pk in pks

        delete_part(pk)


@pytest.mark.filtering
class TestPartFilterByField:

    def test_filter_active_true(self, api_client):
        """API-P-024: ?active=true returns only active parts."""
        r = api_client.get(f"{api_client.base_url}/api/part/", params={"active": "true", "limit": 200})
        assert r.status_code == 200
        for part in r.json()["results"]:
            assert part["active"] is True, f"Part {part['pk']} is inactive but was returned in active filter"

    def test_filter_active_false(self, api_client):
        """API-P-025: ?active=false returns only inactive parts."""
        r = api_client.get(f"{api_client.base_url}/api/part/", params={"active": "false", "limit": 200})
        assert r.status_code == 200
        for part in r.json()["results"]:
            assert part["active"] is False

    def test_filter_by_category(self, api_client, created_part, created_category):
        """API-P-026: ?category= returns only parts in that category."""
        api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"category": created_category["pk"]},
        )
        r = api_client.get(
            f"{api_client.base_url}/api/part/",
            params={"category": created_category["pk"], "limit": 200},
        )
        assert r.status_code == 200
        pks = [p["pk"] for p in r.json()["results"]]
        assert created_part["pk"] in pks

    def test_filter_assembly_true(self, api_client):
        """API-P-027: ?assembly=true returns only assembly parts."""
        r = api_client.get(f"{api_client.base_url}/api/part/", params={"assembly": "true", "limit": 200})
        assert r.status_code == 200
        for part in r.json()["results"]:
            assert part["assembly"] is True

    def test_filter_purchaseable_true(self, api_client):
        """API-P-028: ?purchaseable=true returns only purchaseable parts."""
        r = api_client.get(f"{api_client.base_url}/api/part/", params={"purchaseable": "true", "limit": 200})
        assert r.status_code == 200
        for part in r.json()["results"]:
            assert part["purchaseable"] is True

    def test_filter_virtual_true(self, api_client):
        """API-P-029: ?virtual=true returns only virtual parts."""
        r = api_client.get(f"{api_client.base_url}/api/part/", params={"virtual": "true", "limit": 200})
        assert r.status_code == 200
        for part in r.json()["results"]:
            assert part["virtual"] is True

    @pytest.mark.parametrize("flag", ["trackable", "salable", "component"])
    def test_filter_boolean_flags(self, api_client, flag):
        """API-P-030: Boolean filter flags return only matching parts."""
        r = api_client.get(f"{api_client.base_url}/api/part/", params={flag: "true", "limit": 200})
        assert r.status_code == 200
        for part in r.json()["results"]:
            assert part[flag] is True, f"Part {part['pk']} has {flag}=False but was returned"


@pytest.mark.filtering
class TestPartPagination:

    def test_limit_parameter(self, api_client):
        """API-P-031: ?limit=2 returns at most 2 results."""
        r = api_client.get(f"{api_client.base_url}/api/part/", params={"limit": 2})
        assert r.status_code == 200
        assert len(r.json()["results"]) <= 2

    def test_offset_parameter(self, api_client):
        """API-P-032: ?offset advances the results window."""
        r1 = api_client.get(f"{api_client.base_url}/api/part/", params={"limit": 2, "offset": 0})
        r2 = api_client.get(f"{api_client.base_url}/api/part/", params={"limit": 2, "offset": 2})
        assert r1.status_code == 200
        assert r2.status_code == 200
        pks1 = [p["pk"] for p in r1.json()["results"]]
        pks2 = [p["pk"] for p in r2.json()["results"]]
        # No overlap between pages
        assert not set(pks1) & set(pks2), "Offset pages should not share parts"

    def test_pagination_next_link(self, api_client):
        """API-P-033: When results exceed limit, 'next' URL is populated."""
        r = api_client.get(f"{api_client.base_url}/api/part/", params={"limit": 1})
        body = r.json()
        if body["count"] > 1:
            assert body["next"] is not None
        else:
            assert body["next"] is None

    def test_pagination_count_consistent(self, api_client):
        """API-P-034: 'count' field equals total parts regardless of limit."""
        r_all = api_client.get(f"{api_client.base_url}/api/part/", params={"limit": 1})
        total_count = r_all.json()["count"]

        r_big = api_client.get(f"{api_client.base_url}/api/part/", params={"limit": 500})
        actual_results = len(r_big.json()["results"])

        assert total_count >= actual_results

    @pytest.mark.parametrize("limit", [0, -1, 99999])
    def test_limit_boundary_values(self, api_client, limit):
        """API-P-035: Boundary limit values return 200 or 400 — not 500."""
        r = api_client.get(f"{api_client.base_url}/api/part/", params={"limit": limit})
        assert r.status_code in (200, 400), (
            f"Unexpected status {r.status_code} for limit={limit}"
        )


@pytest.mark.filtering
class TestPartSorting:

    def test_sort_by_name_ascending(self, api_client, created_part):
        """API-P-120: ?ordering=name returns ANYMUS parts sorted A→Z by name.

        Scoped to ANYMUS-prefixed parts so the comparison is stable regardless
        of any Unicode-named rows left by schemathesis (PostgreSQL's Unicode
        collation differs from Python's code-point sort for non-ASCII chars).
        """
        r = api_client.get(
            f"{api_client.base_url}/api/part/",
            params={"ordering": "name", "limit": 200, "search": "ANYMUS"},
        )
        assert r.status_code == 200
        names = [p["name"] for p in r.json()["results"]]
        assert len(names) >= 1, "Expected at least one ANYMUS part (created_part fixture)"
        assert names == sorted(names), "Parts not sorted ascending by name"

    def test_sort_by_name_descending(self, api_client, created_part):
        """API-P-121: ?ordering=-name returns ANYMUS parts sorted Z→A by name."""
        r = api_client.get(
            f"{api_client.base_url}/api/part/",
            params={"ordering": "-name", "limit": 200, "search": "ANYMUS"},
        )
        assert r.status_code == 200
        names = [p["name"] for p in r.json()["results"]]
        assert len(names) >= 1, "Expected at least one ANYMUS part (created_part fixture)"
        assert names == sorted(names, reverse=True), "Parts not sorted descending"

    def test_empty_page_beyond_data(self, api_client):
        """API-P-132: Offset beyond total count returns empty results, not error."""
        r = api_client.get(f"{api_client.base_url}/api/part/", params={"offset": 999999, "limit": 10})
        assert r.status_code == 200
        assert r.json()["results"] == []

    def test_search_by_ipn_value(self, api_client, delete_part):
        """API-P-134: ?search= matches the IPN field specifically."""
        uid = _uid()
        ipn = f"ANYMUS-IPN-SRCH-{uid}"
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS IPN Search Part {uid}", "IPN": ipn},
        )
        assert r.status_code == 201
        pk = r.json()["pk"]

        result = api_client.get(
            f"{api_client.base_url}/api/part/",
            params={"search": ipn, "limit": 200},
        )
        assert result.status_code == 200
        assert any(p["pk"] == pk for p in result.json()["results"]), "Part not found by IPN search"

        delete_part(pk)

    def test_filter_active_false_excludes_inactive(self, api_client, inactive_part):
        """API-P-114: ?active=true must not include inactive parts."""
        r = api_client.get(f"{api_client.base_url}/api/part/", params={"active": "true", "limit": 200})
        assert r.status_code == 200
        pks = [p["pk"] for p in r.json()["results"]]
        assert inactive_part["pk"] not in pks, "Inactive part should not appear in active=true filter"
