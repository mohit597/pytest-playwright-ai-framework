"""
ANYMUS — Part CRUD API Tests
API-P-001 to API-P-020

Tests: Create, Read, Update (PATCH), Delete on /api/part/
Every test asserts: status code + response field + business rule.
"""
import uuid
import pytest


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.mark.crud
class TestPartCreate:

    def test_create_part_minimal(self, api_client, delete_part):
        """API-P-001: Create a part with only required field (name)."""
        uid = _uid()
        payload = {"name": f"ANYMUS Minimal Part {uid}"}
        r = api_client.post(f"{api_client.base_url}/api/part/", json=payload)
        assert r.status_code == 201
        body = r.json()
        assert f"ANYMUS Minimal Part {uid}" == body["name"]
        assert body["active"] is True
        assert body["pk"] is not None
        delete_part(body["pk"])

    def test_create_part_full_fields(self, api_client, delete_part):
        """API-P-002: Create a part with all optional fields populated."""
        uid = _uid()
        payload = {
            "name": f"ANYMUS Full Field Part {uid}",
            "IPN": f"ANYMUS-FULL-{uid}",
            "description": "Complete part with all fields",
            "keywords": "test anymus full",
            "active": True,
            "assembly": False,
            "component": True,
            "purchaseable": True,
            "salable": True,
            "trackable": False,
            "virtual": False,
            "minimum_stock": 5.0,
        }
        r = api_client.post(f"{api_client.base_url}/api/part/", json=payload)
        assert r.status_code == 201
        body = r.json()
        assert body["IPN"] == f"ANYMUS-FULL-{uid}"
        assert body["description"] == "Complete part with all fields"
        assert body["salable"] is True
        assert body["minimum_stock"] == 5.0
        delete_part(body["pk"])

    def test_create_part_assembly_flag(self, api_client, delete_part):
        """API-P-003: Assembly part should be created with assembly=True."""
        payload = {"name": f"ANYMUS Assembly Part {_uid()}", "assembly": True, "component": False}
        r = api_client.post(f"{api_client.base_url}/api/part/", json=payload)
        assert r.status_code == 201
        body = r.json()
        assert body["assembly"] is True
        assert body["component"] is False
        delete_part(body["pk"])

    def test_create_part_virtual_flag(self, api_client, delete_part):
        """API-P-004: Virtual part has no physical stock."""
        payload = {"name": f"ANYMUS Virtual Service Part {_uid()}", "virtual": True}
        r = api_client.post(f"{api_client.base_url}/api/part/", json=payload)
        assert r.status_code == 201
        body = r.json()
        assert body["virtual"] is True
        delete_part(body["pk"])

    def test_create_part_inactive(self, api_client, delete_part):
        """API-P-005: Can create a part with active=False."""
        payload = {"name": f"ANYMUS Inactive Part {_uid()}", "active": False}
        r = api_client.post(f"{api_client.base_url}/api/part/", json=payload)
        assert r.status_code == 201
        pk = r.json()["pk"]
        assert r.json()["active"] is False
        delete_part(pk)

    def test_create_part_with_category(self, api_client, created_category, delete_part):
        """API-P-006: Part assigned to a category reflects category FK."""
        payload = {"name": f"ANYMUS Categorised Part {_uid()}", "category": created_category["pk"]}
        r = api_client.post(f"{api_client.base_url}/api/part/", json=payload)
        assert r.status_code == 201
        body = r.json()
        assert body["category"] == created_category["pk"]
        delete_part(body["pk"])


@pytest.mark.crud
class TestPartRead:

    def test_get_part_list(self, api_client):
        """API-P-007: GET /api/part/?limit=N returns paginated envelope with count and results."""
        r = api_client.get(f"{api_client.base_url}/api/part/", params={"limit": 10})
        assert r.status_code == 200
        body = r.json()
        assert "count" in body, f"Expected paginated envelope, got: {type(body)}"
        assert "results" in body
        assert isinstance(body["results"], list)

    def test_get_part_detail(self, api_client, created_part):
        """API-P-008: GET /api/part/{pk}/ returns the correct part with notes field."""
        r = api_client.get(f"{api_client.base_url}/api/part/{created_part['pk']}/")
        assert r.status_code == 200
        body = r.json()
        assert body["pk"] == created_part["pk"]
        assert body["name"] == created_part["name"]
        assert "notes" in body             # notes only appears on detail endpoint, not list

    def test_get_part_not_found(self, api_client):
        """API-P-009: GET /api/part/999999/ returns 404."""
        r = api_client.get(f"{api_client.base_url}/api/part/999999/")
        assert r.status_code == 404

    def test_part_detail_has_stock_fields(self, api_client, created_part):
        """API-P-010: Detail response includes all stock tracking fields as floats."""
        r = api_client.get(f"{api_client.base_url}/api/part/{created_part['pk']}/")
        body = r.json()
        float_fields = [
            "in_stock", "total_in_stock", "unallocated_stock",
            "allocated_to_build_orders", "allocated_to_sales_orders",
            "building", "ordering", "minimum_stock",
        ]
        for field in float_fields:
            assert field in body, f"Missing field: {field}"
            assert isinstance(body[field], (int, float)), f"{field} should be numeric"


@pytest.mark.crud
class TestPartUpdate:

    def test_patch_part_name(self, api_client, created_part):
        """API-P-011: PATCH name updates the part name."""
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"name": "Updated Name"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"

    def test_patch_part_description(self, api_client, created_part):
        """API-P-012: PATCH description updates correctly."""
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"description": "Updated description"},
        )
        assert r.status_code == 200
        assert r.json()["description"] == "Updated description"

    def test_patch_part_deactivate(self, api_client, created_part):
        """API-P-013: PATCH active=False deactivates the part."""
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"active": False},
        )
        assert r.status_code == 200
        assert r.json()["active"] is False

    def test_patch_part_minimum_stock(self, api_client, created_part):
        """API-P-014: PATCH minimum_stock updates the threshold."""
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"minimum_stock": 25.0},
        )
        assert r.status_code == 200
        assert r.json()["minimum_stock"] == 25.0

    def test_patch_part_toggle_purchaseable(self, api_client, created_part):
        """API-P-015: Toggle purchaseable flag via PATCH."""
        original = created_part["purchaseable"]
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"purchaseable": not original},
        )
        assert r.status_code == 200
        assert r.json()["purchaseable"] is not original

    def test_put_not_found(self, api_client):
        """API-P-016: PATCH on non-existent part returns 404."""
        r = api_client.patch(
            f"{api_client.base_url}/api/part/999999/",
            json={"name": "ghost"},
        )
        assert r.status_code == 404


@pytest.mark.crud
class TestPartDelete:

    def test_delete_part(self, api_client):
        """API-P-017: DELETE removes the part; subsequent GET returns 404."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS Delete Me {_uid()}"},
        )
        assert r.status_code == 201
        pk = r.json()["pk"]

        # InvenTree requires deactivation before deletion
        api_client.patch(f"{api_client.base_url}/api/part/{pk}/", json={"active": False})
        del_r = api_client.delete(f"{api_client.base_url}/api/part/{pk}/")
        assert del_r.status_code in (200, 204)

        get_r = api_client.get(f"{api_client.base_url}/api/part/{pk}/")
        assert get_r.status_code == 404

    def test_delete_non_existent_part(self, api_client):
        """API-P-018: DELETE on non-existent part returns 404."""
        r = api_client.delete(f"{api_client.base_url}/api/part/999999/")
        assert r.status_code == 404

    def test_deleted_part_not_in_list(self, api_client):
        """API-P-019: Deleted part does not appear in the parts list."""
        uid = _uid()
        name = f"ANYMUS Gone Part {uid}"
        r = api_client.post(f"{api_client.base_url}/api/part/", json={"name": name})
        assert r.status_code == 201
        pk = r.json()["pk"]
        api_client.patch(f"{api_client.base_url}/api/part/{pk}/", json={"active": False})
        api_client.delete(f"{api_client.base_url}/api/part/{pk}/")

        list_r = api_client.get(
            f"{api_client.base_url}/api/part/",
            params={"search": name, "limit": 50},
        )
        results = list_r.json().get("results", [])
        pks = [p["pk"] for p in results]
        assert pk not in pks

    def test_create_read_update_delete_flow(self, api_client):
        """API-P-020: Full CRUD flow — part is created, retrieved, updated and deleted."""
        uid = _uid()
        name = f"ANYMUS CRUD Flow Part {uid}"

        r = api_client.post(f"{api_client.base_url}/api/part/", json={"name": name})
        assert r.status_code == 201
        pk = r.json()["pk"]

        r = api_client.get(f"{api_client.base_url}/api/part/{pk}/")
        assert r.status_code == 200
        assert r.json()["name"] == name

        r = api_client.patch(f"{api_client.base_url}/api/part/{pk}/", json={"description": "Updated"})
        assert r.status_code == 200
        assert r.json()["description"] == "Updated"

        # Deactivate before delete
        api_client.patch(f"{api_client.base_url}/api/part/{pk}/", json={"active": False})
        r = api_client.delete(f"{api_client.base_url}/api/part/{pk}/")
        assert r.status_code in (200, 204)

        r = api_client.get(f"{api_client.base_url}/api/part/{pk}/")
        assert r.status_code == 404
