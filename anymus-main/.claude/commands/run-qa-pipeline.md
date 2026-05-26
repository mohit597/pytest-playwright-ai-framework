# ANYMUS — Full QA Pipeline Orchestrator

You are the ANYMUS AI QA Orchestrator. Your job is to run the complete shift-left QA pipeline for the InvenTree Parts module and report results.

Execute the following stages **in order**. Stop and report clearly if any critical stage fails.

---

## Stage 0 — Environment Check

Run this first to confirm InvenTree is reachable and the virtualenv is active:

```bash
cd /Users/sivasankaramalan_gunasekarasivam/CODEMIE/QATHON/ANYMUS
python scripts/run_pipeline.py --check-env --base-url http://inventree.localhost
```

---

## Stage 1 — D3: Pre-flight Health Check

```bash
cd /Users/sivasankaramalan_gunasekarasivam/CODEMIE/QATHON/ANYMUS
python scripts/health_check.py --base-url http://inventree.localhost
```

- If exit code is **1** (any endpoint DOWN): report which endpoints are down and **stop the pipeline**. Do not run tests against a broken server.
- If exit code is **0**: proceed to Stage 2.

---

## Stage 2 — OpenAPI Contract Tests (Schemathesis)

```bash
cd /Users/sivasankaramalan_gunasekarasivam/CODEMIE/QATHON/ANYMUS/automation/api
pytest tests/test_schema_contract.py -v --tb=short -q
```

These tests auto-generate cases from the live OpenAPI spec. Report pass/fail count.

---

## Stage 3 — API Test Suite (Full)

```bash
cd /Users/sivasankaramalan_gunasekarasivam/CODEMIE/QATHON/ANYMUS/automation/api
pytest tests/ -v --tb=short --html=reports/api-report.html --ignore=tests/test_part_mock.py --ignore=tests/test_schema_contract.py -q
```

Run all API tests except mock and contract. Report counts by mark (crud, validation, filtering, cleanup).

---

## Stage 4 — D2: Mock API Tests (Offline Mode)

```bash
cd /Users/sivasankaramalan_gunasekarasivam/CODEMIE/QATHON/ANYMUS/automation/api
MOCK_MODE=true pytest tests/test_part_mock.py -v --tb=short -q
```

These run with no live server (recorded fixtures only). Report pass/fail count.

---

## Stage 5 — UI Test Suite (Playwright)

```bash
cd /Users/sivasankaramalan_gunasekarasivam/CODEMIE/QATHON/ANYMUS/automation/ui
pytest tests/ -v --tb=short --html=reports/ui-report.html -q
```

Excludes visual regression (those need headed browser). Report pass/fail count.

---

## Stage 6 — D1: Visual Regression Tests

```bash
cd /Users/sivasankaramalan_gunasekarasivam/CODEMIE/QATHON/ANYMUS/automation/ui
pytest tests/test_visual_regression.py -v --headed --tb=short -q
```

Report any pixel-diff failures with screenshot paths.

---

## Final Report

After all stages complete, print a summary table:

```
╔══════════════════════════════════════════════════════════╗
║           ANYMUS QA Pipeline — Final Report              ║
╠═══════════════════════╦═════════╦════════╦══════════════╣
║ Stage                 ║ Tests   ║ Status ║ Report       ║
╠═══════════════════════╬═════════╬════════╬══════════════╣
║ D3 Health Check       ║ 6 EP    ║ ✓/✗   ║ health_report.json ║
║ Contract (Schemathesis)║ 14     ║ ✓/✗   ║ —            ║
║ API Suite             ║ 151+   ║ ✓/✗   ║ api-report.html    ║
║ D2 Mock Tests         ║ 10     ║ ✓/✗   ║ —            ║
║ UI Suite              ║ varies ║ ✓/✗   ║ ui-report.html     ║
║ D1 Visual Regression  ║ 4      ║ ✓/✗   ║ snapshots/   ║
╚═══════════════════════╩═════════╩════════╩══════════════╝
```

Open the HTML reports for the user:
- `automation/api/reports/api-report.html`
- `automation/ui/reports/ui-report.html`

If any stage failed, list the failing test IDs and suggest next steps.
