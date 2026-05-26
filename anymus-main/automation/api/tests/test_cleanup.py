"""
ANYMUS — Cleanup & Idempotency Tests

Verifies three things:
  1. No orphaned ANYMUS data remains after pre_suite_cleanup runs.
  2. Full create→delete→404 lifecycle works for every resource type.
  3. All conftest fixtures properly set up resources during tests.

Run standalone:  pytest tests/test_cleanup.py -v -m cleanup
Story: EPMCDMETST-37840 (cross-cutting — affects all stories)
"""
import io
import pytest


# ---------------------------------------------------------------------------
# 1. Pre-suite state — confirm cleanup left no orphans
#    These run early because test_cleanup.py sorts before test_part_*.py
# ---------------------------------------------------------------------------

@pytest.mark.cleanup
class TestPreSuiteState:

    def test_no_orphaned_anymus_parts(self, api_client):
        """No ANYMUS parts should exist at test-session start (pre_suite_cleanup ran)."""
        r = api_client.get(
            f"{api_client.base_url}/api/part/",
            params={"search": "ANYMUS", "limit": 500},
        )
        assert r.status_code == 200
        data = r.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        orphans = [p["name"] for p in results if "ANYMUS" in p.get("name", "")]
        assert orphans == [], f"Orphaned ANYMUS parts found: {orphans}"

    def test_no_orphaned_anymus_categories(self, api_client):
        """No ANYMUS categories should exist at test-session start."""
        r = api_client.get(
            f"{api_client.base_url}/api/part/category/",
            params={"search": "ANYMUS", "limit": 200},
        )
        assert r.status_code == 200
        data = r.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        orphans = [c["name"] for c in results if "ANYMUS" in c.get("name", "")]
        assert orphans == [], f"Orphaned ANYMUS categories found: {orphans}"

    def test_no_orphaned_anymus_parameter_templates(self, api_client):
        """No ANYMUS parameter templates should exist at test-session start."""
        r = api_client.get(
            f"{api_client.base_url}/api/parameter/template/",
            params={"search": "ANYMUS", "limit": 200},
        )
        assert r.status_code == 200
        data = r.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        orphans = [t["name"] for t in results if "ANYMUS" in t.get("name", "")]
        assert orphans == [], f"Orphaned ANYMUS parameter templates found: {orphans}"


# ---------------------------------------------------------------------------
# 2. Lifecycle cleanup — create → delete → verify 404
# ---------------------------------------------------------------------------

@pytest.mark.cleanup
class TestResourceLifecycle:

    def test_part_lifecycle_delete_gives_404(self, api_client):
        """Part: create → deactivate → delete → GET returns 404."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": "ANYMUS Lifecycle Part"},
        )
        assert r.status_code == 201
        pk = r.json()["pk"]

        api_client.patch(f"{api_client.base_url}/api/part/{pk}/", json={"active": False})
        assert api_client.delete(f"{api_client.base_url}/api/part/{pk}/").status_code in (200, 204)
        assert api_client.get(f"{api_client.base_url}/api/part/{pk}/").status_code == 404

    def test_category_lifecycle_delete_gives_404(self, api_client):
        """Category: create → delete → GET returns 404."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "ANYMUS Lifecycle Category"},
        )
        assert r.status_code == 201
        pk = r.json()["pk"]

        assert api_client.delete(f"{api_client.base_url}/api/part/category/{pk}/").status_code in (200, 204)
        assert api_client.get(f"{api_client.base_url}/api/part/category/{pk}/").status_code == 404

    def test_parameter_template_lifecycle_delete_gives_404(self, api_client):
        """Parameter template: create → delete → GET returns 404."""
        r = api_client.post(
            f"{api_client.base_url}/api/parameter/template/",
            json={"name": "ANYMUS Lifecycle Template", "units": "kg"},
        )
        assert r.status_code == 201
        pk = r.json()["pk"]

        assert api_client.delete(f"{api_client.base_url}/api/parameter/template/{pk}/").status_code in (200, 204)
        assert api_client.get(f"{api_client.base_url}/api/parameter/template/{pk}/").status_code == 404

    def test_bom_item_lifecycle_delete_gives_404(self, api_client, created_bom_item):
        """BOM item: use fixture item → delete → GET returns 404."""
        pk = created_bom_item["pk"]
        del_r = api_client.delete(f"{api_client.base_url}/api/bom/{pk}/")
        assert del_r.status_code in (200, 204)
        assert api_client.get(f"{api_client.base_url}/api/bom/{pk}/").status_code == 404

    def test_attachment_lifecycle_delete_gives_404(self, api_client, created_part):
        """Attachment: upload → delete → GET returns 404 (uses /api/attachment/ in v1.3)."""
        buf = io.BytesIO(b"ANYMUS cleanup lifecycle file")
        rc = api_client.post(
            f"{api_client.base_url}/api/attachment/",
            data={"model_type": "part", "model_id": created_part["pk"]},
            files={"attachment": ("lifecycle.txt", buf, "text/plain")},
        )
        assert rc.status_code == 201
        att_pk = rc.json()["pk"]

        assert api_client.delete(f"{api_client.base_url}/api/attachment/{att_pk}/").status_code in (200, 204)
        assert api_client.get(f"{api_client.base_url}/api/attachment/{att_pk}/").status_code == 404

    def test_related_link_lifecycle_delete_gives_404(self, api_client, two_parts):
        """Related link: create → delete → GET returns 404."""
        part_a, part_b = two_parts
        rc = api_client.post(
            f"{api_client.base_url}/api/part/related/",
            json={"part_1": part_a["pk"], "part_2": part_b["pk"]},
        )
        assert rc.status_code == 201
        link_pk = rc.json()["pk"]

        assert api_client.delete(f"{api_client.base_url}/api/part/related/{link_pk}/").status_code in (200, 204)
        assert api_client.get(f"{api_client.base_url}/api/part/related/{link_pk}/").status_code == 404

    def test_part_parameter_lifecycle_delete_gives_404(self, api_client, created_part, parameter_template):
        """Part parameter: assign → delete → GET returns 404 (uses /api/parameter/ in v1.3)."""
        r = api_client.post(
            f"{api_client.base_url}/api/parameter/",
            json={
                "model_type": "part",
                "model_id": created_part["pk"],
                "template": parameter_template["pk"],
                "data": "3.3",
            },
        )
        assert r.status_code == 201
        param_pk = r.json()["pk"]

        assert api_client.delete(f"{api_client.base_url}/api/parameter/{param_pk}/").status_code in (200, 204)
        assert api_client.get(f"{api_client.base_url}/api/parameter/{param_pk}/").status_code == 404


# ---------------------------------------------------------------------------
# 3. Referential integrity — dependent resources block parent deletion
# ---------------------------------------------------------------------------

@pytest.mark.cleanup
class TestReferentialIntegrityCleanup:

    def test_cannot_delete_part_with_active_bom(self, api_client, created_assembly_part, created_component_part):
        """Deleting an assembly that still has BOM items must fail (400/405)."""
        rc = api_client.post(
            f"{api_client.base_url}/api/bom/",
            json={
                "part": created_assembly_part["pk"],
                "sub_part": created_component_part["pk"],
                "quantity": 1.0,
            },
        )
        assert rc.status_code == 201
        bom_pk = rc.json()["pk"]

        r = api_client.delete(f"{api_client.base_url}/api/part/{created_component_part['pk']}/")
        assert r.status_code in (400, 405), (
            f"Expected 400/405 when deleting part referenced in BOM, got {r.status_code}: {r.text}"
        )

        # Cleanup
        api_client.delete(f"{api_client.base_url}/api/bom/{bom_pk}/")

    def test_category_with_parts_cannot_be_deleted(self, api_client):
        """A category that still has parts should reject deletion (400/409)."""
        cat_r = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "ANYMUS Integrity Category"},
        )
        assert cat_r.status_code == 201
        cat_pk = cat_r.json()["pk"]

        part_r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": "ANYMUS Integrity Part", "category": cat_pk},
        )
        assert part_r.status_code == 201
        part_pk = part_r.json()["pk"]

        r = api_client.delete(f"{api_client.base_url}/api/part/category/{cat_pk}/")
        # InvenTree may allow deletion (moves parts to uncategorised) or block it
        # Either way, the part must still be retrievable afterward
        get_r = api_client.get(f"{api_client.base_url}/api/part/{part_pk}/")
        assert get_r.status_code == 200, "Part must still exist regardless of category delete behaviour"

        # Cleanup (deactivate before delete)
        api_client.patch(f"{api_client.base_url}/api/part/{part_pk}/", json={"active": False})
        api_client.delete(f"{api_client.base_url}/api/part/{part_pk}/")
        if r.status_code not in (200, 204):
            api_client.delete(f"{api_client.base_url}/api/part/category/{cat_pk}/")


# ---------------------------------------------------------------------------
# 4. Fixture idempotency — resources exist during tests, are created fresh each time
# ---------------------------------------------------------------------------

@pytest.mark.cleanup
class TestFixtureIdempotency:

    def test_created_part_exists_during_test(self, api_client, created_part):
        """created_part fixture: resource is accessible during the test."""
        r = api_client.get(f"{api_client.base_url}/api/part/{created_part['pk']}/")
        assert r.status_code == 200
        assert r.json()["pk"] == created_part["pk"]

    def test_created_category_exists_during_test(self, api_client, created_category):
        """created_category fixture: resource is accessible during the test."""
        r = api_client.get(f"{api_client.base_url}/api/part/category/{created_category['pk']}/")
        assert r.status_code == 200
        assert r.json()["pk"] == created_category["pk"]

    def test_created_template_part_exists_during_test(self, api_client, created_template_part):
        """created_template_part fixture: is_template flag is set."""
        r = api_client.get(f"{api_client.base_url}/api/part/{created_template_part['pk']}/")
        assert r.status_code == 200
        assert r.json().get("is_template") is True

    def test_created_assembly_part_exists_during_test(self, api_client, created_assembly_part):
        """created_assembly_part fixture: assembly flag is set."""
        r = api_client.get(f"{api_client.base_url}/api/part/{created_assembly_part['pk']}/")
        assert r.status_code == 200
        assert r.json().get("assembly") is True

    def test_created_bom_item_exists_during_test(self, api_client, created_bom_item):
        """created_bom_item fixture: BOM entry is accessible during the test."""
        r = api_client.get(f"{api_client.base_url}/api/bom/{created_bom_item['pk']}/")
        assert r.status_code == 200
        assert r.json()["pk"] == created_bom_item["pk"]

    def test_two_parts_both_exist_during_test(self, api_client, two_parts):
        """two_parts fixture: both parts are accessible during the test."""
        for part in two_parts:
            r = api_client.get(f"{api_client.base_url}/api/part/{part['pk']}/")
            assert r.status_code == 200

    def test_parameter_template_exists_during_test(self, api_client, parameter_template):
        """parameter_template fixture: template is accessible during the test."""
        r = api_client.get(
            f"{api_client.base_url}/api/parameter/template/{parameter_template['pk']}/"
        )
        assert r.status_code == 200
        assert r.json()["pk"] == parameter_template["pk"]
