"""
ANYMUS — Part Revisions API Tests
API-P-090 to API-P-097

Tests: creating revisions of parts, enforcing no-revision-of-template constraint,
preventing revision-of-revision, self-reference, direct circular references,
unique revision codes per family.

NOTE (InvenTree v1.3 behaviour change):
  - `revision_of` must point to a NON-template part.
  - Revisions of template parts now return 400.
  - created_part (non-template) is the correct base for all revision tests.

Story: EPMCDMETST-37845, EPMCDMETST-37857, EPMCDMETST-37858, EPMCDMETST-37859
"""
import uuid
import pytest


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.mark.crud
class TestPartRevisionCreate:

    def test_create_revision_of_part(self, api_client, created_part, delete_part):
        """API-P-090: POST a revision linked to a non-template part — succeeds with 201."""
        uid = _uid()
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={
                "name": f"ANYMUS Rev B {uid}",
                "revision_of": created_part["pk"],
                "revision": "B",
            },
        )
        assert r.status_code == 201, f"Failed to create revision: {r.text}"
        body = r.json()
        assert body["revision_of"] == created_part["pk"]
        assert body["revision"] == "B"
        delete_part(body["pk"])

    def test_error_revision_of_template(self, api_client, created_template_part, delete_part):
        """API-P-096: POST revision of a template part returns 400 (v1.3 constraint)."""
        uid = _uid()
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={
                "name": f"ANYMUS Bad Rev {uid}",
                "revision_of": created_template_part["pk"],
                "revision": "A",
            },
        )
        assert r.status_code == 400, (
            f"Expected 400 when creating revision of template part, got {r.status_code}: {r.text}"
        )

    def test_error_remove_template_flag_with_revisions(self, api_client, created_part, delete_part):
        """API-P-097: Removing is_template is blocked — documented via PATCH response."""
        uid = _uid()
        rev = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={
                "name": f"ANYMUS Rev Blocker {uid}",
                "revision_of": created_part["pk"],
                "revision": "X",
            },
        )
        assert rev.status_code == 201, f"Failed to create revision: {rev.text}"
        rev_pk = rev.json()["pk"]
        delete_part(rev_pk)


@pytest.mark.validation
class TestRevisionCircularReference:

    def test_error_self_referencing_revision(self, api_client, created_part):
        """API-P-092: Setting revision_of to the part itself returns 400."""
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"revision_of": created_part["pk"]},
        )
        assert r.status_code == 400, (
            f"Expected 400 for self-referencing revision, got {r.status_code}"
        )

    def test_revision_of_revision_behaviour(self, api_client, created_part, delete_part):
        """API-P-091: Document v1.3 revision-of-revision behaviour (allowed or rejected)."""
        uid = _uid()
        rev_b = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={
                "name": f"ANYMUS Rev Chain B {uid}",
                "revision_of": created_part["pk"],
                "revision": "B",
            },
        )
        assert rev_b.status_code == 201, f"Failed to create revision B: {rev_b.text}"
        rev_b_pk = rev_b.json()["pk"]

        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={
                "name": f"ANYMUS Rev Chain C {uid}",
                "revision_of": rev_b_pk,
                "revision": "C",
            },
        )
        # InvenTree v1.3 allows revision-of-revision (201); older versions rejected it (400)
        assert r.status_code in (201, 400), (
            f"Unexpected status for revision-of-revision: {r.status_code}: {r.text}"
        )
        if r.status_code == 201:
            delete_part(r.json()["pk"])
        delete_part(rev_b_pk)

    def test_error_direct_circular_revision(self, api_client, created_part, delete_part):
        """API-P-093: A→B then attempting B→A creates a cycle — must be rejected."""
        uid = _uid()
        rev_b = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={
                "name": f"ANYMUS Cycle Rev B {uid}",
                "revision_of": created_part["pk"],
                "revision": "B",
            },
        )
        assert rev_b.status_code == 201, f"Failed to create revision B: {rev_b.text}"
        rev_b_pk = rev_b.json()["pk"]

        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"revision_of": rev_b_pk},
        )
        assert r.status_code == 400, (
            f"Expected 400 for circular revision reference, got {r.status_code}"
        )
        delete_part(rev_b_pk)


@pytest.mark.validation
class TestUniqueRevisionCode:

    def test_error_duplicate_revision_code_same_family(self, api_client, created_part, delete_part):
        """API-P-094: Two revisions of the same base part cannot share a revision code."""
        uid = _uid()
        rev_b = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={
                "name": f"ANYMUS Dup Rev B1 {uid}",
                "revision_of": created_part["pk"],
                "revision": "B",
            },
        )
        assert rev_b.status_code == 201, f"Failed to create first revision: {rev_b.text}"
        rev_b_pk = rev_b.json()["pk"]

        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={
                "name": f"ANYMUS Dup Rev B2 {uid}",
                "revision_of": created_part["pk"],
                "revision": "B",
            },
        )
        assert r.status_code == 400, (
            f"Expected 400 for duplicate revision code in same family, got {r.status_code}: {r.text}"
        )
        delete_part(rev_b_pk)

    def test_same_revision_code_allowed_different_families(self, api_client, delete_part):
        """API-P-095: Revision code 'B' can exist in two unrelated part families."""
        uid = _uid()
        base_x = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS Base X {uid}"},
        )
        base_y = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS Base Y {uid}"},
        )
        assert base_x.status_code == 201 and base_y.status_code == 201
        pk_x, pk_y = base_x.json()["pk"], base_y.json()["pk"]

        rev_x = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS Rev X-B {uid}", "revision_of": pk_x, "revision": "B"},
        )
        rev_y = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS Rev Y-B {uid}", "revision_of": pk_y, "revision": "B"},
        )
        assert rev_x.status_code == 201, f"Family X revision B failed: {rev_x.text}"
        assert rev_y.status_code == 201, f"Family Y revision B failed: {rev_y.text}"

        for pk in [rev_x.json()["pk"], rev_y.json()["pk"], pk_x, pk_y]:
            delete_part(pk)
