# QAHub AI Hackathon 2026 — Claude Code Instructions

## Project Context
This is a hackathon project named **ANYMUS** — an AI-Native Shift Left QA pipeline.
AUT is the **InvenTree Parts Module**. Deadline: **April 14, 2026 — 19:00 UTC+5**.
Full plan and architecture: `Plan.md`.

## Application Endpoints
- **Local InvenTree**: `http://inventree.localhost` (Docker — Caddy proxy on port 80)
- **API Base**: `http://inventree.localhost/api/`
- **OpenAPI Schema**: `http://inventree.localhost/api/schema/?format=json`
- **Demo**: `https://demo.inventree.org`
- **API Docs**: `https://docs.inventree.org/en/stable/api/schema/part/`
- **Parts Docs**: `https://docs.inventree.org/en/stable/part/`

## Auth
- Username: `admin`, Password: `inventree`
- **InvenTree v1.3.0+**: Get API token via `GET /api/user/token/` with Basic Auth (not POST)
- Fallback to `POST /api/user/token/` for older versions
- Use header: `Authorization: Token <token>`

## Tech Stack

### API Automation (`automation/api/`)
- Python, pytest, requests, schemathesis, responses, pytest-html, python-dotenv
- Run: `cd automation/api && pytest tests/ -v --html=report.html`
- Mock mode: `MOCK_MODE=true pytest tests/test_part_mock.py -v`
- Health check: `python scripts/health_check.py --base-url http://inventree.localhost`

### UI Automation (`automation/ui/`)
- Python, playwright, pytest-playwright, pillow, pytest-html
- Run: `cd automation/ui && pytest tests/ -v --headed`
- Visual tests only: `pytest tests/test_visual_regression.py -v --headed`
- Update snapshots: `UPDATE_SNAPSHOTS=true pytest tests/test_visual_regression.py`

## Key Differentiators — Always Apply These

### D1 — Image Recognition
- Use `expect(page).toHaveScreenshot("name.png")` for critical Part pages
- Baselines stored in `automation/ui/snapshots/`
- Target pages: Part Detail, Part Create form, Category view, final state of cross-functional test
- Mark visual tests with `@pytest.mark.visual`

### D2 — Mock API Mode
- `responses` library intercepts HTTP calls when `MOCK_MODE=true`
- Mock fixtures live in `automation/api/mocks/*.json`
- All mock tests in `tests/test_part_mock.py`
- Mock tests must cover the same business logic as live tests — just against fixtures

### D3 — Pre-flight Health Check
- `scripts/health_check.py` pings all Part API endpoints, prints status table, exits 0/1
- `automation/api/tests/test_meta_health.py` runs first (filename prefix ensures order), skips suite on failure
- `automation/ui/conftest.py` has `api_health_gate` session fixture (autouse=True) that skips all UI tests if API is down
- Endpoints to check: `/api/`, `/api/part/`, `/api/part/category/`, `/api/part/category/tree/`, `/api/part/category/parameters/`, `/api/part/test-template/`

## Code Conventions
- Test IDs: UI=`UI-P-XXX`, API=`API-P-XXX`, Health=`HC-XXX`, Visual=`VIS-P-XXX`, Mock=`MOCK-P-XXX`
- Page Object Model for all UI — no raw selectors in test files ever
- Pytest fixtures in `conftest.py` for auth, cleanup, browser, health gate
- All config via environment variables (see below), never hardcoded
- `@pytest.mark.parametrize` for all boundary/edge cases
- Every test: assert status code + response body field + business rule

## Environment Variables
```
INVENTREE_URL=http://localhost:8000
INVENTREE_USER=admin
INVENTREE_PASS=inventree
MOCK_MODE=false
UPDATE_SNAPSHOTS=false
```

## Shift Left Principles — Apply to Every File
1. Test cases must trace back to a documented requirement or schema constraint
2. API contract tests (schemathesis) run before UI tests in CI pipeline
3. Health check pre-flight gates both API and UI test execution
4. Mock mode ensures testing never stops due to infrastructure unavailability
5. Visual baselines catch regressions DOM tests cannot see

## Git Branches
- `main` — final submission
- `AgenticWorkflow` — active development branch

## What NOT to do
- Do not write tests for features outside the Parts module
- Do not use `time.sleep()` — use `page.wait_for_selector()` or `expect(locator).to_be_visible()`
- Do not hardcode base URL or credentials — always use env vars or fixtures
- Do not skip cleanup fixtures — all tests must be idempotent
- Do not put selectors directly in test files — Page Objects only
- Do not commit `.env` files — use `.env.example` with placeholder values

---

## InvenTree v1.3.0 React Frontend — Agentic Automation Guide

> This section documents hard-won knowledge from live selector discovery on InvenTree v1.3.0.
> If tests fail to find elements, consult this section first before debugging blindly.
> The `automation/ui/discover_selectors.py` script can regenerate `discovered_selectors.json`
> to verify current selectors if the InvenTree version is upgraded.

### Frontend Architecture
InvenTree v1.3.0 replaced all Django templates with a **React SPA** using:
- **Mantine UI** for components (dynamic IDs — NEVER use `id=` selectors)
- **React Router** for navigation (URL-based tab routing)
- **TanStack Query** for data fetching (tables render asynchronously — always wait)
- **ActionDropdown** pattern for all action menus

### Navigation URL Map

| View | URL Pattern |
|---|---|
| Login | `/web` |
| Parts home | `/web/part` |
| Category index | `/web/part/category/index/` |
| Category details tab | `/web/part/category/index/details` |
| Category subcategories tab | `/web/part/category/index/subcategories` |
| **Category parts tab (create parts here)** | `/web/part/category/index/parts` |
| Specific category | `/web/part/category/{pk}/` |
| Specific category subcategories | `/web/part/category/{pk}/subcategories` |
| Part detail | `/web/part/{pk}/` or `/web/part/{pk}/details` |
| Part tab (generic) | `/web/part/{pk}/{tabname}` |

**Available part tab slugs**: `details`, `stock`, `allocations`, `used_in`, `pricing`,
`suppliers`, `purchase_orders`, `related_parts`, `parameters`, `attachments`, `notes`

### Selector Patterns — Always Use These

#### Login
```python
USERNAME_INPUT = "[aria-label='login-username']"
PASSWORD_INPUT = "[aria-label='login-password']"
SUBMIT_BUTTON  = "button[type='submit']"  # Login form is the ONLY button[type=submit]
```

#### Action Menus (ActionDropdown pattern)
All action buttons follow `action-menu-{area}` and items follow `action-menu-{area}-{action}`:
```python
# Parts table (at /web/part/category/index/parts)
ADD_PARTS_MENU        = "[aria-label='action-menu-add-parts']"
CREATE_PART_ITEM      = "[aria-label='action-menu-add-parts-create-part']"

# Part detail page
PART_ACTIONS_MENU     = "[aria-label='action-menu-part-actions']"
EDIT_PART_ITEM        = "[aria-label='action-menu-part-actions-edit']"
DUPLICATE_PART_ITEM   = "[aria-label='action-menu-part-actions-duplicate']"
DELETE_PART_ITEM      = "[aria-label='action-menu-part-actions-delete']"  # disabled for active parts
STOCK_ACTIONS_MENU    = "[aria-label='action-menu-stock-actions']"
# NOTE: action-menu-stock-actions-add-stock is for incrementing EXISTING stock (row-based table)
# To create a NEW stock item from scratch, navigate to /web/part/{pk}/stock then click:
ADD_STOCK_ITEM_BTN    = "[aria-label='action-button-add-stock-item']"  # on Stock tab — creates new

# Category pages
ADD_CATEGORY_BUTTON   = "[aria-label='action-button-add-part-category']"  # Direct button, no sub-menu
CATEGORY_ACTIONS_MENU = "[aria-label='action-menu-category-actions']"
DELETE_CATEGORY_ITEM  = "[aria-label='action-menu-category-actions-delete']"
```

#### Modal Forms
All create/edit forms open as modals with `role='dialog'`. **Critical**: Submit buttons are
`type="button"` (NOT `type="submit"`) — use text-based selectors:
```python
MODAL         = "[role='dialog']"
SUBMIT_BUTTON = "[role='dialog'] button:has-text('Submit')"  # Create/Edit modals
DELETE_BUTTON = "[role='dialog'] button:has-text('Delete')"  # Delete confirmation modals
CANCEL_BUTTON = "[role='dialog'] button:has-text('Cancel')"
```

#### Modal Field Selectors (use aria-label, NOT label text — labels have dynamic * suffixes)
```python
# Part create/edit modal
"[aria-label='text-field-name']"
"[aria-label='text-field-description']"
"[aria-label='text-field-IPN']"
"[aria-label='text-field-revision']"
"[aria-label='text-field-keywords']"
"[aria-label='text-field-units']"
"[aria-label='related-field-category']"      # react-select dropdown

# Category create modal
"[aria-label='text-field-name']"
"[aria-label='text-field-description']"

# Checkbox toggles (part attributes)
"[aria-label='boolean-field-assembly']"
"[aria-label='boolean-field-component']"
"[aria-label='boolean-field-purchaseable']"
"[aria-label='boolean-field-trackable']"
"[aria-label='boolean-field-is_template']"
"[aria-label='boolean-field-testable']"
"[aria-label='boolean-field-virtual']"
"[aria-label='boolean-field-active']"
```

#### React-Select Dropdowns
React-select fields (category, location, supplier, etc.) require type-then-click:
```python
# Example: selecting a category
modal.locator("[aria-label='related-field-category']").fill("Category Name")
page.wait_for_selector("[role='option']:has-text('Category Name')", timeout=5000)
page.locator("[role='option']:has-text('Category Name')").first.click()
```

### InvenTree API Behaviors — Critical for Test Fixtures

#### Part Lifecycle (Soft Delete)
Parts MUST be deactivated before deletion. Direct DELETE returns HTTP 400:
```python
# WRONG — returns 400 "Cannot delete this part as it is still active"
requests.delete(f"{BASE_URL}/api/part/{pk}/", headers=headers)

# CORRECT — deactivate first, then delete
requests.patch(f"{BASE_URL}/api/part/{pk}/", json={"active": False}, headers=headers)
requests.delete(f"{BASE_URL}/api/part/{pk}/", headers=headers)  # returns 204
```

**UI delete**: The `action-menu-part-actions-delete` menu item has `disabled` attribute when the part
is active. You must deactivate the part via API PATCH first, then reload the detail page, then
the Delete option becomes clickable. The delete confirmation modal uses `button:has-text('Delete')`.

#### API Response Format Varies by Query Parameter
```python
# Paginated (returns dict with "results" key)
GET /api/part/?limit=50         → {"count": N, "results": [...]}

# Search / filter without limit (returns flat list!)
GET /api/part/?search=name      → [...]   ← NOT a dict!

# Always use limit= to get paginated format:
GET /api/part/?search=name&limit=50  → {"count": N, "results": [...]}
```

Always normalize: `data.get("results", []) if isinstance(data, dict) else data`

#### API Token
```python
# v1.3.0: GET (not POST) returns token for valid admin user
GET /api/user/token/  with Basic Auth  → {"token": "inv-..."}
```

#### Categories — No Deactivation Needed
Unlike parts, categories can be deleted directly (HTTP DELETE returns 204 immediately).

### Running the Test Suite

```bash
cd automation/ui

# Install dependencies (first time only)
py -m pip install -r requirements.txt
py -m playwright install chromium

# Run all UI tests (headed for visibility)
py -m pytest tests/ -v --headed

# Run specific test file
py -m pytest tests/test_part_crud.py -v --headed

# Run single test
py -m pytest tests/test_part_crud.py::test_UI_P_001_create_part_required_fields_only -v --headed

# Generate/update visual regression baselines
UPDATE_SNAPSHOTS=true py -m pytest tests/test_visual_regression.py -v --headed

# Headless (for CI)
py -m pytest tests/ -v
```

**Note**: Use `py` (Python Launcher) instead of `python` or `python3` on Windows.

### Discovering Selectors (When InvenTree Is Upgraded)
If selectors stop working after an InvenTree upgrade, run the discovery script:
```bash
cd automation/ui
py discover_selectors.py
# Outputs: discovered_selectors.json with all interactive elements
```
Then compare with the patterns above and update page objects accordingly.
The script navigates to: category index, create part modal, part detail, create category modal.

### Test Coverage — Current Status (32/32 passing)

| Test File | Test IDs | Status |
|---|---|---|
| `test_part_crud.py` | UI-P-001,002,003,004,005,006,007,008,009,010 | ✅ All passing |
| `test_part_attributes.py` | UI-P-012,013,015,017,020,024 | ✅ All passing |
| `test_part_categories.py` | UI-P-034,035,036,038,039 | ✅ All passing |
| `test_part_parameters.py` | UI-P-027,027b,027c | ✅ All passing |
| `test_cross_functional.py` | XF E2E flow | ✅ Passing |
| `test_visual_regression.py` | VIS-P-001..004 | ✅ Baselines generated |

**Remaining gaps (not in scope for hackathon)**:
- UI-P-021-026: Part detail tab navigation and content verification
- UI-P-041-045: Revision chain (part cannot be revision of itself; `revision_of` FK)
- UI-P-049-050: Template/Variant relationship (variant_of FK; Variants tab appears on template)

**Critical notes for future sessions:**
- Parameter template `_create_parameter_template_via_api` must be idempotent (handle existing templates)
- Visual regression baselines regenerated with `UPDATE_SNAPSHOTS=true py -m pytest tests/test_visual_regression.py`
- Delete part menu item is DISABLED for active parts — must deactivate via API first
- New stock item: use `action-button-add-stock-item` on Stock tab; NOT `action-menu-stock-actions-add-stock`
