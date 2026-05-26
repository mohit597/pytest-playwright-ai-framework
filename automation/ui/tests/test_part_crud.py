"""
UI-P-001 to UI-P-010 — Part CRUD via Playwright Page Objects
Test ID prefix: UI-P
"""
import requests
import pytest
from playwright.sync_api import Page, expect

from pages.part_create_page import PartCreatePage
from pages.part_detail_page import PartDetailPage

BASE_URL_DEFAULT = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_part_via_api(api_headers, base_url, name, description, **kwargs):
    payload = {"name": name, "description": description, **kwargs}
    resp = requests.post(f"{base_url}/api/part/", json=payload, headers=api_headers)
    assert resp.status_code == 201, f"Setup failed: {resp.text}"
    return resp.json()["pk"]


def _get_part_pk_by_name(api_headers, base_url, name):
    """Find part PK by searching via API after UI creation.
    Note: search= returns a flat list; limit= returns paginated dict.
    """
    resp = requests.get(f"{base_url}/api/part/", params={"search": name, "limit": 50}, headers=api_headers)
    data = resp.json()
    results = data.get("results", []) if isinstance(data, dict) else data
    for part in results:
        if part["name"] == name:
            return part["pk"]
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.ui
def test_UI_P_001_create_part_required_fields_only(page: Page, cleanup_parts, api_headers):
    """UI-P-001: Create part with required fields only."""
    import os
    base_url = os.getenv("INVENTREE_URL", BASE_URL_DEFAULT)
    part_name = "UI-P-001 Resistor"

    create_page = PartCreatePage(page)
    create_page.create_part(
        name=part_name,
        description="10K Ohm Resistor for test UI-P-001"
    )

    # Modal closes, stays on parts list — verify part visible in list
    expect(page.get_by_text(part_name).first).to_be_visible()

    # Get PK via API for cleanup
    pk = _get_part_pk_by_name(api_headers, base_url, part_name)
    assert pk is not None, f"Part '{part_name}' not found via API after UI creation"
    cleanup_parts(pk)

    # Navigate to detail page and verify
    detail_page = PartDetailPage(page)
    detail_page.open(pk)
    expect(page.locator("body")).to_contain_text(part_name)


@pytest.mark.ui
def test_UI_P_002_create_part_with_ipn(page: Page, cleanup_parts, api_headers):
    """UI-P-002: Create part with optional IPN field."""
    import os
    base_url = os.getenv("INVENTREE_URL", BASE_URL_DEFAULT)
    part_name = "UI-P-002 Capacitor"

    create_page = PartCreatePage(page)
    create_page.create_part(
        name=part_name,
        description="100uF Capacitor",
        ipn="UI-CAP-002"
    )

    expect(page.get_by_text(part_name).first).to_be_visible()

    pk = _get_part_pk_by_name(api_headers, base_url, part_name)
    assert pk is not None
    cleanup_parts(pk)

    # Verify IPN on detail page
    detail_page = PartDetailPage(page)
    detail_page.open(pk)
    expect(page.locator("body")).to_contain_text("UI-CAP-002")


@pytest.mark.ui
def test_UI_P_004_create_part_without_name_shows_error(page: Page):
    """UI-P-004: Name is required — form must show validation error."""
    create_page = PartCreatePage(page)
    create_page.open()
    create_page.fill_description("Missing name test")
    create_page.submit()

    create_page.assert_name_error()


@pytest.mark.ui
def test_UI_P_005_create_part_with_duplicate_ipn_shows_error(page: Page, cleanup_parts, api_headers):
    """UI-P-005: Duplicate IPN must be rejected."""
    import os
    base_url = os.getenv("INVENTREE_URL", BASE_URL_DEFAULT)

    pk = _create_part_via_api(
        api_headers, base_url,
        name="UI-P-005 Base Part",
        description="Base part for duplicate IPN test",
        IPN="DUP-IPN-005"
    )
    cleanup_parts(pk)

    create_page = PartCreatePage(page)
    create_page.open()
    create_page.fill_name("UI-P-005 Duplicate IPN Part")
    create_page.fill_description("Should fail")
    create_page.fill_ipn("DUP-IPN-005")
    create_page.submit()

    create_page.assert_ipn_error()


@pytest.mark.ui
@pytest.mark.parametrize("name_length,should_succeed", [
    (100, True),
    (101, False),
])
def test_UI_P_006_007_name_boundary(page: Page, cleanup_parts, api_headers, name_length, should_succeed):
    """UI-P-006/007: Part name boundary — 100 chars succeeds, 101 fails."""
    import os
    base_url = os.getenv("INVENTREE_URL", BASE_URL_DEFAULT)

    name = "A" * name_length
    create_page = PartCreatePage(page)
    create_page.open()
    create_page.fill_name(name)
    create_page.fill_description("Boundary test")
    create_page.submit()

    if should_succeed:
        expect(page.get_by_text(name).first).to_be_visible()
        pk = _get_part_pk_by_name(api_headers, base_url, name)
        if pk:
            cleanup_parts(pk)
    else:
        create_page.assert_validation_error()


@pytest.mark.ui
def test_UI_P_008_create_part_with_category(page: Page, cleanup_parts, cleanup_categories, api_headers):
    """UI-P-008: Create part assigned to a category."""
    import os
    base_url = os.getenv("INVENTREE_URL", BASE_URL_DEFAULT)

    # Create category via API first
    resp = requests.post(
        f"{base_url}/api/part/category/",
        json={"name": "UI-P-008 Test Category", "description": "Test"},
        headers=api_headers
    )
    assert resp.status_code == 201
    cat_pk = resp.json()["pk"]
    cleanup_categories(cat_pk)

    part_name = "UI-P-008 Categorised Part"
    create_page = PartCreatePage(page)
    create_page.open()
    create_page.fill_name(part_name)
    create_page.fill_description("Part with category")
    create_page.select_category("UI-P-008 Test Category")
    create_page.submit()

    expect(page.get_by_text(part_name).first).to_be_visible()

    pk = _get_part_pk_by_name(api_headers, base_url, part_name)
    assert pk is not None
    cleanup_parts(pk)


@pytest.mark.ui
def test_UI_P_009_edit_part_name_via_ui(page: Page, cleanup_parts, api_headers):
    """UI-P-009: Edit a part's name via the UI action menu."""
    import os
    base_url = os.getenv("INVENTREE_URL", BASE_URL_DEFAULT)

    pk = _create_part_via_api(api_headers, base_url, "UI-P-009 Original Name", "Part to be renamed")
    cleanup_parts(pk)

    detail = PartDetailPage(page)
    detail.open(pk)
    detail.click_edit_part()

    modal = page.locator("[role='dialog']")
    name_field = modal.locator("[aria-label='text-field-name']")
    name_field.clear()
    name_field.fill("UI-P-009 Renamed Part")
    detail.submit_modal()

    expect(page.locator("body")).to_contain_text("UI-P-009 Renamed Part")


@pytest.mark.ui
def test_UI_P_010_delete_part_via_ui(page: Page, cleanup_parts, api_headers):
    """UI-P-010: Delete a part via the UI — requires deactivation first (soft-delete).
    The Delete menu item is disabled for active parts; deactivate via API then delete via UI.
    cleanup_parts registered as safety net in case the UI delete fails mid-test.
    """
    import os
    base_url = os.getenv("INVENTREE_URL", BASE_URL_DEFAULT)

    pk = _create_part_via_api(api_headers, base_url, "UI-P-010 Delete Me", "Part to be deleted via UI")
    cleanup_parts(pk)  # safety net — no-op if deletion succeeds via UI

    # Deactivate part first — Delete menu item is disabled for active parts
    patch_resp = requests.patch(f"{base_url}/api/part/{pk}/", json={"active": False}, headers=api_headers)
    assert patch_resp.status_code == 200, f"Deactivation failed: {patch_resp.text}"

    detail = PartDetailPage(page)
    detail.open(pk)
    detail.open_part_actions()
    page.wait_for_selector(detail.DELETE_PART_ITEM, timeout=5000)
    page.locator(detail.DELETE_PART_ITEM).click()
    # Wait for Delete confirm button to become visible (React renders it with slight delay)
    delete_confirm = page.locator(detail.DELETE_CONFIRM_BUTTON)
    delete_confirm.wait_for(state="visible", timeout=10000)
    delete_confirm.click()
    # Wait for modal to disappear (confirms deletion was processed)
    page.wait_for_selector(detail.MODAL, state="detached", timeout=10000)
    page.wait_for_load_state("networkidle")

    resp = requests.get(f"{base_url}/api/part/{pk}/", headers=api_headers)
    assert resp.status_code == 404, f"Part {pk} should be deleted but returned {resp.status_code}"


@pytest.mark.ui
def test_UI_P_003_duplicate_part_via_ui(page: Page, cleanup_parts, api_headers):
    """UI-P-003: Duplicate a part via the UI action menu."""
    import os
    base_url = os.getenv("INVENTREE_URL", BASE_URL_DEFAULT)

    original_name = "UI-P-003 Original Part"
    pk = _create_part_via_api(api_headers, base_url, original_name, "Part to be duplicated")
    cleanup_parts(pk)

    detail = PartDetailPage(page)
    detail.open(pk)
    detail.click_duplicate_part()

    modal = page.locator("[role='dialog']")
    name_field = modal.locator("[aria-label='text-field-name']")
    name_field.clear()
    name_field.fill("UI-P-003 Duplicate Part")
    detail.submit_modal()

    dup_pk = _get_part_pk_by_name(api_headers, base_url, "UI-P-003 Duplicate Part")
    assert dup_pk is not None, "Duplicate part not found via API"
    cleanup_parts(dup_pk)
