"""
Selector discovery script for InvenTree React frontend.
Crawls all relevant pages and dumps interactive elements.
Run once to get all selectors needed for page objects.

Usage:
  py discover_selectors.py

Reads configuration from environment variables (or .env file):
  INVENTREE_URL   (default: http://localhost:8000)
  INVENTREE_USER  (default: admin)
  INVENTREE_PASS  (default: inventree)
"""
import json
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

BASE_URL = os.getenv("INVENTREE_URL", "http://localhost:8000")
USERNAME = os.getenv("INVENTREE_USER", "admin")
PASSWORD = os.getenv("INVENTREE_PASS", "inventree")
OUTPUT_FILE = "discovered_selectors.json"

results = {}

def dump_elements(page, label):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    data = page.evaluate("""() => {
        const info = { buttons: [], inputs: [], links: [], tabs: [], roles: [] };

        document.querySelectorAll('button').forEach(el => {
            info.buttons.push({
                text: el.innerText?.trim().slice(0, 80),
                ariaLabel: el.getAttribute('aria-label'),
                id: el.id,
                type: el.type,
                role: el.getAttribute('role'),
                dataTestid: el.getAttribute('data-testid')
            });
        });

        document.querySelectorAll('input, textarea, select').forEach(el => {
            const labelEl = el.labels?.[0] || document.querySelector(`label[for="${el.id}"]`);
            info.inputs.push({
                type: el.type,
                name: el.getAttribute('name'),
                id: el.id,
                ariaLabel: el.getAttribute('aria-label'),
                placeholder: el.getAttribute('placeholder'),
                label: labelEl?.innerText?.trim(),
                dataTestid: el.getAttribute('data-testid')
            });
        });

        document.querySelectorAll('a[href]').forEach(el => {
            info.links.push({
                text: el.innerText?.trim().slice(0, 60),
                href: el.getAttribute('href'),
                ariaLabel: el.getAttribute('aria-label')
            });
        });

        document.querySelectorAll('[role="tab"]').forEach(el => {
            info.tabs.push({
                text: el.innerText?.trim(),
                ariaLabel: el.getAttribute('aria-label'),
                id: el.id
            });
        });

        return info;
    }""")
    results[label] = data
    print(f"\n{'='*60}")
    print(f"PAGE: {label}")
    print(f"{'='*60}")
    print(f"  Buttons ({len(data['buttons'])}):")
    for b in data['buttons']:
        if b['text'] or b['ariaLabel']:
            print(f"    text='{b['text']}' | aria-label='{b['ariaLabel']}' | id='{b['id']}'")
    print(f"  Inputs ({len(data['inputs'])}):")
    for i in data['inputs']:
        print(f"    type={i['type']} name='{i['name']}' id='{i['id']}' aria='{i['ariaLabel']}' placeholder='{i['placeholder']}' label='{i['label']}'")
    print(f"  Tabs ({len(data['tabs'])}):")
    for t in data['tabs']:
        print(f"    text='{t['text']}' | aria-label='{t['ariaLabel']}'")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # --- LOGIN ---
    print("Logging in...")
    page.goto(f"{BASE_URL}/web")
    page.wait_for_selector("[aria-label='login-username']", timeout=15000)
    page.fill("[aria-label='login-username']", USERNAME)
    page.fill("[aria-label='login-password']", PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    print("Logged in.")

    # --- 1. PARTS CATEGORY INDEX ---
    page.goto(f"{BASE_URL}/web/part/category/index/")
    dump_elements(page, "1_parts_category_index")

    # --- 2. OPEN CREATE PART MODAL ---
    print("\nTrying to open Create Part modal...")
    # Try all possible button selectors
    possible = [
        "[aria-label='action-menu-add-parts']",
        "button:has-text('New Part')",
        "button:has-text('Add Part')",
        "button:has-text('Create')",
        "[aria-label*='add']",
        "[aria-label*='part']",
    ]
    clicked = False
    for sel in possible:
        try:
            loc = page.locator(sel).first
            if loc.is_visible():
                print(f"  Found trigger: {sel}")
                loc.click()
                page.wait_for_timeout(1000)
                clicked = True
                break
        except Exception:
            continue

    if clicked:
        # Try to find and click a "Create Part" menu item
        menu_options = [
            "[aria-label='action-menu-add-parts-create-part']",
            "[role='menuitem']:has-text('Create Part')",
            "[role='menuitem']:has-text('New Part')",
            "[role='option']:has-text('Create')",
        ]
        for sel in menu_options:
            try:
                loc = page.locator(sel).first
                if loc.is_visible():
                    print(f"  Found menu item: {sel}")
                    loc.click()
                    page.wait_for_timeout(1500)
                    break
            except Exception:
                continue

        dump_elements(page, "2_create_part_modal")
        # Close modal
        esc = page.locator("[aria-label='Close'], button:has-text('Cancel'), button:has-text('Close')")
        if esc.first.is_visible():
            esc.first.click()
        else:
            page.keyboard.press("Escape")
        page.wait_for_timeout(500)

    # --- 3. NAVIGATE TO A PART DETAIL PAGE ---
    print("\nNavigating to a part detail page...")
    import requests, base64
    token_resp = requests.get(f"{BASE_URL}/api/user/token/", auth=(USERNAME, PASSWORD))
    if token_resp.status_code == 200:
        token = token_resp.json().get("token", "")
    else:
        token_resp2 = requests.post(f"{BASE_URL}/api/user/token/", auth=(USERNAME, PASSWORD))
        token = token_resp2.json().get("token", "")

    headers = {"Authorization": f"Token {token}"}

    # Get or create a part
    parts_resp = requests.get(f"{BASE_URL}/api/part/?limit=1", headers=headers)
    parts = parts_resp.json().get("results", [])
    if parts:
        part_pk = parts[0]["pk"]
        print(f"  Using existing part pk={part_pk}")
    else:
        create_resp = requests.post(
            f"{BASE_URL}/api/part/",
            json={"name": "Discovery Test Part", "description": "For selector discovery"},
            headers=headers
        )
        part_pk = create_resp.json()["pk"]
        print(f"  Created part pk={part_pk}")

    page.goto(f"{BASE_URL}/web/part/{part_pk}/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    dump_elements(page, "3_part_detail_page")

    # --- 4. CATEGORIES PAGE ---
    page.goto(f"{BASE_URL}/web/part/category/index/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Try to open new category modal
    cat_buttons = [
        "[aria-label*='category']",
        "button:has-text('New Category')",
        "button:has-text('Add Category')",
        "[aria-label*='add-categor']",
    ]
    for sel in cat_buttons:
        try:
            loc = page.locator(sel).first
            if loc.is_visible():
                print(f"\n  Found category button: {sel}")
                loc.click()
                page.wait_for_timeout(1000)
                dump_elements(page, "4_create_category_modal")
                page.keyboard.press("Escape")
                break
        except Exception:
            continue

    # Save results
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n\nAll done! Full results saved to: {OUTPUT_FILE}")
    browser.close()
