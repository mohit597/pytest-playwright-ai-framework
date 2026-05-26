import os
import requests
import pytest
from dotenv import load_dotenv
from playwright.sync_api import Page, Browser, BrowserContext

load_dotenv(override=True)  # override=True ensures .env PLAYWRIGHT_BROWSERS_PATH wins over IDE sandbox injection

BASE_URL = os.getenv("INVENTREE_URL", "http://inventree.localhost")
# API_BASE_URL bypasses the nginx proxy for token fetch and cleanup calls.
# Inside Docker, talk to the Django backend directly (port 8000).
API_BASE_URL = os.getenv("INVENTREE_API_URL", BASE_URL)
INVENTREE_USER = os.getenv("INVENTREE_USER", "admin")
INVENTREE_PASS = os.getenv("INVENTREE_PASS", "inventree")

# ---------------------------------------------------------------------------
# Docker DNS override — makes Chromium reach inventree.localhost inside Docker
# ---------------------------------------------------------------------------
# Chromium treats *.localhost as loopback (RFC 6761) so it can't connect to
# http://inventree.localhost when running inside a Docker container.
# --host-resolver-rules overrides DNS for that specific hostname, pointing it
# at the inventree-proxy container.  Cookies and CSRF Origin both remain
# "inventree.localhost" so Django's CSRF_TRUSTED_ORIGINS check passes.
@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    in_docker = API_BASE_URL.startswith("http://inventree-")
    if in_docker:
        return {
            **browser_type_launch_args,
            "args": ["--host-resolver-rules=MAP inventree.localhost inventree-proxy"],
        }
    return browser_type_launch_args

# D3 — all 6 endpoints must be healthy before UI tests run (matches health_check.py)
HEALTH_CHECK_ENDPOINTS = [
    "/api/",
    "/api/part/",
    "/api/part/category/",
    "/api/part/category/tree/",
    "/api/part/category/parameters/",
    "/api/part/test-template/",
]


# ---------------------------------------------------------------------------
# D3 — Pre-flight API health gate (autouse=True → runs before every session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def api_health_gate():
    """D3: Skip all UI tests if critical API endpoints are unreachable."""
    failed = []
    for path in HEALTH_CHECK_ENDPOINTS:
        url = f"{API_BASE_URL}{path}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code not in (200, 401):
                failed.append(f"{path} → HTTP {resp.status_code}")
        except requests.exceptions.ConnectionError:
            failed.append(f"{path} → Connection refused")
        except requests.exceptions.Timeout:
            failed.append(f"{path} → Timeout")

    if failed:
        lines = "\n  ".join(failed)
        pytest.skip(
            f"API health check failed — skipping UI tests to preserve CI resources.\n"
            f"Failed endpoints:\n  {lines}"
        )
    else:
        print("\n[D3] API health OK — proceeding with UI tests")


# ---------------------------------------------------------------------------
# Auth fixture — logs in once per session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "base_url": BASE_URL}


@pytest.fixture(scope="session")
def authenticated_context(browser: Browser):
    """Create a browser context with an authenticated InvenTree session.

    InvenTree v1.3 uses django-allauth headless API (/api/auth/v1/auth/login).
    Direct form-fill + submit via Playwright does NOT trigger the React state
    correctly, so we call the allauth API via fetch() from within the browser
    context — this correctly carries the CSRF cookie and sets the session cookie.
    """
    context = browser.new_context(base_url=BASE_URL)
    page = context.new_page()

    # Navigate to /web so the browser gets the CSRF cookie from InvenTree
    page.goto(f"{BASE_URL}/web")
    page.wait_for_load_state("networkidle", timeout=30000)

    # Read the CSRF token from the cookies issued by InvenTree
    cookies = context.cookies()
    csrf = next((c["value"] for c in cookies if c["name"] == "csrftoken"), "")
    if not csrf:
        raise RuntimeError(
            f"No csrftoken cookie from {BASE_URL}/web — is InvenTree reachable?"
        )

    # POST to the allauth headless login endpoint from within the browser context
    # so the session cookie is set in this browser context automatically.
    result = page.evaluate(
        """async (args) => {
            const resp = await fetch("/api/auth/v1/auth/login", {
                method: "POST",
                credentials: "include",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": args.csrf
                },
                body: JSON.stringify({username: args.username, password: args.password})
            });
            return {status: resp.status};
        }""",
        {"csrf": csrf, "username": INVENTREE_USER, "password": INVENTREE_PASS},
    )

    if result["status"] != 200:
        raise RuntimeError(
            f"Allauth login API returned HTTP {result['status']} for user '{INVENTREE_USER}'. "
            "Check INVENTREE_USER and INVENTREE_PASS environment variables."
        )

    # Navigate to the main app now that the session is established
    page.goto(f"{BASE_URL}/web")
    page.wait_for_load_state("networkidle", timeout=30000)

    if "/web/login" in page.url:
        raise RuntimeError(
            f"Still on login page after successful API login — session cookie may not have been set."
        )

    yield context
    context.close()


@pytest.fixture(scope="function")
def page(authenticated_context: BrowserContext) -> Page:
    """Provide a fresh page per test, reusing the authenticated session."""
    page = authenticated_context.new_page()
    yield page
    page.close()


# ---------------------------------------------------------------------------
# Part cleanup fixture — ensures tests are idempotent
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def cleanup_parts():
    """Track created part PKs and delete them via API after the test."""
    created_pks = []

    def register(pk: int):
        created_pks.append(pk)

    yield register

    token = _get_api_token()
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    for pk in created_pks:
        try:
            # InvenTree requires deactivating before deletion
            requests.patch(f"{API_BASE_URL}/api/part/{pk}/", json={"active": False}, headers=headers, timeout=5)
            requests.delete(f"{API_BASE_URL}/api/part/{pk}/", headers=headers, timeout=5)
        except Exception:
            pass


@pytest.fixture(scope="function")
def cleanup_categories():
    """Track created category PKs and delete them via API after the test."""
    created_pks = []

    def register(pk: int):
        created_pks.append(pk)

    yield register

    token = _get_api_token()
    headers = {"Authorization": f"Token {token}"}
    for pk in reversed(created_pks):
        try:
            requests.delete(f"{API_BASE_URL}/api/part/category/{pk}/", headers=headers, timeout=5)
        except Exception:
            pass


def _get_api_token() -> str:
    # InvenTree v1.x uses GET /api/user/token/ with Basic Auth.
    # Use API_BASE_URL (direct to Django) not BASE_URL (Caddy) — Caddy strips the response body.
    resp = requests.get(
        f"{API_BASE_URL}/api/user/token/",
        auth=(INVENTREE_USER, INVENTREE_PASS),
        timeout=5,
    )
    if resp.status_code == 200:
        return resp.json().get("token", "")
    # Fallback: try POST (older versions)
    resp = requests.post(
        f"{API_BASE_URL}/api/user/token/",
        auth=(INVENTREE_USER, INVENTREE_PASS),
        timeout=5,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"API token acquisition failed (POST fallback): HTTP {resp.status_code} — {resp.text[:200]} [URL: {API_BASE_URL}]")
    return resp.json().get("token", "")


# ---------------------------------------------------------------------------
# API helper for test setup (creating test data)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def api_token():
    return _get_api_token()


@pytest.fixture(scope="session")
def api_headers(api_token):
    return {"Authorization": f"Token {api_token}", "Content-Type": "application/json"}
