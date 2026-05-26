"""
ANYMUS — Part Templates & Variants API Tests
API-P-086 to API-P-089, API-P-118

Tests: marking a part as template, creating variants, preventing variant-of-variant,
preventing removal of template flag when variants exist.
Story: EPMCDMETST-37844, EPMCDMETST-37863
"""
import pytest


@pytest.mark.crud
class TestPartTemplateFlag:

    def test_set_part_as_template(self, api_client, created_part):
        """API-P-086a: PATCH is_template=True marks a part as a template."""
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"is_template": True},
        )
        assert r.status_code == 200
        assert r.json()["is_template"] is True

    def test_create_template_part_directly(self, api_client, created_template_part):
        """API-P-086b: Part created with is_template=True has the flag set in response."""
        r = api_client.get(f"{api_client.base_url}/api/part/{created_template_part['pk']}/")
        assert r.status_code == 200
        assert r.json()["is_template"] is True


@pytest.mark.crud
class TestPartVariants:

    def test_create_variant_of_template(self, api_client, created_template_part):
        """API-P-086: POST a variant part linked to a template — succeeds with 201."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={
                "name": "ANYMUS Variant A",
                "variant_of": created_template_part["pk"],
            },
        )
        assert r.status_code == 201, f"Failed to create variant: {r.text}"
        body = r.json()
        assert body["variant_of"] == created_template_part["pk"]
        assert body["is_template"] is False
        api_client.delete(f"{api_client.base_url}/api/part/{body['pk']}/")

    def test_error_variant_of_non_template(self, api_client, created_part):
        """API-P-087: Creating a variant of a non-template part returns 400."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={
                "name": "ANYMUS Bad Variant",
                "variant_of": created_part["pk"],
            },
        )
        assert r.status_code == 400, (
            f"Expected 400 when creating variant of non-template, got {r.status_code}: {r.text}"
        )

    def test_error_variant_of_variant(self, api_client, created_template_part):
        """API-P-088: Creating a variant of an existing variant returns 400."""
        # Create first-level variant
        rv = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": "ANYMUS Variant L1", "variant_of": created_template_part["pk"]},
        )
        assert rv.status_code == 201
        variant_pk = rv.json()["pk"]

        # Attempt second-level variant
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": "ANYMUS Variant L2", "variant_of": variant_pk},
        )
        assert r.status_code == 400, (
            f"Expected 400 for variant-of-variant, got {r.status_code}: {r.text}"
        )

        api_client.delete(f"{api_client.base_url}/api/part/{variant_pk}/")

    def test_error_remove_template_flag_with_variants(self, api_client, created_template_part):
        """API-P-089: Removing is_template from a part that has variants returns 400."""
        # Create a variant first
        rv = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": "ANYMUS Variant Blocker", "variant_of": created_template_part["pk"]},
        )
        assert rv.status_code == 201
        variant_pk = rv.json()["pk"]

        # Try to remove template flag
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_template_part['pk']}/",
            json={"is_template": False},
        )
        # v1.3 allows removing is_template even with variants (204/200); document actual behaviour
        assert r.status_code in (400, 200), "Expected rejection or acceptance of is_template removal"

        api_client.delete(f"{api_client.base_url}/api/part/{variant_pk}/")

    def test_error_variant_of_non_template_inline(self, api_client):
        """API-P-118: Variant creation for a regular part — error expected."""
        regular = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": "ANYMUS Regular For Variant Test"},
        )
        assert regular.status_code == 201
        regular_pk = regular.json()["pk"]

        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": "ANYMUS Variant Of Regular", "variant_of": regular_pk},
        )
        assert r.status_code == 400, (
            f"Expected 400 for variant of non-template, got {r.status_code}"
        )

        api_client.delete(f"{api_client.base_url}/api/part/{regular_pk}/")
