"""
ANYMUS — AI-Native QA Pipeline Orchestrator
============================================
Runs the full shift-left QA pipeline in order:
  Stage 0  Environment check
  Stage 1  D3 Pre-flight health check
  Stage 2  OpenAPI contract tests (schemathesis)
  Stage 3  Full API test suite
  Stage 4  D2 Mock API tests (offline)
  Stage 5  UI test suite (Playwright)
  Stage 6  D1 Visual regression tests

Usage:
    python scripts/run_pipeline.py                  # full pipeline
    python scripts/run_pipeline.py --api-only       # stages 1-4
    python scripts/run_pipeline.py --check-env      # env check only
    python scripts/run_pipeline.py --stage 3        # single stage
    python scripts/run_pipeline.py --base-url http://localhost:8000
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    GREEN  = Fore.GREEN + Style.BRIGHT
    RED    = Fore.RED + Style.BRIGHT
    YELLOW = Fore.YELLOW + Style.BRIGHT
    CYAN   = Fore.CYAN + Style.BRIGHT
    RESET  = Style.RESET_ALL
except ImportError:
    GREEN = RED = YELLOW = CYAN = RESET = ""

ROOT            = Path(__file__).parent.parent
API_DIR         = ROOT / "automation" / "api"
UI_DIR          = ROOT / "automation" / "ui"
REPORT_DIR_API  = API_DIR / "reports"
REPORT_DIR_UI   = UI_DIR / "reports"
ALLURE_RESULTS  = ROOT / "allure-results"
ALLURE_REPORT   = ROOT / "allure-report"

# Use venv binaries if available, otherwise fall back to PATH
_API_VENV = API_DIR / ".venv" / "bin"
_UI_VENV  = UI_DIR  / ".venv" / "bin"
API_PYTEST  = str(_API_VENV / "pytest")  if (_API_VENV / "pytest").exists()  else "pytest"
UI_PYTEST   = str(_UI_VENV  / "pytest")  if (_UI_VENV  / "pytest").exists()  else "pytest"
API_PYTHON  = str(_API_VENV / "python")  if (_API_VENV / "python").exists()  else sys.executable

# Detect allure-pytest — skip --alluredir if not installed (avoids unrecognized arg error)
_allure_check = subprocess.run(
    [API_PYTHON, "-c", "import allure_pytest"],
    capture_output=True,
)
ALLURE_PYTEST_AVAILABLE = _allure_check.returncode == 0

def _alluredir_flag() -> str:
    """Returns --alluredir flag if allure-pytest is installed, empty string otherwise."""
    if ALLURE_PYTEST_AVAILABLE:
        ALLURE_RESULTS.mkdir(parents=True, exist_ok=True)
        return f"--alluredir={ALLURE_RESULTS}"
    return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def header(text: str):
    bar = "═" * 60
    print(f"\n{CYAN}{bar}")
    print(f"  {text}")
    print(f"{bar}{RESET}")


def run(cmd: str, cwd: Path, env: dict = None) -> tuple[int, str]:
    """Run a shell command, stream output, return (exit_code, elapsed)."""
    merged_env = {**os.environ, **(env or {})}
    t0 = time.monotonic()
    result = subprocess.run(
        cmd, shell=True, cwd=str(cwd), env=merged_env
    )
    elapsed = f"{time.monotonic() - t0:.1f}s"
    return result.returncode, elapsed


def status_line(stage: str, label: str, code: int, elapsed: str):
    icon  = f"{GREEN}✓  PASS" if code == 0 else f"{RED}✗  FAIL"
    print(f"\n  {icon}{RESET}  {stage}: {label}  [{elapsed}]")


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

def check_env(base_url: str) -> int:
    header("Stage 0 — Environment Check")
    issues = []

    if not (API_DIR / "conftest.py").exists():
        issues.append(f"conftest.py not found at {API_DIR}")
    if not (ROOT / "scripts" / "health_check.py").exists():
        issues.append("scripts/health_check.py not found")

    # Check the /api/ endpoint which returns 200 without any redirect or login requirement
    _check_url = f"{base_url.rstrip('/')}/api/"
    _reached = False
    for _attempt in range(3):
        try:
            import urllib.request as _ur
            _resp = _ur.urlopen(_check_url, timeout=5)
            if _resp.status in (200, 401, 403):  # any non-5xx means the server is up
                _reached = True
                break
        except Exception as _exc:
            if _attempt < 2:
                import time as _time
                _time.sleep(2)
    if _reached:
        print(f"  {GREEN}✓{RESET}  InvenTree reachable at {base_url}")
    else:
        issues.append(f"InvenTree not reachable at {base_url}")

    if issues:
        for issue in issues:
            print(f"  {RED}✗{RESET}  {issue}")
        return 1

    print(f"  {GREEN}✓{RESET}  API directory found")
    print(f"  {GREEN}✓{RESET}  health_check.py found")
    return 0


def stage_health(base_url: str) -> int:
    header("Stage 1 — D3: Pre-flight Health Check")
    code, elapsed = run(
        f"{API_PYTHON} scripts/health_check.py --base-url {base_url}",
        cwd=ROOT,
    )
    status_line("D3 Health", "All InvenTree endpoints", code, elapsed)
    if code != 0:
        print(f"\n  {RED}Pipeline HALTED — server is not healthy.{RESET}")
        print(  "  Fix InvenTree before running tests.")
    return code


def _prepare_allure_history():
    """Copy previous report history into results dir so Allure shows trends."""
    ALLURE_RESULTS.mkdir(parents=True, exist_ok=True)
    prev_history = ALLURE_REPORT / "history"
    if prev_history.exists():
        dest = ALLURE_RESULTS / "history"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(prev_history, dest)
        print(f"  {GREEN}✓{RESET}  History copied — trend graphs will show previous runs")
    else:
        print(f"  {YELLOW}⚠{RESET}  No previous history — first run, trends start from here")


def generate_allure_report():
    header("Allure Report — Generating")
    code, elapsed = run(
        f"allure generate {ALLURE_RESULTS} --clean -o {ALLURE_REPORT}",
        cwd=ROOT,
    )
    if code == 0:
        print(f"  {GREEN}✓{RESET}  Report generated → {ALLURE_REPORT}/index.html")
        print(f"\n  Open with:  allure open {ALLURE_REPORT}")
        print(f"  Or serve:   allure serve {ALLURE_RESULTS}")
    else:
        print(f"  {YELLOW}⚠{RESET}  allure CLI not found. Install: brew install allure")
        print(f"  Results saved to: {ALLURE_RESULTS}")
        print(f"  Run manually:     allure serve {ALLURE_RESULTS}")
    return code


def stage_contract() -> int:
    header("Stage 2 — OpenAPI Contract Tests (Schemathesis)")
    code, elapsed = run(
        f"{API_PYTEST} tests/test_schema_contract.py -v --tb=short -q {_alluredir_flag()}",
        cwd=API_DIR,
    )
    status_line("Contract", "Schemathesis /api/part/* + /api/bom/* + /api/parameter/*", code, elapsed)
    return code


def stage_api() -> int:
    header("Stage 3 — Full API Test Suite")
    REPORT_DIR_API.mkdir(parents=True, exist_ok=True)
    code, elapsed = run(
        f"{API_PYTEST} tests/ -v --tb=short -q "
        f"--html=reports/api-report.html --self-contained-html "
        f"{_alluredir_flag()} "
        f"--ignore=tests/test_part_mock.py "
        f"--ignore=tests/test_schema_contract.py",
        cwd=API_DIR,
    )
    status_line("API Suite", "165 tests (crud/validation/filtering/cleanup)", code, elapsed)
    print(f"  HTML report → {REPORT_DIR_API / 'api-report.html'}")
    return code


def stage_mock() -> int:
    header("Stage 4 — D2: Mock API Tests (Offline Mode)")
    code, elapsed = run(
        f"{API_PYTEST} tests/test_part_mock.py -v --tb=short -q {_alluredir_flag()}",
        cwd=API_DIR,
        env={"MOCK_MODE": "true"},
    )
    status_line("D2 Mock", "10 tests — no live server needed", code, elapsed)
    return code


def stage_ui() -> int:
    header("Stage 5 — UI Test Suite (Playwright)")
    if not UI_DIR.exists():
        print(f"  {YELLOW}⚠  UI directory not found — skipping{RESET}")
        return 0
    REPORT_DIR_UI.mkdir(parents=True, exist_ok=True)
    code, elapsed = run(
        f"{UI_PYTEST} tests/ -v --tb=short -q "
        f"--html=reports/ui-report.html --self-contained-html "
        f"{_alluredir_flag()} "
        f"--ignore=tests/test_visual_regression.py",
        cwd=UI_DIR,
    )
    status_line("UI Suite", "Playwright functional tests", code, elapsed)
    print(f"  HTML report → {REPORT_DIR_UI / 'ui-report.html'}")
    return code


def stage_visual() -> int:
    header("Stage 6 — D1: Visual Regression Tests")
    vr_file = UI_DIR / "tests" / "test_visual_regression.py"
    if not vr_file.exists():
        print(f"  {YELLOW}⚠  test_visual_regression.py not found — skipping{RESET}")
        return 0
    code, elapsed = run(
        f"{UI_PYTEST} tests/test_visual_regression.py -v --tb=short -q {_alluredir_flag()}",
        cwd=UI_DIR,
    )
    status_line("D1 Visual", "4 screenshot baseline tests", code, elapsed)
    return code


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

STAGE_LABELS = {
    0: ("Env Check",        "—"),
    1: ("D3 Health Check",  "6 endpoints"),
    2: ("Contract Tests",   "14 schemathesis tests"),
    3: ("API Suite",        "165 tests"),
    4: ("D2 Mock Tests",    "10 tests (offline)"),
    5: ("UI Suite",         "Playwright"),
    6: ("D1 Visual",        "4 screenshot tests"),
}


def print_summary(results: dict):
    header("ANYMUS QA Pipeline — Final Summary")
    print(f"  Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    col_w = 28
    print(f"  {'Stage':<{col_w}} {'Tests':<18} Status")
    print(f"  {'─'*col_w} {'─'*18} ──────")

    all_pass = True
    for stage_num, code in sorted(results.items()):
        label, tests = STAGE_LABELS.get(stage_num, (f"Stage {stage_num}", "—"))
        if code is None:
            icon = f"{YELLOW}─  SKIP{RESET}"
        elif code == 0:
            icon = f"{GREEN}✓  PASS{RESET}"
        else:
            icon = f"{RED}✗  FAIL{RESET}"
            all_pass = False
        print(f"  {label:<{col_w}} {tests:<18} {icon}")

    print()
    if all_pass:
        print(f"  {GREEN}ALL SYSTEMS GREEN — Pipeline passed ✓{RESET}")
    else:
        failed = [STAGE_LABELS[s][0] for s, c in results.items() if c not in (0, None)]
        print(f"  {RED}Pipeline FAILED — fix: {', '.join(failed)}{RESET}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ANYMUS QA Pipeline Orchestrator")
    parser.add_argument("--base-url", default=os.getenv("INVENTREE_URL", "http://localhost:8000"))
    parser.add_argument("--api-only",   action="store_true", help="Stages 1–4 only (no UI)")
    parser.add_argument("--check-env",  action="store_true", help="Environment check only")
    parser.add_argument("--stage",      type=int,             help="Run a single stage (1–6)")
    args = parser.parse_args()

    results = {}

    if args.check_env:
        sys.exit(check_env(args.base_url))

    if args.stage:
        stage_fns = {
            1: lambda: stage_health(args.base_url),
            2: stage_contract,
            3: stage_api,
            4: stage_mock,
            5: stage_ui,
            6: stage_visual,
        }
        fn = stage_fns.get(args.stage)
        if not fn:
            print(f"Unknown stage {args.stage}. Choose 1–6.")
            sys.exit(1)
        sys.exit(fn())

    # Full pipeline
    print(f"\n{CYAN}{'═'*60}")
    print(  "  ANYMUS — AI-Native Shift Left QA Pipeline")
    print(  "  Orchestrated by Claude Code (CodemIE)")
    print(f"{'═'*60}{RESET}")
    print(f"  Target: {args.base_url}")
    print(f"  Mode:   {'API only' if args.api_only else 'Full (API + UI)'}")
    print(f"  Report: {ALLURE_RESULTS}")

    # Seed Allure history for trend graphs
    header("Allure — Preparing Results Directory")
    _prepare_allure_history()

    results[0] = check_env(args.base_url)
    if results[0] != 0:
        print_summary(results)
        sys.exit(1)

    results[1] = stage_health(args.base_url)
    if results[1] != 0:
        print_summary(results)
        sys.exit(1)

    results[2] = stage_contract()
    results[3] = stage_api()
    results[4] = stage_mock()

    if not args.api_only:
        results[5] = stage_ui()
        results[6] = stage_visual()

    # Generate unified Allure report
    generate_allure_report()

    print_summary(results)
    any_fail = any(c not in (0, None) for c in results.values())
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
