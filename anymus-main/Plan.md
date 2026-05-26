# QAHub AI Hackathon 2026 — ANYMUS Project Plan

> **Deadline**: April 14, 2026 — 19:00 UTC+5
> **AUT**: InvenTree Parts Module — https://demo.inventree.org
> **Theme**: Shift Left Testing via AI-Agentic Workflow

---

## Key Differentiators (What Makes ANYMUS Stand Out)

These three features are the competitive edge. Every jury criterion — Originality, Technology, Scalability — is addressed here.

### D1 — Image Recognition for Visual Regression
Playwright's built-in `expect(page).toHaveScreenshot()` captures pixel-perfect baselines of critical Part pages (detail view, form states, category hierarchy). On subsequent runs, any visual drift fails the test. This goes beyond DOM assertions — it catches CSS regressions, layout shifts, and rendering issues that selector-based tests miss entirely.
- Baseline screenshots stored in `automation/ui/snapshots/`
- Critical pages: Part Detail, Part Create form, Category view, Cross-functional flow final state

### D2 — Mock API for Resilient Testing
When InvenTree is unreachable (CI flakiness, downstream outage, offline dev), testing must not stop. Using the `responses` library, API tests switch to recorded mock fixtures (`automation/api/mocks/*.json`) via `MOCK_MODE=true`. This enables:
- Full API test suite execution without a live server
- Offline development and fast feedback loops
- Isolation of test logic from infrastructure availability

### D3 — Pre-flight Health Check / Meta Testing
Before any test suite runs, a health check script pings all InvenTree Part API endpoints and reports their status. This acts as a pre-flight gate:
- For **API tests**: skip suite if core endpoints are down, log which are unavailable
- For **UI tests**: gate Playwright execution on API health — if API is down, skip UI tests immediately instead of burning CI/CD time on guaranteed failures
- Runs as a standalone script and as the first step in GitHub Actions

---

## Repository Structure

```
anymus/
├── README.md                          # Project overview + quick start
├── Plan.md                            # This file
├── CLAUDE.md                          # AI agent instructions + selectors guide
├── AGENTS.md                          # QA Orchestration agent operating manual
├── SHIFT_LEFT_STRATEGY.md             # Shift Left narrative and approach
├── ADLC_ALIGNMENT.md                  # EPAM ADLC framework alignment
├── anymus-demo-slides.html            # Hackathon presentation slides
├── dashboard/
│   └── index.html                     # Live QA results dashboard UI
├── scripts/
│   ├── health_check.py                # D3 — pre-flight API health check
│   ├── run_pipeline.py                # Full QA pipeline orchestration
│   └── serve_dashboard.py             # Dashboard HTTP server
├── agents/
│   ├── prompts.md                     # All prompts used with Claude Code
│   ├── system-instructions.md         # Agent session bootstrap guide
│   ├── qa_orchestrator_agent.py       # Agentic QA orchestrator
│   └── conversation-logs/             # Run history and AI narrative logs
├── test-cases/
│   ├── api-test-cases.json            # Schema-derived API test cases
│   └── ui-test-cases.json             # Requirement-traced UI test cases
├── automation/
│   ├── ui/                            # Playwright (Python) UI automation
│   │   ├── pages/                     # Page Object Model
│   │   ├── tests/                     # Test files incl. visual regression (D1)
│   │   └── snapshots/                 # D1 — baseline screenshots
│   └── api/                           # pytest + requests API automation
│       ├── mocks/                     # D2 — fixture JSONs for mock mode
│       └── tests/                     # Test files incl. health + mock tests
├── docker/
│   ├── Dockerfile.tests               # Test runner container
│   ├── Dockerfile.dashboard           # Dashboard container
│   └── entrypoint.sh                  # Container entrypoint
├── docker-compose.tests.yml           # Test + dashboard services overlay
└── .github/
    └── workflows/
        ├── api-tests.yml
        └── ui-tests.yml
```

---

## Phase 1 — Requirements + Test Case Generation

Use Claude Code to ingest InvenTree documentation and generate test cases:

**API Test Cases** — ingest `https://docs.inventree.org/en/stable/api/schema/part/`
- Coverage: CRUD, filtering/pagination, field validation, relational integrity, edge cases
- Output: `test-cases/api-test-cases.json`

**UI Test Cases** — ingest Parts documentation sub-pages
- Coverage: Part creation, all detail tabs, attributes, categories, revisions, boundary cases
- Output: `test-cases/ui-test-cases.json`

---

## Phase 2 — API Automation

Stack: `pytest` + `requests` + `schemathesis`

Test files in `automation/api/tests/`:
- `test_meta_health.py` — D3 pre-flight health check (runs first)
- `test_part_crud.py` — full CRUD with business rule assertions
- `test_part_filtering.py` — search, filter, pagination with `@pytest.mark.parametrize`
- `test_part_validation.py` — field validation, required fields, max lengths
- `test_part_categories.py` — category CRUD and hierarchy
- `test_schema_contract.py` — schemathesis OpenAPI contract tests
- `test_part_mock.py` — D2 mock mode tests against JSON fixtures
- `test_part_templates.py` — template/variant tests

---

## Phase 3 — UI Automation

Stack: `Playwright` (Python) + Page Object Model

Page objects in `automation/ui/pages/`:
- `base_page.py` — common actions
- `login_page.py` — login flow (allauth headless API)
- `parts_list_page.py` — list, search, navigate
- `part_detail_page.py` — all tabs, attributes, edit
- `part_create_page.py` — creation form
- `category_page.py` — hierarchy navigation

Test files in `automation/ui/tests/`:
- `test_part_crud.py` — create → verify → edit → delete
- `test_part_attributes.py` — toggle attributes, verify UI
- `test_part_categories.py` — category hierarchy
- `test_part_parameters.py` — parameter templates and values
- `test_cross_functional.py` — end-to-end flow
- `test_visual_regression.py` — D1 screenshot baseline comparison

---

## Phase 4 — Agentic Orchestration

`scripts/run_pipeline.py` orchestrates the full pipeline in 7 stages:

| Stage | Name | What runs |
|---|---|---|
| 0 | Environment check | Verify InvenTree reachable |
| 1 | D3 Health gate | `test_meta_health.py` — skip if API down |
| 2 | Contract tests | schemathesis OpenAPI validation |
| 3 | API suite | All API + mock tests |
| 4 | D2 Mock diagnostic | Mock mode smoke test |
| 5 | UI suite | Playwright functional tests |
| 6 | Visual regression | Screenshot baseline comparison (D1) |

`agents/qa_orchestrator_agent.py` wraps the pipeline with AI-driven decision logic — if live tests fail, it automatically runs mock diagnostics to distinguish framework failures from infrastructure failures.

---

## Running the Full Pipeline

```bash
# Local — full pipeline
python scripts/run_pipeline.py --base-url http://inventree.localhost

# Local — API only (no browser needed)
python scripts/run_pipeline.py --api-only --base-url http://inventree.localhost

# Docker — full pipeline + dashboard
docker compose -f docker-compose.yml -f docker-compose.tests.yml up --build

# D2 — mock mode (no InvenTree needed)
cd automation/api && MOCK_MODE=true pytest tests/test_part_mock.py -v

# D3 — standalone health check
python scripts/health_check.py --base-url http://inventree.localhost
```

---

## Environment Variables

```bash
INVENTREE_URL=http://inventree.localhost  # browser navigation (Playwright)
INVENTREE_API_URL=http://localhost:8000   # direct API calls (bypass Caddy proxy)
INVENTREE_USER=admin
INVENTREE_PASS=inventree
MOCK_MODE=false          # true = run API tests against mock fixtures
UPDATE_SNAPSHOTS=false   # true = regenerate visual regression baselines
```

---

## Shift Left Narrative

The full ANYMUS Shift Left loop:

```
1. REQUIREMENTS  →  AI ingests live docs → test cases generated before code is touched
2. CONTRACT      →  schemathesis auto-validates OpenAPI spec → catch API breaks early
3. RESILIENCE    →  Mock API mode → testing continues even when infra is unavailable (D2)
4. GATE          →  Health check pre-flight → UI tests won't run on a broken backend (D3)
5. VISUAL        →  Screenshot baselines → catch visual regressions DOM tests miss (D1)
6. CI/CD         →  Every push runs the full pipeline → quality is continuous
```

This is not just test automation. It's a **quality-first engineering system**.

---

## Test IDs

- UI tests: `UI-P-001`, `UI-P-002` ... (P = Parts)
- API tests: `API-P-001`, `API-P-002` ...
- Health check: `HC-001`, `HC-002` ...
- Visual tests: `VIS-P-001`, `VIS-P-002` ...
- Mock tests: `MOCK-P-001`, `MOCK-P-002` ...
