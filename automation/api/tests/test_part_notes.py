"""
ANYMUS — Part Notes & Metadata Tests
API-P-123 to API-P-124

Tests: adding notes to a part, updating notes, clearing notes.
The 'notes' field is on the Part model itself, updated via PATCH /api/part/{pk}/.
Story: EPMCDMETST-37882
"""
import pytest


@pytest.mark.crud
class TestPartNotes:

    def test_add_note_to_part(self, api_client, created_part):
        """API-P-123: PATCH notes field stores the content and returns it."""
        note_text = "ANYMUS test note — shift left QA hackathon 2026"
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"notes": note_text},
        )
        assert r.status_code == 200
        assert r.json()["notes"] == note_text

    def test_note_persists_on_get(self, api_client, created_part):
        """API-P-123b: Notes written via PATCH are persisted and visible on GET."""
        note_text = "ANYMUS persistent note"
        api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"notes": note_text},
        )
        r = api_client.get(f"{api_client.base_url}/api/part/{created_part['pk']}/")
        assert r.status_code == 200
        assert r.json()["notes"] == note_text

    def test_update_existing_note(self, api_client, created_part):
        """API-P-123c: Updating notes replaces the previous content."""
        api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"notes": "Initial note"},
        )
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"notes": "Updated note"},
        )
        assert r.status_code == 200
        assert r.json()["notes"] == "Updated note"

    def test_clear_notes_field(self, api_client, created_part):
        """API-P-124: Setting notes to empty string clears the field."""
        api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"notes": "Note to be cleared"},
        )
        r = api_client.patch(
            f"{api_client.base_url}/api/part/{created_part['pk']}/",
            json={"notes": ""},
        )
        assert r.status_code == 200
        assert r.json()["notes"] in ("", None)

    def test_notes_field_in_detail_response(self, api_client, created_part):
        """API-P-004 (notes): Detail endpoint exposes the 'notes' field (absent in list)."""
        r = api_client.get(f"{api_client.base_url}/api/part/{created_part['pk']}/")
        assert r.status_code == 200
        assert "notes" in r.json(), "'notes' field must be present in detail response"
