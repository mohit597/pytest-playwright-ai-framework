"""
UI-P-011 to UI-P-020 — Part Attribute toggles via Playwright
Test ID prefix: UI-P
"""
import os
import requests
import pytest
from playwright.sync_api import Page, expect

from pages.part_detail_page import PartDetailPage

BASE_URL = os.getenv("INVENTREE_URL", "http://localhost:8000")


def _create_test_part(api_headers, name, **kwargs):
    payload = {"name": name, "description": f"Attribute test part: {name}", **kwargs}
    resp = requests.post(f"{BASE_URL}/api/part/", json=payload, headers=api_headers)
    assert resp.status_code == 201, f"Part creation failed: {resp.text}"
    return resp.json()["pk"]


def _update_part(api_headers, pk, payload):
    resp = requests.patch(f"{BASE_URL}/api/part/{pk}/", json=payload, headers=api_headers)
    assert resp.status_code in (200, 201), f"Part update failed: {resp.text}"
    return resp.json()


@pytest.mark.ui
def test_UI_P_012_assembly_shows_bom_tab(page: Page, cleanup_parts, api_headers):
    """UI-P-012: Setting Assembly=true reveals the BOM tab."""
    pk = _create_test_part(api_headers, "UI-P-012 Assembly Part", assembly=True)
    cleanup_parts(pk)

    detail = PartDetailPage(page)
    detail.open(pk)

    assert detail.is_bom_tab_visible(), "BOM tab should be visible for Assembly part"


@pytest.mark.ui
def test_UI_P_013_component_shows_used_in_tab(page: Page, cleanup_parts, api_headers):
    """UI-P-013: Setting Component=true reveals the Used In / Allocated tab."""
    pk = _create_test_part(api_headers, "UI-P-013 Component Part", component=True)
    cleanup_parts(pk)

    detail = PartDetailPage(page)
    detail.open(pk)

    assert detail.is_allocated_tab_visible(), "Allocated tab should be visible for Component part"


@pytest.mark.ui
def test_UI_P_015_purchaseable_shows_suppliers_tab(page: Page, cleanup_parts, api_headers):
    """UI-P-015: Setting Purchaseable=true reveals the Suppliers tab."""
    pk = _create_test_part(api_headers, "UI-P-015 Purchaseable Part", purchaseable=True)
    cleanup_parts(pk)

    detail = PartDetailPage(page)
    detail.open(pk)

    assert detail.is_suppliers_tab_visible(), "Suppliers tab should be visible for Purchaseable part"


@pytest.mark.ui
def test_UI_P_017_template_shows_variants_tab(page: Page, cleanup_parts, api_headers):
    """UI-P-017: Setting Template=true reveals the Variants tab."""
    pk = _create_test_part(api_headers, "UI-P-017 Template Part", is_template=True)
    cleanup_parts(pk)

    detail = PartDetailPage(page)
    detail.open(pk)

    assert detail.is_variants_tab_visible(), "Variants tab should be visible for Template part"


@pytest.mark.ui
def test_UI_P_024_bom_tab_hidden_for_non_assembly(page: Page, cleanup_parts, api_headers):
    """UI-P-025: BOM tab hidden when Assembly=false."""
    pk = _create_test_part(api_headers, "UI-P-024 Non-Assembly Part", assembly=False)
    cleanup_parts(pk)

    detail = PartDetailPage(page)
    detail.open(pk)

    assert not detail.is_bom_tab_visible(), "BOM tab should NOT be visible for non-Assembly part"


@pytest.mark.ui
@pytest.mark.parametrize("attribute,expected_tab_check", [
    ({"assembly": True, "component": True}, "bom"),
    ({"purchaseable": True, "salable": True}, "suppliers"),
])
def test_UI_P_020_multiple_attributes(page: Page, cleanup_parts, api_headers, attribute, expected_tab_check):
    """UI-P-020: Multiple attributes saved simultaneously, correct tabs appear."""
    pk = _create_test_part(api_headers, f"UI-P-020 Multi-Attr {expected_tab_check}", **attribute)
    cleanup_parts(pk)

    detail = PartDetailPage(page)
    detail.open(pk)

    if expected_tab_check == "bom":
        assert detail.is_bom_tab_visible()
    elif expected_tab_check == "suppliers":
        assert detail.is_suppliers_tab_visible()
