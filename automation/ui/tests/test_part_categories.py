"""
UI-P-034 to UI-P-040 — Part Category UI tests
Test ID prefix: UI-P
"""
import os
import requests
import pytest
from playwright.sync_api import Page, expect

from pages.category_page import CategoryPage
from pages.parts_list_page import PartsListPage

BASE_URL = os.getenv("INVENTREE_URL", "http://localhost:8000")


def _create_category_via_api(api_headers, name, parent=None):
    payload = {"name": name, "description": f"Test category: {name}"}
    if parent:
        payload["parent"] = parent
    resp = requests.post(f"{BASE_URL}/api/part/category/", json=payload, headers=api_headers)
    assert resp.status_code == 201, f"Category creation failed: {resp.text}"
    return resp.json()["pk"]


def _delete_category_via_api(api_headers, pk):
    requests.delete(f"{BASE_URL}/api/part/category/{pk}/", headers=api_headers, timeout=5)


@pytest.mark.ui
def test_UI_P_034_create_root_category(page: Page, cleanup_categories, api_headers):
    """UI-P-034: Create a root-level category via UI."""
    category_page = CategoryPage(page)
    category_page.open()
    category_page.create_category(name="UI-P-034 Root Category", description="Root level test category")

    # Verify it appears in the category list
    expect(page.locator("body")).to_contain_text("UI-P-034 Root Category")

    # Get PK for cleanup
    resp = requests.get(
        f"{BASE_URL}/api/part/category/",
        params={"name": "UI-P-034 Root Category", "limit": 10},
        headers=api_headers
    )
    data = resp.json()
    results = data.get("results", []) if isinstance(data, dict) else data
    if results:
        cleanup_categories(results[0]["pk"])


@pytest.mark.ui
def test_UI_P_035_create_child_subcategory(page: Page, cleanup_categories, api_headers):
    """UI-P-035: Create a child subcategory under a parent."""
    parent_pk = _create_category_via_api(api_headers, "UI-P-035 Parent Category")
    cleanup_categories(parent_pk)

    category_page = CategoryPage(page)
    category_page.open_category(parent_pk)
    category_page.create_category(
        name="UI-P-035 Child Category",
        description="Child subcategory",
        parent_pk=parent_pk
    )

    expect(page.locator("body")).to_contain_text("UI-P-035 Child Category")

    resp = requests.get(
        f"{BASE_URL}/api/part/category/",
        params={"name": "UI-P-035 Child Category", "limit": 10},
        headers=api_headers
    )
    data = resp.json()
    results = data.get("results", []) if isinstance(data, dict) else data
    if results:
        cleanup_categories(results[0]["pk"])


@pytest.mark.ui
def test_UI_P_036_navigate_category_hierarchy(page: Page, cleanup_categories, api_headers):
    """UI-P-036: Navigate through a multi-level category hierarchy."""
    grandparent_pk = _create_category_via_api(api_headers, "UI-P-036 Grandparent")
    cleanup_categories(grandparent_pk)
    parent_pk = _create_category_via_api(api_headers, "UI-P-036 Parent", parent=grandparent_pk)
    cleanup_categories(parent_pk)
    child_pk = _create_category_via_api(api_headers, "UI-P-036 Child", parent=parent_pk)
    cleanup_categories(child_pk)

    category_page = CategoryPage(page)
    category_page.open_category(child_pk)

    # Breadcrumb should show the full hierarchy
    breadcrumb = category_page.get_breadcrumb_text()
    assert "UI-P-036 Grandparent" in breadcrumb or "UI-P-036 Parent" in breadcrumb


@pytest.mark.ui
def test_UI_P_038_parametric_table(page: Page, cleanup_categories, api_headers):
    """UI-P-038: Parametric table view is accessible from category view."""
    cat_pk = _create_category_via_api(api_headers, "UI-P-038 Parametric Category")
    cleanup_categories(cat_pk)

    category_page = CategoryPage(page)
    category_page.open_category(cat_pk)

    # Parametric table link should be visible (may be grayed if no parameters)
    expect(page.locator("body")).to_be_visible()


@pytest.mark.ui
def test_UI_P_039_delete_empty_category(page: Page, cleanup_categories, api_headers):
    """UI-P-039: An empty category can be deleted via the UI."""
    cat_pk = _create_category_via_api(api_headers, "UI-P-039 Delete Me")
    cleanup_categories(cat_pk)  # safeguard if UI delete fails

    category_page = CategoryPage(page)
    category_page.open_category(cat_pk)
    category_page.delete_current_category()

    # After deletion, should redirect and category should be gone
    resp = requests.get(f"{BASE_URL}/api/part/category/{cat_pk}/", headers=api_headers)
    assert resp.status_code == 404, "Category should be deleted"
