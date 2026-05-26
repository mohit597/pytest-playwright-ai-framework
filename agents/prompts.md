# ANYMUS — Agent Prompts Log

> This file documents all prompts used with Claude Code (via CodemIE) during the hackathon.
> Each prompt is an artefact demonstrating the AI-native shift-left QA pipeline.
> **Tool:** Claude Code (claude-sonnet-4-6) via CodemIE IDE extension
> **Project config:** `CLAUDE.md` in repo root

---

## API Automation Prompts — D2 + D3

### Prompt S-01 — API Manual Test Case Generation

**Tool:** Claude Code via CodemIE
**Output:** `test-cases/api-manual-tests.md` — 74 test cases

```
Ingest the InvenTree Parts API schema from https://docs.inventree.org/en/stable/api/schema/part/
Generate comprehensive API manual test cases in markdown table format with columns:
Test ID | Endpoint | Method | Test Name | Preconditions | Input | Expected Status | Expected Response | Type

Cover: CRUD operations, filtering/pagination, field validation, relational integrity, edge cases.
Include boundary value analysis and negative scenarios from schema constraints.
Output to test-cases/api-manual-tests.md. Minimum 30 test cases.
```

---

### Prompt S-02 — API Automation Scaffold

**Tool:** Claude Code via CodemIE
**Output:** `automation/api/conftest.py`, `config/settings.py`, 7 initial test files

```
Generate pytest + requests API automation scripts for InvenTree Parts module.
Base URL from env var INVENTREE_URL (default http://localhost:8000). Auth via token header.

Create these files:
- automation/api/conftest.py: auth token fixture (GET /api/user/token/), part cleanup fixture, base_url from env
- automation/api/config/settings.py: ENV-based config (INVENTREE_URL, INVENTREE_USER, INVENTREE_PASS, MOCK_MODE)
- automation/api/tests/test_part_crud.py: full CRUD with assertions on status + response body + business rules
- automation/api/tests/test_part_filtering.py: ?search=, ?category=, ?active=, ?limit=, ?offset= with parametrize
- automation/api/tests/test_part_validation.py: missing required fields, max length violations, read-only field rejection
- automation/api/tests/test_part_categories.py: category CRUD, parent/child hierarchy, tree endpoint
- automation/api/tests/test_schema_contract.py: schemathesis against /api/schema/?format=json targeting /api/part/ paths
```

---

### Prompt S-03 — Mock API Mode (D2)

**Tool:** Claude Code via CodemIE
**Output:** `automation/api/mocks/*.json`, `tests/test_part_mock.py`

```
Add mock API testing to the InvenTree pytest suite using the `responses` library.

1. Create automation/api/mocks/ directory with JSON fixture files:
   - part_list.json: mock GET /api/part/ response (list of 3 parts with all fields)
   - part_detail.json: mock GET /api/part/1/ response (single part, all fields)
   - part_create_201.json: mock POST /api/part/ success response
   - part_create_400.json: mock POST /api/part/ validation error response
   - category_list.json: mock GET /api/part/category/ response

2. Create automation/api/tests/test_part_mock.py:
   - Use @responses.activate decorator to intercept HTTP calls
   - Load fixtures from mocks/*.json
   - Test same business logic as test_part_crud.py but against mock responses
   - Controlled by MOCK_MODE=true env variable (skip if false)

3. Update conftest.py: add mock_mode fixture that reads MOCK_MODE env var
```

---

### Prompt S-04 — Health Check Script (D3)

**Tool:** Claude Code via CodemIE
**Output:** `scripts/health_check.py`, `tests/test_meta_health.py`

```
Create a pre-flight health check system for InvenTree API:

1. Create scripts/health_check.py:
   - Ping: /api/, /api/part/, /api/part/category/, /api/part/category/tree/,
     /api/part/parameter/, /api/part/test-template/
   - Print a table: Endpoint | Status Code | Latency | UP/DOWN
   - Exit code 0 if all critical endpoints up, exit code 1 if any down
   - Accept --base-url argument (default http://localhost:8000)
   - Timeout per request: 5 seconds

2. Create automation/api/tests/test_meta_health.py:
   - Filename prefix ensures it runs first in pytest
   - Tests: all 6 endpoints return 200 or 401 (not 500/404/connection refused)
   - If any endpoint is down: pytest.skip() remaining tests with clear message
   - Mark with @pytest.mark.health
```

---

### Prompt S-05 — Jira User Story Extraction via MCP + REST API

**Tool:** Claude Code via CodemIE + Official Atlassian Remote MCP + Jira REST API v2 (curl)
**Output:** `test-cases/jira-user-stories.json` (44 stories), `test-cases/jira-user-stories.csv`

```
Configure the Official Atlassian Remote MCP server at https://mcp.atlassian.com/v1/mcp
with Bearer token authentication. Then extract all 44 Jira user stories
(EPMCDMETST-37840 to EPMCDMETST-37883) from jiraeu.epam.com using Jira REST API v2.

For each story, fetch:
  - key, summary, issuetype, status, priority, reporter, created, updated
  - Full description text (parsed from Jira wiki markup)
  - Acceptance criteria (parsed from AC section in description)
  - Test scenarios (extracted Gherkin blocks)

Save everything to:
1. test-cases/jira-user-stories.json — structured JSON with AI tools metadata header
   Include header: "extracted_via": "Claude Code (CodemIE) + Jira REST API v2 (Bearer Token)"
2. test-cases/jira-user-stories.csv — 44 rows × 16 columns for demo purposes

This JSON/CSV demonstrates the full AI toolchain: MCP → Jira → Claude Code → test cases.
```

---

### Prompt S-06 — Quality Test Case Curation (176 → 54)

**Tool:** Claude Code via CodemIE
**Output:** `test-cases/api-test-cases.json`, `test-cases/api-test-review.md`

```
Review the 176 AI-generated API test cases (provided as input) and curate only
high-quality, non-duplicate automation targets.

Reduction criteria:
- Remove tests already covered by existing automation files (test_part_crud.py,
  test_part_filtering.py, test_part_validation.py, test_part_categories.py,
  test_schema_contract.py)
- Remove duplicates and overlapping scenarios within the 176
- Defer out-of-scope tests (pricing, stock location, image upload, import/export)
- Keep: all unique business rules, constraint validations, referential integrity,
  lifecycle tests not yet covered

Output:
1. test-cases/api-test-cases.json — 54 curated test cases with full automation metadata
   (tc_id, story, endpoint, method, fixtures, payload, expected_status, assertions,
    automation_file, automation_status)
2. test-cases/api-test-review.md — review rationale with coverage table and build order
```

---

### Prompt S-07 — Advanced API Automation (BOM, Revisions, Related Parts, Notes, Attachments)

**Tool:** Claude Code via CodemIE
**Output:** 7 new test files + 7 new fixtures + appended to 3 existing files (165 total tests)

```
Automate the 54 curated quality test cases for InvenTree Parts module.
Follow existing patterns from conftest.py, test_part_crud.py, test_part_filtering.py.

New fixtures to add to conftest.py:
  created_template_part, created_assembly_part, created_component_part,
  parameter_template, inactive_part, two_parts, created_bom_item
  (all function-scoped with yield + cleanup)

New test files to create:
- tests/test_part_parameters.py: API-P-081 to API-P-085, 119 (7 tests)
- tests/test_part_templates.py: API-P-086 to API-P-089, 118 (7 tests)
- tests/test_part_revisions.py: API-P-090 to API-P-097 (8 tests)
- tests/test_part_bom.py: API-P-098 to API-P-103, 122 (8 tests)
- tests/test_part_attachments.py: API-P-104 to API-P-106 (3 tests, multipart upload)
- tests/test_part_related.py: API-P-107 to API-P-109 (5 tests)
- tests/test_part_notes.py: API-P-123 to API-P-124 (5 tests)

Append to existing files:
- test_part_filtering.py: sorting + IPN search tests (API-P-120, 121, 132, 134)
- test_part_validation.py: IPN uniqueness, boolean flags, PUT 405, FK 400 tests
- test_part_categories.py: circular reference + deletion constraint tests

Rules: pytest.mark.crud for happy path, pytest.mark.validation for constraints.
Every test: assert status code + response body + business rule.
All cleanup via fixture yield — no manual delete in test body.
```

---

### Prompt S-08 — Cleanup Test Infrastructure

**Tool:** Claude Code via CodemIE
**Output:** `tests/test_cleanup.py` (19 tests) + `pre_suite_cleanup` fixture in conftest.py

```
Add comprehensive cleanup test infrastructure for InvenTree running in Docker.

1. Add pre_suite_cleanup fixture to conftest.py:
   - scope="session", autouse=True
   - Runs before AND after the test session (yield pattern)
   - Deletes all ANYMUS* test data in referential integrity order:
     BOM items → related links → attachments → part parameters →
     parts (non-templates first, then templates) → parameter templates → categories
   - Uses search API (?search=ANYMUS) to find orphaned data from failed previous runs
   - All errors silently swallowed (server may be down during cleanup)
   - Skipped in MOCK_MODE

2. Create tests/test_cleanup.py with 4 test classes:
   - TestPreSuiteState: verify no orphaned ANYMUS data at session start (3 tests)
   - TestResourceLifecycle: create→delete→404 for every resource type (7 tests)
   - TestReferentialIntegrityCleanup: deletion blocked by dependencies (2 tests)
   - TestFixtureIdempotency: all 7 conftest fixtures create resources correctly (7 tests)

Mark all with @pytest.mark.cleanup. Named test_cleanup.py so it sorts before
test_part_*.py alphabetically — orphan check runs before any part tests.
```

---

## UI Automation Prompts — D1 + D3 gate

### Prompt A1 — UI Manual Test Case Generation (Phase 1)

**Tool:** Claude Code via CodemIE
**Input sources:**
- `https://docs.inventree.org/en/stable/part/`
- `https://docs.inventree.org/en/stable/part/views/`
- `https://docs.inventree.org/en/stable/part/parameter/`
- `https://docs.inventree.org/en/stable/part/template/`
- `https://docs.inventree.org/en/stable/part/revision/`
**Output:** `test-cases/ui-manual-tests.md` — 50 test cases

```
Ingest InvenTree Parts documentation from these GitHub raw URLs:
- https://raw.githubusercontent.com/inventree/InvenTree/master/docs/docs/part/views.md
- https://raw.githubusercontent.com/inventree/InvenTree/master/docs/docs/part/revision.md
- https://raw.githubusercontent.com/inventree/InvenTree/master/docs/docs/part/template.md
- https://raw.githubusercontent.com/inventree/InvenTree/master/docs/docs/concepts/parameters.md
- https://raw.githubusercontent.com/inventree/InvenTree/master/docs/docs/part/index.md

Generate comprehensive UI manual test cases in markdown table format:
Test ID | Test Name | Preconditions | Steps | Expected Result | Priority | Type (Positive/Negative/Boundary)

Cover: Part creation (form + import), all Part detail tabs, Part attributes (all 8 types),
categories hierarchy, units of measure, revisions (constraints), negative/boundary cases.
Emphasize Shift Left: derive test cases directly from documented business rules.
Output to test-cases/ui-manual-tests.md. Minimum 40 test cases. Use ID prefix UI-P-XXX.
```

---

### Prompt A2 — Page Object Model Generation (Phase 3)

**Tool:** Claude Code via CodemIE
**Output:** 6 page object files in `automation/ui/pages/`

```
Generate Playwright (Python) Page Object Model classes for InvenTree Parts module.
Base URL from env var INVENTREE_URL (default http://localhost:8000).
Auth: admin/inventree from env vars INVENTREE_USER / INVENTREE_PASS.

Create these page objects in automation/ui/pages/:
- base_page.py: common actions (wait_for_load, click, fill, navigate, get_text, is_visible)
- login_page.py: login flow with credentials from env vars, assert_logged_in method
- parts_list_page.py: list view, search, navigate to category, get part count, click part by name
- part_detail_page.py: all tabs (click_tab methods), attribute visibility checks, parameters, stock actions
- part_create_page.py: creation form fields, attribute toggles, submit, assert validation errors
- category_page.py: create category, delete category, navigate hierarchy, breadcrumb

Rules:
- No raw selectors in test files — all selectors in page objects only
- No time.sleep() — use expect(locator).to_be_visible() or wait_for_load_state()
- All config from env vars, never hardcoded
```

---

### Prompt A3 — UI Automation Test Files (Phase 3)

**Tool:** Claude Code via CodemIE
**Output:** 5 test files in `automation/ui/tests/`

```
Generate Playwright (Python) UI automation test files for InvenTree Parts module.
Use the Page Object Model classes already created in automation/ui/pages/.

Create these test files in automation/ui/tests/:
- test_part_crud.py: UI-P-001..010 — part create, edit, delete, boundary names
- test_part_attributes.py: UI-P-011..020 — Assembly shows BOM tab, Component shows Used In tab, etc.
- test_part_categories.py: UI-P-034..040 — hierarchy creation, breadcrumb navigation
- test_part_parameters.py: UI-P-027 — add parameter, assign value, verify on detail page
- test_cross_functional.py: Full flow — create category (API) → create part (UI) →
  add parameter (UI) → create stock (UI) → verify in category view (UI)

Rules: no raw selectors, no time.sleep(), @pytest.mark.parametrize for boundary tests,
cleanup via fixtures, test IDs in docstrings.
```

---

### Prompt A4 — Visual Regression Tests — D1 Differentiator

**Tool:** Claude Code via CodemIE
**Output:** `automation/ui/tests/test_visual_regression.py`

```
Add visual regression testing to the InvenTree Playwright suite using Playwright's built-in
screenshot comparison (expect(page).to_have_screenshot()).

Create automation/ui/tests/test_visual_regression.py with these tests:
1. VIS-P-001 test_part_detail_visual
2. VIS-P-002 test_part_create_form_visual
3. VIS-P-003 test_category_view_visual
4. VIS-P-004 test_part_attributes_all_visual

Rules:
- Mark all tests with @pytest.mark.visual
- Snapshots stored in automation/ui/snapshots/
- threshold=0.1 for pixel comparison
- full_page=True for list views, False for forms/detail
- Each test creates its own part via API in setup, deletes in teardown (idempotent)
```

---

### Prompt A5 — D3 Health Gate Integration

**Tool:** Claude Code via CodemIE
**Output:** `automation/ui/conftest.py`

```
Integrate the API health check into the Playwright UI test suite in automation/ui/conftest.py.

Add a session-scoped fixture api_health_gate with autouse=True:
- Pings /api/, /api/part/, /api/part/category/ with GET requests (5s timeout each)
- If any endpoint returns non-2xx/non-401 or connection refused:
  - Print which endpoints failed
  - Call pytest.skip("API health check failed — skipping UI tests to preserve CI resources")
- If all pass: print "[D3] API health OK — proceeding with UI tests"
- autouse=True so it runs before every test session automatically

Also add fixtures: authenticated_context (session), page (function, reuses session auth),
cleanup_parts, cleanup_categories (function-scoped API teardown), api_token, api_headers.
```

---

## AI Tools Summary

| Tool | Used For | Output |
|------|----------|--------|
| Claude Code via CodemIE | API test generation, fixture design, cleanup infrastructure | 165 pytest tests, conftest.py, 8 prompts |
| Claude Code via CodemIE | UI test generation, Page Object Model, visual regression | 50 UI manual tests, 5 UI test files, 6 page objects |
| Official Atlassian MCP | Jira story access via natural language | Authenticated MCP connection to jiraeu.epam.com |
| Jira REST API v2 (via curl) | Full story extraction with wiki markup parsing | 44 stories → JSON + CSV |
| schemathesis | OpenAPI contract validation | Automated contract tests vs live /api/schema/ |
| responses library | Mock HTTP layer for D2 resilience | 5 mock fixtures, 10 mock tests |
