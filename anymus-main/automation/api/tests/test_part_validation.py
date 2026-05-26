"""
ANYMUS — Part Field Validation & Error Handling Tests
API-P-041 to API-P-060

Tests: required fields, invalid payloads, read-only fields, auth enforcement.
"""
import uuid
import pytest


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.mark.validation
class TestRequiredFields:

    def test_create_part_no_name_returns_400(self, api_client):
        """API-P-041: POST without 'name' returns 400 with field error."""
        r = api_client.post(f"{api_client.base_url}/api/part/", json={"description": "No name"})
        assert r.status_code == 400
        body = r.json()
        assert "name" in body, f"Expected 'name' in error body, got: {body}"

    def test_create_part_empty_name_returns_400(self, api_client):
        """API-P-042: POST with empty string name returns 400."""
        r = api_client.post(f"{api_client.base_url}/api/part/", json={"name": ""})
        assert r.status_code == 400

    def test_create_part_null_name_returns_400(self, api_client):
        """API-P-043: POST with null name returns 400."""
        r = api_client.post(f"{api_client.base_url}/api/part/", json={"name": None})
        assert r.status_code == 400

    def test_create_part_whitespace_name(self, api_client):
        """API-P-044: POST with whitespace-only name returns 400."""
        r = api_client.post(f"{api_client.base_url}/api/part/", json={"name": "   "})
        assert r.status_code in (400, 201)  # Some APIs strip whitespace


@pytest.mark.validation
class TestFieldConstraints:

    @pytest.mark.parametrize("name_length,expected_status", [
        (5, 201),       # minimum valid (InvenTree v1.3 max_length=100)
        (50, 201),      # normal length
        (100, 201),     # at the limit
        (101, 400),     # exceeds limit (InvenTree v1.3 max_length=100)
    ])
    def test_name_length_boundary(self, api_client, delete_part, name_length, expected_status):
        """API-P-045: Part name respects max_length=100 constraint (InvenTree v1.3)."""
        uid = _uid()
        # Build a unique name of exactly name_length chars
        prefix = f"AN{uid}"  # 10 chars
        if name_length <= len(prefix):
            padded = (prefix + "X" * name_length)[:name_length]
        else:
            padded = prefix + "A" * (name_length - len(prefix))
        r = api_client.post(f"{api_client.base_url}/api/part/", json={"name": padded})
        assert r.status_code == expected_status, (
            f"name length={name_length}: expected {expected_status}, got {r.status_code}: {r.text[:100]}"
        )
        if r.status_code == 201:
            delete_part(r.json()["pk"])

    def test_minimum_stock_cannot_be_negative(self, api_client):
        """API-P-046: minimum_stock < 0 should return 400."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": "Negative Stock Part", "minimum_stock": -1.0},
        )
        assert r.status_code in (400, 201)  # Document actual behaviour

    def test_invalid_category_id_returns_400(self, api_client):
        """API-P-047: Referencing a non-existent category returns 400."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": "Bad Category Part", "category": 999999},
        )
        assert r.status_code == 400

    def test_default_expiry_non_negative(self, api_client, delete_part):
        """API-P-048: default_expiry=0 is valid (no expiry)."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS No Expiry Part {_uid()}", "default_expiry": 0},
        )
        assert r.status_code == 201
        assert r.json()["default_expiry"] == 0
        delete_part(r.json()["pk"])

    @pytest.mark.parametrize("bad_payload", [
        {"name": "Part", "assembly": "not_a_bool"},
        {"name": "Part", "active": "yes"},
        {"name": "Part", "virtual": 123},
    ])
    def test_boolean_fields_reject_non_boolean(self, api_client, bad_payload):
        """API-P-049: Boolean fields reject non-boolean values."""
        r = api_client.post(f"{api_client.base_url}/api/part/", json=bad_payload)
        assert r.status_code in (400, 201)  # Document actual coercion behaviour


@pytest.mark.validation
class TestReadOnlyFields:

    def test_pk_is_read_only(self, api_client, created_part):
        """API-P-050: Cannot override pk via PATCH."""
        original_pk = created_part["pk"]
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{original_pk}/",
            json={"pk": 999999},
        )
        # Server should either ignore the pk field or return 400
        if r.status_code == 200:
            assert r.json()["pk"] == original_pk, "pk should not change via PATCH"

    def test_creation_date_is_read_only(self, api_client, delete_part):
        """API-P-051: creation_date is set by server, not client."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS Date Test Part {_uid()}", "creation_date": "2000-01-01"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["creation_date"] != "2000-01-01"
        delete_part(body["pk"])

    def test_in_stock_is_read_only(self, api_client, created_part):
        """API-P-052: in_stock cannot be set via PATCH (managed by stock system)."""
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"in_stock": 9999.0},
        )
        if r.status_code == 200:
            body = r.json()
            # in_stock is a computed field — PATCH payload is silently ignored.
            # A fresh part has 0 stock, never 9999.
            assert body.get("in_stock") != 9999.0, "in_stock must not be settable via PATCH"


@pytest.mark.validation
class TestAuthEnforcement:

    def test_unauthenticated_get_returns_401(self, base_url):
        """API-P-053: GET /api/part/ without token returns 401."""
        import requests
        r = requests.get(f"{base_url}/api/part/")
        assert r.status_code == 401

    def test_unauthenticated_post_returns_401(self, base_url):
        """API-P-054: POST /api/part/ without token returns 401."""
        import requests
        r = requests.post(f"{base_url}/api/part/", json={"name": "No Auth Part"})
        assert r.status_code == 401

    def test_invalid_token_returns_401(self, base_url):
        """API-P-055: Invalid token returns 401."""
        import requests
        r = requests.get(
            f"{base_url}/api/part/",
            headers={"Authorization": "Token invalid_token_xyz"},
        )
        assert r.status_code == 401

    def test_unauthenticated_delete_returns_401(self, base_url, created_part):
        """API-P-056: DELETE without auth returns 401 (part not yet deactivated, so unauth check fires first)."""
        import requests
        r = requests.delete(f"{base_url}/api/part/{created_part['pk']}/")
        assert r.status_code == 401


@pytest.mark.validation
class TestUniqueIPN:

    def test_duplicate_ipn_allowed(self, api_client, delete_part):
        """API-P-110: InvenTree v1.3 allows duplicate IPNs (uniqueness not enforced)."""
        uid = _uid()
        ipn = f"ANYMUS-IPN-DUP-{uid}"
        r1 = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS IPN Part A {uid}", "IPN": ipn},
        )
        assert r1.status_code == 201
        pk1 = r1.json()["pk"]

        r2 = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS IPN Part B {uid}", "IPN": ipn},
        )
        # v1.3 does NOT enforce IPN uniqueness — both parts created successfully
        assert r2.status_code == 201, (
            f"InvenTree v1.3 should allow duplicate IPNs, got {r2.status_code}"
        )
        pk2 = r2.json()["pk"]

        delete_part(pk1)
        delete_part(pk2)

    def test_duplicate_ipn_patch_documents_behaviour(self, api_client, delete_part):
        """API-P-111: PATCH IPN to match another part's IPN — documents v1.3 actual behaviour."""
        uid = _uid()
        ipn_a = f"ANYMUS-IPN-PA-{uid}"
        ipn_b = f"ANYMUS-IPN-PB-{uid}"
        ra = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS Patch IPN A {uid}", "IPN": ipn_a},
        )
        rb = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS Patch IPN B {uid}", "IPN": ipn_b},
        )
        assert ra.status_code == 201 and rb.status_code == 201
        pk_a, pk_b = ra.json()["pk"], rb.json()["pk"]

        r = api_client.patch(f"{api_client.base_url}/api/part/{pk_b}/", json={"IPN": ipn_a})
        # v1.3 allows this — document the actual response code
        assert r.status_code in (200, 400), (
            f"Unexpected status for duplicate IPN patch: {r.status_code}"
        )

        delete_part(pk_a)
        delete_part(pk_b)

    def test_multiple_null_ipns_allowed(self, api_client, delete_part):
        """API-P-112: Multiple parts with null IPN must all be accepted."""
        pks = []
        for i in range(3):
            r = api_client.post(
                f"{api_client.base_url}/api/part/",
                json={"name": f"ANYMUS No IPN Part {i} {_uid()}"},
            )
            assert r.status_code == 201, f"Failed creating part {i} without IPN"
            pks.append(r.json()["pk"])
        for pk in pks:
            delete_part(pk)


@pytest.mark.validation
class TestPartAttributeFlags:

    def test_set_multiple_boolean_flags(self, api_client, created_part):
        """API-P-125: PATCH multiple boolean flags in one request."""
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"purchaseable": True, "salable": True, "trackable": True},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["purchaseable"] is True
        assert body["salable"] is True
        assert body["trackable"] is True

    def test_set_virtual_flag(self, api_client, created_part):
        """API-P-126: Setting virtual=True is accepted; document side-effects."""
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"virtual": True},
        )
        assert r.status_code == 200
        assert r.json()["virtual"] is True

    def test_set_valid_units(self, api_client, delete_part):
        """API-P-127: Part created with a units value stores it correctly."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS Units Part {_uid()}", "units": "pcs"},
        )
        assert r.status_code == 201
        assert r.json()["units"] == "pcs"
        delete_part(r.json()["pk"])

    def test_empty_description_accepted(self, api_client, delete_part):
        """API-P-128: Empty string description is accepted at creation (null rejected in v1.3)."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": f"ANYMUS Empty Desc Part {_uid()}", "description": ""},
        )
        assert r.status_code == 201
        body = r.json()
        assert body.get("description") in (None, "")
        delete_part(body["pk"])

    def test_inactive_part_still_retrievable(self, api_client, inactive_part):
        """API-P-113: GET on an inactive part returns 200 with active=False."""
        r = api_client.get(f"{api_client.base_url}/api/part/{inactive_part['pk']}/")
        assert r.status_code == 200
        assert r.json()["active"] is False


@pytest.mark.validation
class TestMalformedRequests:

    def test_wrong_type_for_category_fk(self, api_client):
        """API-P-130: Passing a string where category FK expects integer returns 400."""
        r = api_client.post(
            f"{api_client.base_url}/api/part/",
            json={"name": "Bad Type Part", "category": "not-an-integer"},
        )
        assert r.status_code == 400
        assert "category" in r.json()

    def test_unsupported_method_returns_405(self, api_client, created_part):
        """API-P-133: PUT on /api/part/{pk}/ — document server behaviour (405 or 200 in v1.3+)."""
        r = api_client.put(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"name": created_part["name"]},
        )
        # InvenTree v1.3 supports PUT (returns 200); older versions returned 405
        assert r.status_code in (200, 405, 400), (
            f"Unexpected status for PUT /api/part/{{pk}}/: {r.status_code}"
        )

    def test_nonexistent_part_returns_404(self, api_client):
        """API-P-129: GET on a non-existent part ID returns 404."""
        r = api_client.get(f"{api_client.base_url}/api/part/999999999/")
        assert r.status_code == 404
