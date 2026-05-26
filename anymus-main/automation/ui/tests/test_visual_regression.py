"""
Visual Regression Tests — D1 Differentiator
Playwright screenshot comparison for critical InvenTree Part pages.

Visual regression tests capture baseline screenshots of critical Part pages.
On CI, any pixel deviation beyond threshold fails the test, catching layout/CSS regressions
that DOM-based assertions miss entirely.

Baseline management:
  - First run: baselines are created automatically in snapshots/
  - UPDATE_SNAPSHOTS=true: regenerate all baselines
  - Normal run: compare against existing baselines (fails on pixel drift)

Test ID prefix: VIS-P
"""
import io
import os

import numpy as np
import pytest
import requests
from PIL import Image
from playwright.sync_api import Page, expect

from pages.category_page import CategoryPage
from pages.part_create_page import PartCreatePage
from pages.part_detail_page import PartDetailPage

BASE_URL = os.getenv("INVENTREE_URL", "http://localhost:8000")
UPDATE_SNAPSHOTS = os.getenv("UPDATE_SNAPSHOTS", "false").lower() == "true"
SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "snapshots")


# ---------------------------------------------------------------------------
# Helper: screenshot comparison using PIL/numpy
# ---------------------------------------------------------------------------

def assert_screenshot(page: Page, name: str, threshold: float = 0.1, full_page: bool = False):
    """
    D1 Image Recognition: custom PIL-based screenshot comparison.

    On first run (or UPDATE_SNAPSHOTS=true): saves baseline to snapshots/.
    On subsequent runs: compares against baseline, fails if mean pixel diff > threshold.
    threshold=0.1 means ≤10% mean-normalised pixel deviation is acceptable.
    """
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    baseline_path = os.path.join(SNAPSHOT_DIR, name)

    screenshot_bytes = page.screenshot(full_page=full_page)

    if UPDATE_SNAPSHOTS or not os.path.exists(baseline_path):
        with open(baseline_path, "wb") as f:
            f.write(screenshot_bytes)
        print(f"[VIS] Baseline saved: {name}")
        return  # No comparison on baseline creation

    actual_img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    baseline_img = Image.open(baseline_path).convert("RGB")

    if actual_img.size != baseline_img.size:
        actual_path = baseline_path.replace(".png", "-actual.png")
        actual_img.save(actual_path)
        raise AssertionError(
            f"[VIS] Size mismatch for {name}: "
            f"baseline={baseline_img.size}, actual={actual_img.size}. "
            f"Actual saved to {actual_path}. Run with UPDATE_SNAPSHOTS=true to regenerate."
        )

    actual_arr = np.array(actual_img, dtype=float)
    baseline_arr = np.array(baseline_img, dtype=float)
    diff_ratio = np.abs(actual_arr - baseline_arr).mean() / 255.0

    if diff_ratio > threshold:
        actual_path = baseline_path.replace(".png", "-actual.png")
        actual_img.save(actual_path)
        raise AssertionError(
            f"[VIS] Visual regression detected in {name}: "
            f"diff={diff_ratio:.4f} > threshold={threshold}. "
            f"Actual saved to {actual_path}. Run with UPDATE_SNAPSHOTS=true to update baseline."
        )

    print(f"[VIS] {name} OK (diff={diff_ratio:.4f})")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_part_via_api(api_headers, name, **kwargs):
    resp = requests.post(
        f"{BASE_URL}/api/part/",
        json={"name": name, "description": f"Visual test: {name}", **kwargs},
        headers=api_headers
    )
    assert resp.status_code == 201, f"Setup failed: {resp.text}"
    return resp.json()["pk"]


def _delete_part_via_api(api_headers, pk):
    requests.patch(f"{BASE_URL}/api/part/{pk}/", json={"active": False}, headers=api_headers, timeout=5)
    requests.delete(f"{BASE_URL}/api/part/{pk}/", headers=api_headers, timeout=5)


# ---------------------------------------------------------------------------
# Visual Regression Tests
# ---------------------------------------------------------------------------

@pytest.mark.visual
def test_VIS_P_001_part_detail_visual(page: Page, api_headers):
    """VIS-P-001: Visual baseline for Part detail page."""
    pk = _create_part_via_api(api_headers, "VIS-P-001 Visual Part", component=True, purchaseable=True)
    try:
        detail = PartDetailPage(page)
        detail.open(pk)
        page.wait_for_load_state("networkidle")

        # Hide dynamic elements that would cause flakiness (timestamps, etc.)
        page.evaluate("""
            document.querySelectorAll('.creation-date, .modified-date, [data-timestamp]')
                .forEach(el => el.style.visibility = 'hidden');
        """)

        assert_screenshot(page, "part-detail.png", threshold=0.1, full_page=False)
    finally:
        _delete_part_via_api(api_headers, pk)


@pytest.mark.visual
def test_VIS_P_002_part_create_form_visual(page: Page):
    """VIS-P-002: Visual baseline for Part creation form."""
    create_page = PartCreatePage(page)
    create_page.open()
    page.wait_for_load_state("networkidle")
    # Wait for the create modal to fully render before screenshot
    expect(page.locator("[role='dialog']")).to_be_visible(timeout=8000)

    # Mask any dynamic content in the form (version badges, timestamps)
    page.evaluate("""
        document.querySelectorAll('.creation-date, .modified-date, [data-timestamp]')
            .forEach(el => el.style.visibility = 'hidden');
    """)

    assert_screenshot(page, "part-create-form.png", threshold=0.1, full_page=False)


@pytest.mark.visual
def test_VIS_P_003_category_view_visual(page: Page, api_headers):
    """VIS-P-003: Visual baseline for Category list view."""
    resp = requests.post(
        f"{BASE_URL}/api/part/category/",
        json={"name": "VIS-P-003 Category", "description": "Visual test category"},
        headers=api_headers
    )
    assert resp.status_code == 201, f"VIS-P-003 setup failed: {resp.text}"
    cat_pk = resp.json()["pk"]

    try:
        category_page = CategoryPage(page)
        category_page.open_category(cat_pk)
        page.wait_for_load_state("networkidle")

        # Mask dynamic content for stable baseline
        page.evaluate("""
            document.querySelectorAll('.creation-date, .modified-date, [data-timestamp]')
                .forEach(el => el.style.visibility = 'hidden');
        """)

        assert_screenshot(page, "category-view.png", threshold=0.1, full_page=True)
    finally:
        if cat_pk:
            requests.delete(f"{BASE_URL}/api/part/category/{cat_pk}/", headers=api_headers)


@pytest.mark.visual
def test_VIS_P_004_part_attributes_all_visual(page: Page, api_headers):
    """VIS-P-004: Visual baseline for part with all attributes set."""
    pk = _create_part_via_api(
        api_headers,
        "VIS-P-004 All Attributes Part",
        assembly=True,
        component=True,
        trackable=True,
        purchaseable=True,
        salable=True,
        is_template=False,
    )
    try:
        detail = PartDetailPage(page)
        detail.open(pk)
        page.wait_for_load_state("networkidle")

        page.evaluate("""
            document.querySelectorAll('.creation-date, .modified-date, [data-timestamp]')
                .forEach(el => el.style.visibility = 'hidden');
        """)

        assert_screenshot(page, "part-attributes-all.png", threshold=0.1, full_page=False)
    finally:
        _delete_part_via_api(api_headers, pk)
