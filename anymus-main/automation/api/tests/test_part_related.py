"""
ANYMUS — Related Parts API Tests
API-P-107 to API-P-109

Tests: creating a related-part link, error on self-reference, error on duplicate link.
Story: EPMCDMETST-37848, EPMCDMETST-37876
"""
import pytest


@pytest.mark.crud
class TestRelatedParts:

    def test_create_related_part_link(self, api_client, two_parts):
        """API-P-107: POST /api/part/related/ creates a bi-directional relationship."""
        part_a, part_b = two_parts
        r = api_client.post(
            f"{api_client.base_url}/api/part/related/",
            json={"part_1": part_a["pk"], "part_2": part_b["pk"]},
        )
        assert r.status_code == 201, f"Failed to create related link: {r.text}"
        body = r.json()
        assert body["pk"] > 0
        assert set([body["part_1"], body["part_2"]]) == {part_a["pk"], part_b["pk"]}
        api_client.delete(f"{api_client.base_url}/api/part/related/{body['pk']}/")

    def test_list_related_parts(self, api_client, two_parts):
        """API-P-107b: GET /api/part/related/?part={pk} returns the linked parts."""
        part_a, part_b = two_parts
        rc = api_client.post(
            f"{api_client.base_url}/api/part/related/",
            json={"part_1": part_a["pk"], "part_2": part_b["pk"]},
        )
        assert rc.status_code == 201
        link_pk = rc.json()["pk"]

        r = api_client.get(
            f"{api_client.base_url}/api/part/related/",
            params={"part": part_a["pk"]},
        )
        assert r.status_code == 200
        data = r.json()
        results = data["results"] if isinstance(data, dict) else data
        assert any(rel["pk"] == link_pk for rel in results)

        api_client.delete(f"{api_client.base_url}/api/part/related/{link_pk}/")

    def test_delete_related_part_link(self, api_client, two_parts):
        """API-P-109b: DELETE a relationship — it no longer appears in list."""
        part_a, part_b = two_parts
        rc = api_client.post(
            f"{api_client.base_url}/api/part/related/",
            json={"part_1": part_a["pk"], "part_2": part_b["pk"]},
        )
        assert rc.status_code == 201
        link_pk = rc.json()["pk"]

        r = api_client.delete(f"{api_client.base_url}/api/part/related/{link_pk}/")
        assert r.status_code in (200, 204)

        get_r = api_client.get(f"{api_client.base_url}/api/part/related/{link_pk}/")
        assert get_r.status_code == 404


@pytest.mark.validation
class TestRelatedPartsConstraints:

    def test_error_self_reference(self, api_client, created_part):
        """API-P-108: Relating a part to itself returns 400."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/related/",
            json={"part_1": created_part["pk"], "part_2": created_part["pk"]},
        )
        assert r.status_code == 400, (
            f"Expected 400 for self-related link, got {r.status_code}: {r.text}"
        )

    def test_error_duplicate_related_link(self, api_client, two_parts):
        """API-P-109: Creating the same relationship twice returns 400."""
        part_a, part_b = two_parts
        rc = api_client.post(
            f"{api_client.base_url}/api/part/related/",
            json={"part_1": part_a["pk"], "part_2": part_b["pk"]},
        )
        assert rc.status_code == 201
        link_pk = rc.json()["pk"]

        r = api_client.post(
            f"{api_client.base_url}/api/part/related/",
            json={"part_1": part_a["pk"], "part_2": part_b["pk"]},
        )
        assert r.status_code == 400, (
            f"Expected 400 for duplicate related link, got {r.status_code}: {r.text}"
        )

        api_client.delete(f"{api_client.base_url}/api/part/related/{link_pk}/")
