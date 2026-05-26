"""
Cross-functional flow: Create Part → Add Parameters → Create Stock → Verify in Category
Test ID: UI-P-050
"""
import io
import os
import numpy as np
import requests
import pytest
from PIL import Image
from playwright.sync_api import Page, expect

from pages.part_create_page import PartCreatePage
from pages.part_detail_page import PartDetailPage
from pages.category_page import CategoryPage

BASE_URL = os.getenv("INVENTREE_URL", "http://inventree.localhost")
UPDATE_SNAPSHOTS = os.getenv("UPDATE_SNAPSHOTS", "false").lower() == "true"
SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "snapshots")


def _assert_screenshot(page: Page, name: str, threshold: float = 0.1):
    """D1: PIL-based screenshot comparison. Reuses the same logic as test_visual_regression.py."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    baseline_path = os.path.join(SNAPSHOT_DIR, name)
    screenshot_bytes = page.screenshot(full_page=False)
    if UPDATE_SNAPSHOTS or not os.path.exists(baseline_path):
        with open(baseline_path, "wb") as f:
            f.write(screenshot_bytes)
        print(f"[VIS] Baseline saved: {name}")
        return
    actual_img   = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    baseline_img = Image.open(baseline_path).convert("RGB")
    if actual_img.size != baseline_img.size:
        raise AssertionError(
            f"[VIS] Size mismatch for {name}: baseline={baseline_img.size}, actual={actual_img.size}. "
            "Run with UPDATE_SNAPSHOTS=true to regenerate."
        )
    diff = np.abs(np.array(actual_img, dtype=float) - np.array(baseline_img, dtype=float)).mean() / 255.0
    if diff > threshold:
        raise AssertionError(
            f"[VIS] Visual regression in {name}: diff={diff:.4f} > threshold={threshold}. "
            "Run with UPDATE_SNAPSHOTS=true to update baseline."
        )


def _create_category_via_api(api_headers, name):
    resp = requests.post(
        f"{BASE_URL}/api/part/category/",
        json={"name": name, "description": "Cross-functional test category"},
        headers=api_headers
    )
    assert resp.status_code == 201
    return resp.json()["pk"]


def _create_parameter_template_via_api(api_headers, name):
    resp = requests.post(
        f"{BASE_URL}/api/parameter/template/",
        json={"name": name, "description": f"Template: {name}"},
        headers=api_headers
    )
    if resp.status_code == 201:
        return resp.json()["pk"]
    # Template already exists (leftover from previous run) — find and return its PK
    search = requests.get(f"{BASE_URL}/api/parameter/template/", params={"search": name}, headers=api_headers)
    data = search.json()
    results = data.get("results", []) if isinstance(data, dict) else data
    for t in results:
        if t["name"] == name:
            return t["pk"]
    raise AssertionError(f"Could not create or find parameter template '{name}': {resp.text}")


def _get_part_pk_by_name(api_headers, name):
    resp = requests.get(
        f"{BASE_URL}/api/part/",
        params={"search": name, "limit": 10},
        headers=api_headers
    )
    data = resp.json()
    results = data.get("results", []) if isinstance(data, dict) else data
    for part in results:
        if part["name"] == name:
            return part["pk"]
    return None


@pytest.mark.ui
@pytest.mark.cross_functional
def test_UI_P_050_cross_functional_create_part_add_params_create_stock_verify_category(
    page: Page, cleanup_parts, cleanup_categories, api_headers
):
    """
    Full cross-functional flow:
    1. Create a category via API
    2. Create a part in that category via UI
    3. Add a parameter to the part via UI
    4. Create a stock item for the part via UI
    5. Verify the part appears in the category view
    """

    # --- Step 1: Create category via API ---
    cat_name = "XF Test Category"
    cat_pk = _create_category_via_api(api_headers, cat_name)
    cleanup_categories(cat_pk)

    # --- Step 2: Create part via UI in that category ---
    part_name = "XF Test Part"
    create_page = PartCreatePage(page)
    create_page.open()
    create_page.fill_name(part_name)
    create_page.fill_description("Cross-functional test part")
    create_page.select_category(cat_name)
    create_page.submit()

    # Modal closes, stays on parts list — get PK via API
    expect(page.get_by_text(part_name).first).to_be_visible()
    part_pk = _get_part_pk_by_name(api_headers, part_name)
    assert part_pk is not None, f"Part '{part_name}' not found via API after creation"
    cleanup_parts(part_pk)

    # --- Step 3: Add a parameter to the part ---
    template_name = "XF Resistance"
    template_pk = _create_parameter_template_via_api(api_headers, template_name)
    try:
        detail = PartDetailPage(page)
        detail.open(part_pk)
        detail.add_parameter(template_name, "4700")
        expect(page.locator("body")).to_contain_text(template_name)
    finally:
        requests.delete(f"{BASE_URL}/api/parameter/template/{template_pk}/", headers=api_headers)

    # --- Step 4: Create a stock item via the Stock tab ---
    detail.open(part_pk)
    detail.click_add_stock()
    # Stock modal: fill quantity
    modal = page.locator("[role='dialog']")
    qty_input = modal.locator("[aria-label='number-field-quantity']")
    qty_input.fill("25")
    page.locator("[role='dialog'] button:has-text('Submit')").click()
    page.wait_for_load_state("networkidle")

    # Verify stock count on stock tab
    detail.open(part_pk)
    detail.click_stock_tab()
    expect(page.locator("body")).to_contain_text("25")

    # --- Step 5: Verify part visible in category view (Parts sub-tab) ---
    category_page = CategoryPage(page)
    category_page.open_category_parts_tab(cat_pk)
    expect(page.locator("body")).to_contain_text(part_name, timeout=10000)

    # --- D1: Visual baseline for cross-functional final state ---
    # Mask dynamic content before snapshot
    page.evaluate("""
        document.querySelectorAll('.creation-date, .modified-date, [data-timestamp]')
            .forEach(el => el.style.visibility = 'hidden');
    """)
    _assert_screenshot(page, "cross-functional-final-state.png", threshold=0.1)
