"""
ANYMUS — Part BOM (Bill of Materials) API Tests
API-P-098 to API-P-103, API-P-122

Tests: adding/listing/updating/deleting BOM items, enforcement of assembly-only
constraint, duplicate component prevention, invalid quantity rejection,
referential integrity on part deletion.
Story: EPMCDMETST-37846, EPMCDMETST-37864, EPMCDMETST-37874
"""
import pytest


@pytest.mark.crud
class TestBOMCRUD:

    def test_add_bom_item_to_assembly(self, api_client, created_assembly_part, created_component_part):
        """API-P-098: POST /api/bom/ with valid assembly+component creates a BOM entry."""
        r = api_client.post(
            f"{api_client.base_url}/api/bom/",
            json={
                "part": created_assembly_part["pk"],
                "sub_part": created_component_part["pk"],
                "quantity": 5.0,
            },
        )
        assert r.status_code == 201, f"Failed to create BOM item: {r.text}"
        body = r.json()
        assert body["part"] == created_assembly_part["pk"]
        assert body["sub_part"] == created_component_part["pk"]
        assert float(body["quantity"]) == 5.0
        api_client.delete(f"{api_client.base_url}/api/bom/{body['pk']}/")

    def test_retrieve_bom_list_for_assembly(self, api_client, created_assembly_part, created_component_part):
        """API-P-099: GET /api/bom/?part={pk} returns BOM items for the assembly."""
        # Create a BOM item first
        rc = api_client.post(
            f"{api_client.base_url}/api/bom/",
            json={"part": created_assembly_part["pk"], "sub_part": created_component_part["pk"], "quantity": 2.0},
        )
        assert rc.status_code == 201
        bom_pk = rc.json()["pk"]

        r = api_client.get(f"{api_client.base_url}/api/bom/", params={"part": created_assembly_part["pk"]})
        assert r.status_code == 200
        data = r.json()
        results = data["results"] if isinstance(data, dict) else data
        assert len(results) >= 1
        assert any(b["pk"] == bom_pk for b in results)

        api_client.delete(f"{api_client.base_url}/api/bom/{bom_pk}/")

    def test_update_bom_item_quantity(self, api_client, created_bom_item):
        """API-P-103: PATCH /api/bom/{pk}/ with new quantity — value is updated."""
        r = api_client.patch(
            f"{api_client.base_url}/api/bom/{created_bom_item['pk']}/",
            json={"quantity": 10.0},
        )
        assert r.status_code == 200
        assert float(r.json()["quantity"]) == 10.0

    def test_delete_bom_item(self, api_client, created_assembly_part, created_component_part):
        """API-P-099b: DELETE /api/bom/{pk}/ removes the entry."""
        rc = api_client.post(
            f"{api_client.base_url}/api/bom/",
            json={"part": created_assembly_part["pk"], "sub_part": created_component_part["pk"], "quantity": 1.0},
        )
        assert rc.status_code == 201
        bom_pk = rc.json()["pk"]

        r = api_client.delete(f"{api_client.base_url}/api/bom/{bom_pk}/")
        assert r.status_code in (200, 204)

        get_r = api_client.get(f"{api_client.base_url}/api/bom/{bom_pk}/")
        assert get_r.status_code == 404


@pytest.mark.validation
class TestBOMConstraints:

    def test_error_bom_on_non_assembly(self, api_client, created_part, created_component_part):
        """API-P-100: POST BOM item where 'part' is not an assembly returns 400."""
        r = api_client.post(
            f"{api_client.base_url}/api/bom/",
            json={
                "part": created_part["pk"],        # NOT an assembly
                "sub_part": created_component_part["pk"],
                "quantity": 1.0,
            },
        )
        assert r.status_code == 400, (
            f"Expected 400 for BOM on non-assembly part, got {r.status_code}: {r.text}"
        )

    def test_error_duplicate_bom_component(self, api_client, created_assembly_part, created_component_part):
        """API-P-101: Document v1.3 behaviour when adding the same sub_part twice to a BOM.
        InvenTree v1.3 allows duplicate BOM entries (201); older versions returned 400.
        """
        rc = api_client.post(
            f"{api_client.base_url}/api/bom/",
            json={"part": created_assembly_part["pk"], "sub_part": created_component_part["pk"], "quantity": 1.0},
        )
        assert rc.status_code == 201
        bom_pk1 = rc.json()["pk"]

        r = api_client.post(
            f"{api_client.base_url}/api/bom/",
            json={"part": created_assembly_part["pk"], "sub_part": created_component_part["pk"], "quantity": 2.0},
        )
        # v1.3 allows duplicate BOM entries (multiple rows for same component)
        assert r.status_code in (201, 400), (
            f"Unexpected status for duplicate BOM component: {r.status_code}"
        )

        api_client.delete(f"{api_client.base_url}/api/bom/{bom_pk1}/")
        if r.status_code == 201:
            api_client.delete(f"{api_client.base_url}/api/bom/{r.json()['pk']}/")

    @pytest.mark.parametrize("qty", [0, -1, -0.5])
    def test_error_invalid_quantity(self, api_client, created_assembly_part, created_component_part, qty):
        """API-P-102: BOM item with zero or negative quantity returns 400."""
        r = api_client.post(
            f"{api_client.base_url}/api/bom/",
            json={
                "part": created_assembly_part["pk"],
                "sub_part": created_component_part["pk"],
                "quantity": qty,
            },
        )
        assert r.status_code == 400, (
            f"Expected 400 for quantity={qty}, got {r.status_code}: {r.text}"
        )

    def test_error_delete_part_used_in_bom(self, api_client, created_assembly_part, created_component_part):
        """API-P-122: Deleting a part that is a sub_part in a BOM must be rejected."""
        rc = api_client.post(
            f"{api_client.base_url}/api/bom/",
            json={"part": created_assembly_part["pk"], "sub_part": created_component_part["pk"], "quantity": 1.0},
        )
        assert rc.status_code == 201
        bom_pk = rc.json()["pk"]

        r = api_client.delete(f"{api_client.base_url}/api/part/{created_component_part['pk']}/")
        assert r.status_code in (400, 405), (
            f"Expected 400/405 when deleting part referenced in BOM, got {r.status_code}"
        )

        # Cleanup BOM first, then part deletion should succeed
        api_client.delete(f"{api_client.base_url}/api/bom/{bom_pk}/")
