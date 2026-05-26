# ANYMUS — AI-Native Shift Left QA Pipeline

> **QAHub AI Hackathon 2026**

**ANYMUS** (**A**I-**N**ative **Y**ield of **M**odern **U**nified **S**hift-left) is an end-to-end quality engineering pipeline built entirely through agentic AI collaboration using Claude Code and CodemIE.

The central thesis: *testing should begin the moment requirements are written, not after development ends.*

Built following the **[EPAM Agentic Development Lifecycle (ADLC)](ADLC_ALIGNMENT.md)** — see the full framework alignment, agentic maturity assessment, and roadmap in [`ADLC_ALIGNMENT.md`](ADLC_ALIGNMENT.md).

---

## Key Differentiators

| # | Feature | What it does |
|---|---|---|
| D1 | **Image Recognition** | Playwright visual regression — pixel-perfect baselines for critical Part pages |
| D2 | **Mock API Mode** | `MOCK_MODE=true` runs full API suite against fixtures when InvenTree is unreachable |
| D3 | **Pre-flight Health Check** | Pings all API endpoints before any test runs — gates UI tests to save CI resources |
| D4 | **ADLC Alignment** | Built following the EPAM Agentic Development Lifecycle — 7/8 maturity indicators complete; see [`ADLC_ALIGNMENT.md`](ADLC_ALIGNMENT.md) |

---

## Application Under Test

**InvenTree** — open-source inventory management system, Parts module only.

| Resource | URL |
|---|---|
| Local instance | `http://localhost:8000` |
| Demo | https://demo.inventree.org |
| Parts docs | https://docs.inventree.org/en/stable/part/ |
| API schema | https://docs.inventree.org/en/stable/api/schema/part/ |

---

## Quick Start

### 1. Run InvenTree locally (Docker)
```bash
git clone https://github.com/inventree/InvenTree
cd InvenTree
docker compose up -d
# Wait ~60s for startup
curl http://localhost:8000/api/  # should return 200
```

### 2. Run pre-flight health check
```bash
pip install requests tabulate
python scripts/health_check.py --base-url http://localhost:8000
```

### 3. Run API tests
```bash
cd automation/api
pip install -r requirements.txt
pytest tests/ -v --html=report.html
```

Run in mock mode (no InvenTree needed):
```bash
MOCK_MODE=true pytest tests/test_part_mock.py -v
```

### 4. Run UI tests
```bash
cd automation/ui
pip install -r requirements.txt
playwright install chromium
pytest tests/ -v --headed
```

Run visual regression tests only:
```bash
pytest tests/test_visual_regression.py -v --headed
```

Update visual baselines:
```bash
UPDATE_SNAPSHOTS=true pytest tests/test_visual_regression.py --headed
```

---

## Environment Variables

```bash
INVENTREE_URL=http://localhost:8000
INVENTREE_USER=admin
INVENTREE_PASS=inventree
MOCK_MODE=false          # true = run API tests against mock fixtures
UPDATE_SNAPSHOTS=false   # true = regenerate visual regression baselines
```

Copy `.env.example` to `.env` and fill in your values.

---

## Repository Structure

```
anymus/
├── README.md
├── Plan.md                        # Project execution plan
├── CLAUDE.md                      # Claude Code / CodemIE instructions
├── SHIFT_LEFT_STRATEGY.md         # Shift Left narrative and approach
├── scripts/
│   └── health_check.py            # D3 — pre-flight API health check
├── agents/
│   ├── prompts.md                 # All prompts used with Claude Code
│   └── system-instructions.md    # Agent configuration
├── test-cases/
│   ├── ui-manual-tests.md         # Phase 1 — requirement-traced UI tests
│   └── api-manual-tests.md        # Phase 2 — schema-derived API tests
├── automation/
│   ├── ui/                        # Playwright (Python) UI automation
│   │   ├── pages/                 # Page Object Model
│   │   ├── tests/                 # Test files incl. visual regression (D1)
│   │   └── snapshots/             # D1 — baseline screenshots
│   └── api/                       # pytest + requests API automation
│       ├── mocks/                 # D2 — fixture JSONs for mock mode
│       └── tests/                 # Test files incl. health + mock tests
└── .github/
    └── workflows/
        ├── api-tests.yml
        └── ui-tests.yml
```

---

## Shift Left Pipeline

```
Requirements ──► AI generates test cases ──► API Contract validated
      │                                              │
      └──────────── D3 Health Check ◄───────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        API Tests                 UI Tests
     (+ D2 Mock mode)         (+ D1 Visual regression)
              │                       │
              └───────────┬───────────┘
                          ▼
                    CI/CD Pipeline
```

---

## Tech Stack

| Layer | Stack |
|---|---|
| API Automation | Python, pytest, requests, schemathesis, responses |
| UI Automation | Python, Playwright, pytest-playwright, Pillow |
| CI/CD | GitHub Actions |
| AI Tools | Claude Code, CodemIE |
| AUT | InvenTree (Docker) |

---

## Built With

ANYMUS was built end-to-end through agentic AI collaboration using **Claude Code** via **CodemIE**.
See [`agents/prompts.md`](agents/prompts.md) for the full prompt history and [`ADLC_ALIGNMENT.md`](ADLC_ALIGNMENT.md) for the framework alignment.
