"""
ANYMUS — Part Parameters API Tests
API-P-081 to API-P-085, API-P-119

Tests: parameter template CRUD, assigning/updating/deleting part parameters,
duplicate constraint enforcement.
Story: EPMCDMETST-37843, EPMCDMETST-37865
"""
import pytest


@pytest.mark.crud
class TestParameterTemplate:

    def test_create_parameter_template(self, api_client):
        """API-P-119: POST /api/parameter/template/ creates a template."""
        import uuid
        r = api_client.post(
            f"{api_client.base_url}/api/parameter/template/",
            json={"name": f"ANYMUS Resistance {uuid.uuid4().hex[:8]}", "units": "ohm"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["pk"] > 0
        assert "ANYMUS Resistance" in body["name"]
        assert body["units"] == "ohm"
        api_client.delete(f"{api_client.base_url}/api/parameter/template/{body['pk']}/")

    def test_list_parameter_templates(self, api_client, parameter_template):
        """API-P-119b: GET /api/parameter/template/ returns the template list."""
        r = api_client.get(f"{api_client.base_url}/api/parameter/template/")
        assert r.status_code == 200
        # Response may be paginated or a plain list
        data = r.json()
        results = data["results"] if isinstance(data, dict) else data
        pks = [t["pk"] for t in results]
        assert parameter_template["pk"] in pks


@pytest.mark.crud
class TestPartParameter:

    def test_assign_parameter_to_part(self, api_client, created_part, parameter_template):
        """API-P-081: POST a parameter assignment — part gets the value linked to the template."""
        r = api_client.post(
            f"{api_client.base_url}/api/parameter/",
            json={
                "model_type": "part",
                "model_id": created_part["pk"],
                "template": parameter_template["pk"],
                "data": "220",
            },
        )
        assert r.status_code == 201, f"Failed to assign parameter: {r.text}"
        body = r.json()
        assert body["pk"] > 0
        assert body["data"] == "220"
        api_client.delete(f"{api_client.base_url}/api/parameter/{body['pk']}/")

    def test_list_parameters_for_part(self, api_client, created_part, parameter_template):
        """API-P-082: GET /api/parameter/?part={pk} returns assigned parameters."""
        ra = api_client.post(
            f"{api_client.base_url}/api/parameter/",
            json={
                "model_type": "part",
                "model_id": created_part["pk"],
                "template": parameter_template["pk"],
                "data": "5V",
            },
        )
        assert ra.status_code == 201
        param_pk = ra.json()["pk"]

        r = api_client.get(
            f"{api_client.base_url}/api/parameter/",
            params={"model_type": "part", "model_id": created_part["pk"], "limit": 200},
        )
        assert r.status_code == 200
        data = r.json()
        results = data["results"] if isinstance(data, dict) else data
        assert len(results) >= 1
        assert any(p["pk"] == param_pk for p in results)

        api_client.delete(f"{api_client.base_url}/api/parameter/{param_pk}/")

    def test_update_parameter_value(self, api_client, created_part, parameter_template):
        """API-P-083: PATCH a parameter's data field updates the value."""
        ra = api_client.post(
            f"{api_client.base_url}/api/parameter/",
            json={
                "model_type": "part",
                "model_id": created_part["pk"],
                "template": parameter_template["pk"],
                "data": "100",
            },
        )
        assert ra.status_code == 201
        param_pk = ra.json()["pk"]

        r = api_client.patch(
            f"{api_client.base_url}/api/parameter/{param_pk}/",
            json={"data": "240"},
        )
        assert r.status_code == 200
        assert r.json()["data"] == "240"

        api_client.delete(f"{api_client.base_url}/api/parameter/{param_pk}/")

    def test_delete_parameter(self, api_client, created_part, parameter_template):
        """API-P-084: DELETE a parameter removes it; subsequent GET returns 404."""
        ra = api_client.post(
            f"{api_client.base_url}/api/parameter/",
            json={
                "model_type": "part",
                "model_id": created_part["pk"],
                "template": parameter_template["pk"],
                "data": "50",
            },
        )
        assert ra.status_code == 201
        param_pk = ra.json()["pk"]

        r = api_client.delete(f"{api_client.base_url}/api/parameter/{param_pk}/")
        assert r.status_code in (200, 204)

        get_r = api_client.get(f"{api_client.base_url}/api/parameter/{param_pk}/")
        assert get_r.status_code == 404

    def test_duplicate_parameter_rejected(self, api_client, created_part, parameter_template):
        """API-P-085: Assigning the same template to a part twice returns 400."""
        ra = api_client.post(
            f"{api_client.base_url}/api/parameter/",
            json={
                "model_type": "part",
                "model_id": created_part["pk"],
                "template": parameter_template["pk"],
                "data": "10",
            },
        )
        assert ra.status_code == 201
        param_pk = ra.json()["pk"]

        r = api_client.post(
            f"{api_client.base_url}/api/parameter/",
            json={
                "model_type": "part",
                "model_id": created_part["pk"],
                "template": parameter_template["pk"],
                "data": "20",
            },
        )
        assert r.status_code == 400, (
            f"Expected 400 for duplicate parameter template on same part, got {r.status_code}"
        )

        api_client.delete(f"{api_client.base_url}/api/parameter/{param_pk}/")
