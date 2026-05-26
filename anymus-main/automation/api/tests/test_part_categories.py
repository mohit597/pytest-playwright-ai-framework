"""
ANYMUS — Part Category API Tests
API-P-061 to API-P-080

Tests: Category CRUD, parent/child hierarchy, tree endpoint, filtering.
"""
import pytest


@pytest.mark.crud
class TestCategoryCRUD:

    def test_create_category_minimal(self, api_client):
        """API-P-061: Create a category with only name."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "ANYMUS Root Category"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "ANYMUS Root Category"
        assert body["parent"] is None       # root category has no parent
        assert body["level"] == 0           # root is at level 0
        api_client.delete(f"{api_client.base_url}/api/part/category/{body['pk']}/")

    def test_create_category_with_description(self, api_client):
        """API-P-062: Category description is stored and returned."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "Described Category", "description": "Test description"},
        )
        assert r.status_code == 201
        assert r.json()["description"] == "Test description"
        api_client.delete(f"{api_client.base_url}/api/part/category/{r.json()['pk']}/")

    def test_create_child_category(self, api_client, created_category):
        """API-P-063: Child category has parent FK and level > 0."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "ANYMUS Child Category", "parent": created_category["pk"]},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["parent"] == created_category["pk"]
        assert body["level"] == created_category["level"] + 1
        assert created_category["name"] in body["pathstring"]
        api_client.delete(f"{api_client.base_url}/api/part/category/{body['pk']}/")

    def test_get_category_list(self, api_client, created_category):
        """API-P-064: GET /api/part/category/?limit=N returns paginated list."""
        r = api_client.get(f"{api_client.base_url}/api/part/category/", params={"limit": 50})
        assert r.status_code == 200
        body = r.json()
        assert "count" in body, f"Expected paginated envelope but got: {type(body)}"
        assert "results" in body
        assert isinstance(body["results"], list)

    def test_get_category_detail(self, api_client, created_category):
        """API-P-065: GET /api/part/category/{pk}/ returns correct category."""
        r = api_client.get(
            f"{api_client.base_url}/api/part/category/{created_category['pk']}/"
        )
        assert r.status_code == 200
        body = r.json()
        assert body["pk"] == created_category["pk"]
        assert body["name"] == created_category["name"]
        assert "pathstring" in body
        assert "part_count" in body
        assert "subcategories" in body

    def test_patch_category_name(self, api_client, created_category):
        """API-P-066: PATCH category name updates correctly."""
        r = api_client.patch(
            f"{api_client.base_url}/api/part/category/{created_category['pk']}/",
            json={"name": "Updated Category Name"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Category Name"

    def test_delete_empty_category(self, api_client):
        """API-P-067: DELETE category with no parts succeeds."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "Delete Me Category"},
        )
        pk = r.json()["pk"]
        del_r = api_client.delete(f"{api_client.base_url}/api/part/category/{pk}/")
        assert del_r.status_code in (200, 204)

        get_r = api_client.get(f"{api_client.base_url}/api/part/category/{pk}/")
        assert get_r.status_code == 404

    def test_category_not_found(self, api_client):
        """API-P-068: GET non-existent category returns 404."""
        r = api_client.get(f"{api_client.base_url}/api/part/category/999999/")
        assert r.status_code == 404


@pytest.mark.crud
class TestCategoryHierarchy:

    def test_pathstring_reflects_hierarchy(self, api_client):
        """API-P-069: Deep hierarchy reflected in pathstring using slash separator."""
        # Create: Root → Child → Grandchild
        root = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "ANYMUS Root"},
        ).json()
        child = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "ANYMUS Child", "parent": root["pk"]},
        ).json()
        grandchild = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "ANYMUS Grandchild", "parent": child["pk"]},
        ).json()

        assert "ANYMUS Root" in grandchild["pathstring"]
        assert "ANYMUS Child" in grandchild["pathstring"]
        assert grandchild["level"] == 2

        # cleanup deepest first
        api_client.delete(f"{api_client.base_url}/api/part/category/{grandchild['pk']}/")
        api_client.delete(f"{api_client.base_url}/api/part/category/{child['pk']}/")
        api_client.delete(f"{api_client.base_url}/api/part/category/{root['pk']}/")

    def test_subcategory_count_increments(self, api_client, created_category):
        """API-P-070: Parent's subcategories count increments when child is created."""
        before = api_client.get(
            f"{api_client.base_url}/api/part/category/{created_category['pk']}/"
        ).json()["subcategories"]

        child = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "Count Child", "parent": created_category["pk"]},
        ).json()

        after = api_client.get(
            f"{api_client.base_url}/api/part/category/{created_category['pk']}/"
        ).json()["subcategories"]

        assert after == before + 1
        api_client.delete(f"{api_client.base_url}/api/part/category/{child['pk']}/")


@pytest.mark.filtering
class TestCategoryTree:

    def test_tree_endpoint_returns_array(self, api_client):
        """API-P-071: /api/part/category/tree/ returns a flat array."""
        r = api_client.get(f"{api_client.base_url}/api/part/category/tree/")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list), f"Expected list, got {type(body)}"

    def test_tree_nodes_have_minimal_fields(self, api_client):
        """API-P-072: Tree nodes contain pk, name, parent, structural, subcategories."""
        r = api_client.get(f"{api_client.base_url}/api/part/category/tree/")
        assert r.status_code == 200
        if r.json():
            node = r.json()[0]
            for field in ["pk", "name", "parent", "structural", "subcategories"]:
                assert field in node, f"Tree node missing field: {field}"

    def test_tree_root_nodes_have_null_parent(self, api_client, created_category):
        """API-P-073: Root categories in the tree have parent=null."""
        r = api_client.get(f"{api_client.base_url}/api/part/category/tree/")
        tree = r.json()
        if not tree:
            pytest.skip("No categories in DB — cannot verify root node parent")
        root_nodes = [n for n in tree if n["parent"] is None]
        assert len(root_nodes) > 0, "Expected at least one root category"

    def test_tree_is_not_paginated(self, api_client):
        """API-P-074: Tree endpoint returns all categories at once, no pagination envelope."""
        r = api_client.get(f"{api_client.base_url}/api/part/category/tree/")
        body = r.json()
        # Should be a plain array, not a dict with 'count'/'results'
        assert not isinstance(body, dict), "Tree endpoint should not be paginated"


@pytest.mark.validation
class TestCategoryCircularReference:

    def test_direct_circular_parent_rejected(self, api_client):
        """API-P-115: Setting category parent to its own child creates a cycle — must be rejected."""
        parent = api_client.post(
            f"{api_client.base_url}/api/part/category/", json={"name": "ANYMUS Cycle Parent"}
        ).json()
        child = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "ANYMUS Cycle Child", "parent": parent["pk"]},
        ).json()

        r = api_client.patch(
            f"{api_client.base_url}/api/part/category/{parent['pk']}/",
            json={"parent": child["pk"]},
        )
        assert r.status_code in (400, 422), (
            f"Expected 400 for circular category reference, got {r.status_code}: {r.text}"
        )

        api_client.delete(f"{api_client.base_url}/api/part/category/{child['pk']}/")
        api_client.delete(f"{api_client.base_url}/api/part/category/{parent['pk']}/")

    def test_indirect_circular_parent_rejected(self, api_client):
        """API-P-116: Setting A→C where C→B→A creates indirect cycle — must be rejected."""
        a = api_client.post(
            f"{api_client.base_url}/api/part/category/", json={"name": "ANYMUS Chain A"}
        ).json()
        b = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "ANYMUS Chain B", "parent": a["pk"]},
        ).json()
        c = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "ANYMUS Chain C", "parent": b["pk"]},
        ).json()

        # Attempt to set A's parent to C — would create A→C→B→A cycle
        r = api_client.patch(
            f"{api_client.base_url}/api/part/category/{a['pk']}/",
            json={"parent": c["pk"]},
        )
        assert r.status_code in (400, 422), (
            f"Expected 400 for indirect circular category reference, got {r.status_code}"
        )

        api_client.delete(f"{api_client.base_url}/api/part/category/{c['pk']}/")
        api_client.delete(f"{api_client.base_url}/api/part/category/{b['pk']}/")
        api_client.delete(f"{api_client.base_url}/api/part/category/{a['pk']}/")

    def test_delete_category_with_children_documents_behaviour(self, api_client):
        """API-P-117: Document v1.3 behaviour when deleting a parent category with children.
        InvenTree v1.3 cascade-deletes children (204); older versions returned 400/409.
        """
        parent = api_client.post(
            f"{api_client.base_url}/api/part/category/", json={"name": "ANYMUS Del Parent"}
        ).json()
        child = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "ANYMUS Del Child", "parent": parent["pk"]},
        ).json()

        r = api_client.delete(f"{api_client.base_url}/api/part/category/{parent['pk']}/")
        # v1.3 allows cascade delete (204); accept 400/409 for older behaviour
        assert r.status_code in (204, 400, 409), (
            f"Unexpected status when deleting parent with children: {r.status_code}"
        )

        # Cleanup (idempotent — already deleted in cascade)
        api_client.delete(f"{api_client.base_url}/api/part/category/{child['pk']}/")
        if r.status_code != 204:
            api_client.delete(f"{api_client.base_url}/api/part/category/{parent['pk']}/")

    def test_invalid_parent_reference_rejected(self, api_client):
        """API-P-116b: Creating a category with a non-existent parent returns 400."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/category/",
            json={"name": "ANYMUS Orphan Category", "parent": 9999999},
        )
        assert r.status_code == 400
