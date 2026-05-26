# ANYMUS — Agent System Instructions

> This file documents the system-level instructions and configuration used to guide Claude Code
> throughout the hackathon. These instructions were active in every session.

---

## Project Context Given to Agent

The agent was given the following context at the start of every session via `CLAUDE.md`:

- **Project name:** ANYMUS — AI-Native Shift Left QA Pipeline
- **Application Under Test:** InvenTree Parts Module (v1.3.0)
- **Deadline:** April 14, 2026 — 19:00 UTC+5

---

## Session Bootstrap Instructions

At the start of each work session, the following prompt was used to orient Claude Code:

```
Read CLAUDE.md and Plan.md in the repo root.
My current task is [describe task from Plan.md].
Help me implement this following the conventions in CLAUDE.md.
```

---

## Constraints Given to the Agent

1. **Scope**: Only generate code/tests for the InvenTree Parts module
2. **No sleep()**: Use Playwright explicit waits or pytest fixtures — never `time.sleep()`
3. **No hardcoded credentials**: Always use environment variables
4. **POM enforced**: No raw Playwright selectors outside of `pages/` directory
5. **Idempotent tests**: Every test must clean up after itself via fixtures
6. **Shift Left first**: Every test case must reference a business rule from InvenTree docs

---

## Tool Configuration

| Tool | Version / Config |
|---|---|
| Claude Code | via CodemIE |
| AI Model | claude-sonnet-4-6 |
| Working directory | repo root |
| CLAUDE.md | auto-loaded on session start |
| Branch | `AgenticWorkflow` (active) · `main` (submission) |

---

## Three Differentiators

- **D1 — Image Recognition:** Playwright screenshot comparison (`expect(page).to_have_screenshot()`)
- **D2 — Mock API Mode:** `responses` library, `MOCK_MODE=true`
- **D3 — Pre-flight Health Check:** `api_health_gate` autouse session fixture in `conftest.py`

---

## Agentic QA Orchestrator (Phase 2)

The `agents/qa_orchestrator_agent.py` introduces a Claude-powered autonomous orchestrator that
owns the full AUT lifecycle beyond what a static script can do.

### System Prompt for the Orchestrator Agent

```
You are the ANYMUS QA Orchestration Agent — an autonomous AI that owns the full lifecycle of an
InvenTree QA run.

Your responsibilities:
1. Determine whether the Application Under Test (InvenTree) is already running.
2. If not running, start it with spin_up_aut.
3. Wait for all API endpoints to become healthy with wait_for_healthy.
4. Run the QA pipeline with run_pipeline.
5. If Stage 3 (API Suite) fails unexpectedly, call run_pipeline again with stage=4 and
   mock_mode=true to diagnose whether the test framework is healthy.
6. Generate and serve the Allure report with generate_and_serve_report.
7. Save a structured run log with save_run_report.
8. Print a final summary to the user.
```

### Tool Set

| Tool | Purpose | Returns |
|------|---------|---------|
| `check_aut_running` | Ping `/api/` to see if InvenTree is live | `{running, base_url, detail}` |
| `spin_up_aut` | `docker compose up -d` | `{success, elapsed, output}` |
| `wait_for_healthy` | Poll `health_check.py` until 6/6 up | `{healthy, waited_seconds, endpoints_up}` |
| `run_pipeline` | Run `run_pipeline.py`, parse summary | `{all_pass, stages, duration, output}` |
| `generate_and_serve_report` | `allure generate` + `allure serve` | `{url, generated, serve_pid}` |
| `read_run_history` | Analyze last N run logs for systemic failures | `{pattern, systemic_failures, pass_rate}` |
| `save_run_report` | Write `run-*.json` + `run-*.md` | `{saved_json, saved_md}` |
| `tear_down_aut` | `docker compose down` | `{success, elapsed, output}` |
| `create_jira_ticket` | POST Jira REST API v2, tag [ANYMUS] | `{created, ticket_key, url}` |

### Agentic Decision Rules

- If AUT is already running → skip `spin_up_aut` and `wait_for_healthy`
- If `wait_for_healthy` times out → save failure log and halt
- If Stage 3 fails → run Stage 4 mock as diagnostic before saving report
- Always call `save_run_report` last, even on failure
- History shows stage failing ≥60% of last 5 runs → classify as systemic

### CLI Usage

```bash
# Full lifecycle from scratch
python agents/qa_orchestrator_agent.py

# API only (no UI/visual)
python agents/qa_orchestrator_agent.py --mode api

# Mock mode only (no live server required)
python agents/qa_orchestrator_agent.py --mode mock

# Skip AUT spin-up (InvenTree already running)
python agents/qa_orchestrator_agent.py --skip-spinup

# Tear down InvenTree after run
python agents/qa_orchestrator_agent.py --teardown
```

### Run Logs

Each run produces two files in `agents/conversation-logs/`:
- `run-{ISO_TIMESTAMP}.json` — machine-readable structured results
- `run-{ISO_TIMESTAMP}.md` — human-readable narrative for review

Both are gitignored (see `.gitignore`) — only `.gitkeep` is tracked.

---

## InvenTree v1.3.0 — Key Agentic Learnings

These were discovered through live exploration of the running InvenTree instance.
They are documented here so future agents can orient themselves quickly without repeating
the exploration cycle.

### What Changed in v1.3.0 vs Older Versions

| Aspect | Old (Django templates) | v1.3.0 (React SPA) |
|---|---|---|
| Login selector | `#id_username` | `[aria-label='login-username']` |
| Form IDs | `#id_name`, `#id_description` | `[aria-label='text-field-name']` etc. |
| Tab navigation | Click tab element | Navigate via URL `/web/part/{pk}/details/{tab}` |
| Part creation URL | `/part/new/` | No such route — use modal at `/web/part/category/index/parts` |
| Submit buttons | `button[type='submit']` | `button:has-text('Submit')` (type is "button") |
| API token endpoint | `POST /api/user/token/` | `GET /api/user/token/` (v1.3.0+) |

### Selector Discovery Approach

When a selector stops working after an upgrade:

1. Run `py automation/ui/discover_selectors.py` → outputs `discovered_selectors.json`
2. Look for `aria-label` attributes — these are stable across React re-renders
3. Mantine dynamic IDs (e.g., `mantine-abc123-tab-stock`) change on every render — NEVER use them
4. Tab slugs in URLs are the most reliable tab navigation method

### Critical URL Patterns

The parts table (with the "add part" button) lives at:
```
/web/part/category/index/parts      ← NOT /web/part/category/index/details/parts
```

Subcategories tab (with "add category" button) lives at:
```
/web/part/category/index/subcategories
/web/part/category/{pk}/subcategories
```

### Critical API Behaviors

**Parts require deactivation before deletion:**
```python
requests.patch(f"{BASE_URL}/api/part/{pk}/", json={"active": False}, headers=headers)
requests.delete(f"{BASE_URL}/api/part/{pk}/", headers=headers)
```

**Part actions menu item aria-labels (no `-part` suffix):**
```
action-menu-part-actions-edit        # Edit Part
action-menu-part-actions-duplicate   # Duplicate Part
action-menu-part-actions-delete      # Delete Part — DISABLED for active parts
```
The Delete menu item has a `disabled` HTML attribute when the part is active. Deactivate first via
API PATCH `{"active": False}`, then reload the detail page before clicking Delete.

**Category delete modal has required fields:**
The "Delete Part Category" modal shows "Parts Action" and "Child Categories Action" dropdowns.
For an empty category (no parts, no children), clicking Delete directly works without filling them.

**Search without limit returns a flat list (not paginated dict):**
```python
GET /api/part/?search=foo       → [...]          # flat list
GET /api/part/?limit=50         → {"count": N, "results": [...]}
GET /api/part/?search=foo&limit=50 → {"count": N, "results": [...]}  # always add limit=
```

### Prompts Used to Generate This Project

See [`prompts.md`](prompts.md) for the exact prompts used with Claude Code.

---

## Architecture Reference

InvenTree's Parts module key entities:

| Entity | API Endpoint | Notes |
|---|---|---|
| Part | `/api/part/` | Central entity; soft-deleted via `active=False` |
| PartCategory | `/api/part/category/` | Hierarchical tree (django-treebeard) |
| BomItem | `/api/bom/` | Assembly BOM lines |
| StockItem | `/api/stock/` | Physical instances of a Part |
| PartParameter | `/api/part/parameter/` | Key-value metadata on a Part |
| PartTestTemplate | `/api/part/test-template/` | Test definitions for testable parts |
| SupplierPart | `/api/company/part/` | Links Part to supplier with SKU |

Key business rules driving test cases:
- `(name, IPN, revision)` must be unique per part
- Parts with `assembly=True` show Bill of Materials tab
- Parts with `purchaseable=True` show Suppliers tab
- Parts with `is_template=True` show Variants tab
- Parts with `trackable=True` require serial numbers on stock items
- `active=False` required before DELETE (soft-delete pattern)
- Locked parts (`locked=True`) cannot be edited
