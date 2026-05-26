"""
ANYMUS — Part Attachments API Tests
API-P-104 to API-P-106

Tests: uploading a file attachment, listing attachments, deleting an attachment.

NOTE (InvenTree v1.3 behaviour change):
  Attachment endpoint moved from /api/part/attachment/ to /api/attachment/.
  Upload now uses model_type + model_id (generic attachment system).

Story: EPMCDMETST-37847, EPMCDMETST-37875
"""
import io
import pytest


def _make_text_file(content: str = "ANYMUS test attachment") -> io.BytesIO:
    """Returns an in-memory text file suitable for multipart upload."""
    buf = io.BytesIO(content.encode())
    buf.name = "anymus_test.txt"
    return buf


@pytest.mark.crud
class TestPartAttachments:

    def test_upload_attachment_to_part(self, api_client, created_part):
        """API-P-104: POST a file to /api/attachment/ — 201 with pk returned."""
        file_buf = _make_text_file("ANYMUS attachment upload test")
        r = api_client.post(
            f"{api_client.base_url}/api/attachment/",
            data={"model_type": "part", "model_id": created_part["pk"], "comment": "ANYMUS test file"},
            files={"attachment": ("anymus_test.txt", file_buf, "text/plain")},
        )
        assert r.status_code == 201, f"Attachment upload failed: {r.text}"
        body = r.json()
        assert body["pk"] > 0
        api_client.delete(f"{api_client.base_url}/api/attachment/{body['pk']}/")

    def test_list_attachments_for_part(self, api_client, created_part):
        """API-P-105: GET /api/attachment/?model_type=part&model_id=pk returns the uploaded file."""
        file_buf = _make_text_file("ANYMUS list test")
        rc = api_client.post(
            f"{api_client.base_url}/api/attachment/",
            data={"model_type": "part", "model_id": created_part["pk"]},
            files={"attachment": ("anymus_list.txt", file_buf, "text/plain")},
        )
        assert rc.status_code == 201
        att_pk = rc.json()["pk"]

        r = api_client.get(
            f"{api_client.base_url}/api/attachment/",
            params={"model_type": "part", "model_id": created_part["pk"], "limit": 50},
        )
        assert r.status_code == 200
        data = r.json()
        results = data["results"] if isinstance(data, dict) else data
        assert any(a["pk"] == att_pk for a in results), "Uploaded attachment not found in list"

        api_client.delete(f"{api_client.base_url}/api/attachment/{att_pk}/")

    def test_delete_attachment(self, api_client, created_part):
        """API-P-106: DELETE an attachment — subsequent GET returns 404."""
        file_buf = _make_text_file("ANYMUS delete test")
        rc = api_client.post(
            f"{api_client.base_url}/api/attachment/",
            data={"model_type": "part", "model_id": created_part["pk"]},
            files={"attachment": ("anymus_del.txt", file_buf, "text/plain")},
        )
        assert rc.status_code == 201
        att_pk = rc.json()["pk"]

        r = api_client.delete(f"{api_client.base_url}/api/attachment/{att_pk}/")
        assert r.status_code in (200, 204)

        get_r = api_client.get(f"{api_client.base_url}/api/attachment/{att_pk}/")
        assert get_r.status_code == 404
