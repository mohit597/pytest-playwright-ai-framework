# GitHub Copilot Instructions — ANYMUS

You are assisting with **ANYMUS**, an AI-native Shift Left QA pipeline for the InvenTree Parts module

## Your Primary Role in This Project

GitHub Copilot owns **two specific areas** in this repo:

### 1. GitHub Actions CI/CD Workflows (`.github/workflows/`)
This is your strongest domain. Generate and complete:
- `api-tests.yml` — runs health check first, then full API test suite
- `ui-tests.yml` — gates on health check output before running Playwright tests

### 2. Inline Completions for Repetitive Patterns
- `@pytest.mark.parametrize` data arrays (boundary values, edge cases)
- `requirements.txt` dependency lists
- Fixture boilerplate following patterns already in `conftest.py`
- JSON mock fixture files in `automation/api/mocks/`

---

## GitHub Actions Patterns to Follow

### `api-tests.yml` — Required Structure
```yaml
name: API Tests

on:
  push:
    branches: [main, 'Mohit/api']
  pull_request:
    branches: [main]

jobs:
  health-check:
    runs-on: ubuntu-latest
    outputs:
      healthy: ${{ steps.check.outputs.healthy }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install requests tabulate colorama
      - id: check
        run: |
          python scripts/health_check.py --base-url ${{ env.INVENTREE_URL }}
          echo "healthy=true" >> $GITHUB_OUTPUT
        continue-on-error: true
        env:
          INVENTREE_URL: http://localhost:8000

  api-tests:
    needs: health-check
    if: needs.health-check.outputs.healthy == 'true'
    runs-on: ubuntu-latest
    services:
      inventree:
        image: inventree/inventree:latest
        ports: ['8000:8000']
        # ... env and health check config
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r automation/api/requirements.txt
      - run: pytest automation/api/tests/ -v --html=report.html
        env:
          INVENTREE_URL: http://localhost:8000
          INVENTREE_USER: admin
          INVENTREE_PASS: inventree
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: api-test-report
          path: report.html
```

### `ui-tests.yml` — Required Structure
```yaml
name: UI Tests

on:
  push:
    branches: [main, 'mohit/ui']
  pull_request:
    branches: [main]

jobs:
  health-gate:
    # Same health check step as api-tests.yml
    # UI tests do NOT run if this fails — saves CI minutes

  ui-tests:
    needs: health-gate
    if: needs.health-gate.outputs.healthy == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r automation/ui/requirements.txt
      - run: playwright install --with-deps chromium
      - run: pytest automation/ui/tests/ -v
        env:
          INVENTREE_URL: http://localhost:8000
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ui-test-screenshots
          path: automation/ui/snapshots/
```

---

## Project Conventions (Always Follow)

- **Python version**: 3.11
- **No hardcoded credentials** — always use `${{ secrets.INVENTREE_USER }}` or env vars
- **Test reports** always uploaded as artifacts with `actions/upload-artifact@v4`
- **Health check always runs first** — UI tests are gated on its output
- **Mock mode**: `MOCK_MODE=true` can run API tests without InvenTree service

## What NOT to generate
- Do not touch `automation/ui/pages/` — that is Page Object Model code, not your domain
- Do not generate pytest test logic — that belongs to Cursor
- Do not modify `CLAUDE.md` or `Plan.md`
