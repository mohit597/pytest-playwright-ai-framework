"""
UI-P-027 — Part Parameters UI tests
Test ID prefix: UI-P
"""
import os
import requests
import pytest
from playwright.sync_api import Page, expect

from pages.part_detail_page import PartDetailPage

BASE_URL = os.getenv("INVENTREE_URL", "http://localhost:8000")


def _create_part_via_api(api_headers, name):
    resp = requests.post(
        f"{BASE_URL}/api/part/",
        json={"name": name, "description": f"Parameter test: {name}"},
        headers=api_headers
    )
    assert resp.status_code == 201
    return resp.json()["pk"]


def _create_parameter_template_via_api(api_headers, name):
    """Parameter templates are at /api/parameter/template/ (not /api/part/parameter/template/).
    Idempotent: if template already exists (leftover from previous run), returns its PK.
    """
    resp = requests.post(
        f"{BASE_URL}/api/parameter/template/",
        json={"name": name, "description": f"Template: {name}"},
        headers=api_headers
    )
    if resp.status_code == 201:
        return resp.json()["pk"]
    # Template already exists — find and return its PK
    search = requests.get(f"{BASE_URL}/api/parameter/template/", params={"search": name}, headers=api_headers)
    data = search.json()
    results = data.get("results", []) if isinstance(data, dict) else data
    for t in results:
        if t["name"] == name:
            return t["pk"]
    raise AssertionError(f"Could not create or find parameter template '{name}': {resp.text}")


def _delete_parameter_template_via_api(api_headers, pk):
    requests.delete(f"{BASE_URL}/api/parameter/template/{pk}/", headers=api_headers)


@pytest.mark.ui
def test_UI_P_027_add_parameter_to_part(page: Page, cleanup_parts, api_headers):
    """UI-P-027: Add a parameter to a part via the Parameters tab."""
    template_name = "UI-P-027 Resistance"
    part_pk = _create_part_via_api(api_headers, "UI-P-027 Parameter Part")
    cleanup_parts(part_pk)
    template_pk = _create_parameter_template_via_api(api_headers, template_name)

    try:
        detail = PartDetailPage(page)
        detail.open(part_pk)
        detail.add_parameter(template_name, "10000")

        # Verify parameter is visible on the page
        expect(page.locator("body")).to_contain_text(template_name)
    finally:
        _delete_parameter_template_via_api(api_headers, template_pk)


@pytest.mark.ui
def test_UI_P_028_parameters_tab_visible(page: Page, cleanup_parts, api_headers):
    """UI-P-028: Parameters tab is always visible on part detail."""
    part_pk = _create_part_via_api(api_headers, "UI-P-028 Params Tab Part")
    cleanup_parts(part_pk)

    detail = PartDetailPage(page)
    detail.open(part_pk)

    detail.assert_tab_visible(PartDetailPage.TAB_PARAMETERS)


@pytest.mark.ui
@pytest.mark.parametrize("param_value,expected_visible", [
    ("100", True),
    ("0", True),
    ("-1", True),
])
def test_UI_P_029_parameter_boundary_values(
    page: Page, cleanup_parts, api_headers, param_value, expected_visible
):
    """UI-P-029: Parameter accepts various boundary values (boundary analysis)."""
    template_name = f"UI-P-029 Template {param_value}"
    part_pk = _create_part_via_api(api_headers, f"UI-P-029 Param Part {param_value}")
    cleanup_parts(part_pk)
    template_pk = _create_parameter_template_via_api(api_headers, template_name)
    try:
        detail = PartDetailPage(page)
        detail.open(part_pk)
        detail.add_parameter(template_name, param_value)

        if expected_visible:
            expect(page.locator("body")).to_contain_text(param_value)
    finally:
        _delete_parameter_template_via_api(api_headers, template_pk)
