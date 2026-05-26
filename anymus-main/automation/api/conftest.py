"""
ANYMUS — API Test Fixtures
All test files import from here. Do not define fixtures in individual test files.
"""
import json
import uuid
import pytest
import requests
from config.settings import BASE_URL, USERNAME, PASSWORD, MOCK_MODE, HEALTH_ENDPOINTS, HEALTHY_STATUS_CODES

try:
    import allure
    _ALLURE_AVAILABLE = True
except ImportError:
    _ALLURE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Allure — feature label map (file name → display name in report)
# ---------------------------------------------------------------------------
_FILE_FEATURE = {
    "test_part_crud":        "Part CRUD",
    "test_part_filtering":   "Filtering & Search",
    "test_part_validation":  "Field Validation",
    "test_part_categories":  "Categories",
    "test_part_parameters":  "Parameters",
    "test_part_templates":   "Templates & Variants",
    "test_part_revisions":   "Revisions",
    "test_part_bom":         "Bill of Materials",
    "test_part_attachments": "Attachments",
    "test_part_related":     "Related Parts",
    "test_part_notes":       "Notes",
    "test_part_mock":        "D2 Mock API",
    "test_schema_contract":  "Contract Tests",
    "test_meta_health":      "D3 Health Check",
    "test_cleanup":          "Cleanup & Idempotency",
}

_MARK_SEVERITY = {
    "validation": "critical",
    "crud":       "normal",
    "filtering":  "normal",
    "cleanup":    "minor",
    "health":     "blocker",
    "contract":   "critical",
    "mock":       "normal",
}


def _uid():
    """Short unique suffix so fixture-created resources never collide on the uniqueness constraint."""
    return uuid.uuid4().hex[:8]


def _delete_part(api_client, pk):
    """
    InvenTree requires parts to be deactivated before they can be deleted.
    This helper handles the two-step deactivate → delete safely.
    """
    base = api_client.base_url
    try:
        api_client.patch(f"{base}/api/part/{pk}/", json={"active": False})
        api_client.delete(f"{base}/api/part/{pk}/")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Session-scoped: auth token (fetched once per test run)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def auth_token(base_url):
    """
    Fetches an API token from InvenTree using Basic Auth.
    Endpoint: GET /api/user/token/  (InvenTree uses GET, not POST)
    In MOCK_MODE a synthetic token is returned so mock tests never touch the live server.
    """
    if MOCK_MODE:
        return "mock-token-anymus-testing"

    response = requests.get(
        f"{base_url}/api/user/token/",
        auth=(USERNAME, PASSWORD),
        timeout=10,
    )
    assert response.status_code == 200, (
        f"Failed to obtain auth token: HTTP {response.status_code}\n"
        f"Body: {response.text!r}\n"
        f"URL:  {base_url}/api/user/token/"
    )
    try:
        return response.json()["token"]
    except (ValueError, KeyError) as exc:
        raise RuntimeError(
            f"Token endpoint returned unexpected body (status={response.status_code}):\n"
            f"  {response.text!r}\n"
            f"Check that INVENTREE_URL={base_url!r} is reachable and credentials are correct."
        ) from exc


@pytest.fixture(scope="session")
def api_client(base_url, auth_token):
    """
    A requests.Session pre-configured with auth header and base URL.
    Usage: api_client.get("/api/part/") — prefix with base_url for full URL.
    """
    session = requests.Session()
    session.headers.update({"Authorization": f"Token {auth_token}"})
    session.base_url = base_url
    return session


# ---------------------------------------------------------------------------
# Function-scoped: part + category cleanup (keeps tests idempotent)
# ---------------------------------------------------------------------------

@pytest.fixture
def created_part(api_client):
    """
    Creates a minimal Part with a unique name and yields it.
    Deletes it after the test regardless of outcome.
    Tests that need a part should use this fixture — never create parts manually.
    """
    payload = {
        "name": f"ANYMUS Test Part {_uid()}",
        "description": "Created by ANYMUS fixture — safe to delete",
        "active": True,
        "purchaseable": True,
    }
    response = api_client.post(f"{api_client.base_url}/api/part/", json=payload)
    assert response.status_code == 201, f"Fixture failed to create part: {response.text}"
    part = response.json()
    yield part
    _delete_part(api_client, part["pk"])


@pytest.fixture
def created_category(api_client):
    """
    Creates a Part Category with a unique name and yields it. Deletes after the test.
    """
    payload = {
        "name": f"ANYMUS Test Category {_uid()}",
        "description": "Created by ANYMUS fixture — safe to delete",
    }
    response = api_client.post(f"{api_client.base_url}/api/part/category/", json=payload)
    assert response.status_code == 201, f"Fixture failed to create category: {response.text}"
    category = response.json()
    yield category
    api_client.delete(f"{api_client.base_url}/api/part/category/{category['pk']}/")


# ---------------------------------------------------------------------------
# D2 — Mock mode flag
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mock_mode():
    """Returns True when MOCK_MODE=true env var is set. Used to skip/select mock tests."""
    return MOCK_MODE


# ---------------------------------------------------------------------------
# D3 — Pre-flight health gate (session-scoped, auto-use)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def api_health_gate(base_url):
    """
    Pings all critical InvenTree endpoints before any test runs.
    If any endpoint is unreachable or returns 5xx, the entire test session is skipped.
    This prevents false failures and saves CI/CD time.
    """
    if MOCK_MODE:
        # In mock mode, we don't need the real server
        return

    failures = []
    for path in HEALTH_ENDPOINTS:
        try:
            r = requests.get(f"{base_url}{path}", timeout=5)
            if r.status_code not in HEALTHY_STATUS_CODES:
                failures.append(f"{path} → {r.status_code}")
        except requests.ConnectionError:
            failures.append(f"{path} → CONNECTION REFUSED")
        except requests.Timeout:
            failures.append(f"{path} → TIMEOUT")

    if failures:
        pytest.skip(
            f"D3 Health Gate: {len(failures)} endpoint(s) are DOWN — skipping test suite.\n"
            + "\n".join(f"  ✗ {f}" for f in failures)
            + "\nRun scripts/health_check.py for details."
        )


# ---------------------------------------------------------------------------
# Extended fixtures — templates, assemblies, parameters, inactive parts
# ---------------------------------------------------------------------------

@pytest.fixture
def created_template_part(api_client):
    """Part with is_template=True. Used by template/variant/revision tests."""
    r = api_client.post(
        f"{api_client.base_url}/api/part/",
        json={"name": f"ANYMUS Template Part {_uid()}", "is_template": True},
    )
    assert r.status_code == 201, f"Fixture failed to create template part: {r.text}"
    part = r.json()
    yield part
    _delete_part(api_client, part["pk"])


@pytest.fixture
def created_assembly_part(api_client):
    """Part with assembly=True. Used by BOM tests."""
    r = api_client.post(
        f"{api_client.base_url}/api/part/",
        json={"name": f"ANYMUS Assembly Part {_uid()}", "assembly": True},
    )
    assert r.status_code == 201, f"Fixture failed to create assembly part: {r.text}"
    part = r.json()
    yield part
    _delete_part(api_client, part["pk"])


@pytest.fixture
def created_component_part(api_client):
    """Regular part suitable as a BOM component."""
    r = api_client.post(
        f"{api_client.base_url}/api/part/",
        json={"name": f"ANYMUS Component Part {_uid()}", "component": True},
    )
    assert r.status_code == 201, f"Fixture failed to create component part: {r.text}"
    part = r.json()
    yield part
    _delete_part(api_client, part["pk"])


@pytest.fixture
def parameter_template(api_client):
    """A part parameter template (e.g. Voltage). Used by parameter tests."""
    r = api_client.post(
        f"{api_client.base_url}/api/parameter/template/",
        json={"name": f"ANYMUS Voltage {_uid()}", "units": "V"},
    )
    assert r.status_code == 201, f"Fixture failed to create parameter template: {r.text}"
    tmpl = r.json()
    yield tmpl
    api_client.delete(f"{api_client.base_url}/api/parameter/template/{tmpl['pk']}/")


@pytest.fixture
def inactive_part(api_client):
    """Part with active=False. Used by inactive-restriction tests."""
    r = api_client.post(
        f"{api_client.base_url}/api/part/",
        json={"name": f"ANYMUS Inactive Part {_uid()}", "active": False},
    )
    assert r.status_code == 201, f"Fixture failed to create inactive part: {r.text}"
    part = r.json()
    yield part
    _delete_part(api_client, part["pk"])


@pytest.fixture
def two_parts(api_client):
    """Two independent parts. Used by related-parts tests. Yields (part_a, part_b)."""
    uid = _uid()
    ra = api_client.post(f"{api_client.base_url}/api/part/", json={"name": f"ANYMUS Related A {uid}"})
    rb = api_client.post(f"{api_client.base_url}/api/part/", json={"name": f"ANYMUS Related B {uid}"})
    assert ra.status_code == 201 and rb.status_code == 201
    part_a, part_b = ra.json(), rb.json()
    yield part_a, part_b
    _delete_part(api_client, part_a["pk"])
    _delete_part(api_client, part_b["pk"])


@pytest.fixture
def created_bom_item(api_client, created_assembly_part, created_component_part):
    """A BOM item linking assembly→component. Used by BOM update/delete tests."""
    r = api_client.post(
        f"{api_client.base_url}/api/bom/",
        json={
            "part": created_assembly_part["pk"],
            "sub_part": created_component_part["pk"],
            "quantity": 1.0,
        },
    )
    assert r.status_code == 201, f"Fixture failed to create BOM item: {r.text}"
    item = r.json()
    yield item
    api_client.delete(f"{api_client.base_url}/api/bom/{item['pk']}/")


# ---------------------------------------------------------------------------
# Pre/post-suite cleanup — removes orphaned ANYMUS data from failed runs
# ---------------------------------------------------------------------------

def _delete_anymus_data(api_client):
    """
    Deletes all resources whose name contains 'ANYMUS' via the API.
    Respects referential integrity order:
      BOM items → related links → attachments → parameters → parts (revisions first)
      → parameter templates → categories
    Safe to call when server is down — all errors are silently swallowed.
    """
    base = api_client.base_url

    def _list(path, params=None):
        try:
            r = api_client.get(f"{base}{path}", params={**(params or {}), "limit": 500})
            if r.status_code != 200:
                return []
            data = r.json()
            return data.get("results", data) if isinstance(data, dict) else data
        except Exception:
            return []

    def _del(path):
        try:
            api_client.delete(f"{base}{path}")
        except Exception:
            pass

    # 1. Find all ANYMUS part PKs
    all_parts = _list("/api/part/", {"search": "ANYMUS"})
    anymus_pks = [p["pk"] for p in all_parts if "ANYMUS" in p.get("name", "")]

    # 2. BOM items where any ANYMUS part is the assembly
    for pk in anymus_pks:
        for item in _list("/api/bom/", {"part": pk}):
            _del(f"/api/bom/{item['pk']}/")

    # 3. Related-part links
    for pk in anymus_pks:
        for rel in _list("/api/part/related/", {"part": pk}):
            _del(f"/api/part/related/{rel['pk']}/")

    # 4. Attachments
    for pk in anymus_pks:
        for att in _list("/api/part/attachment/", {"part": pk}):
            _del(f"/api/part/attachment/{att['pk']}/")

    # 5. Part parameters (endpoint moved to /api/parameter/ in InvenTree v1.3)
    for pk in anymus_pks:
        for param in _list("/api/parameter/", {"part": pk}):
            _del(f"/api/parameter/{param['pk']}/")

    # 6. Delete parts — deactivate first, then delete (InvenTree requires active=False before DELETE)
    #    Non-templates (revisions / regular) before templates
    non_templates = [p for p in all_parts if "ANYMUS" in p.get("name", "") and not p.get("is_template")]
    templates = [p for p in all_parts if "ANYMUS" in p.get("name", "") and p.get("is_template")]
    for p in non_templates + templates:
        try:
            api_client.patch(f"{base}/api/part/{p['pk']}/", json={"active": False})
        except Exception:
            pass
        _del(f"/api/part/{p['pk']}/")

    # 7. Parameter templates (endpoint moved to /api/parameter/template/ in InvenTree v1.3)
    for tmpl in _list("/api/parameter/template/", {"search": "ANYMUS"}):
        if "ANYMUS" in tmpl.get("name", ""):
            _del(f"/api/parameter/template/{tmpl['pk']}/")

    # 8. Categories (leaf nodes before parents — reverse pk order is a safe heuristic)
    cats = [c for c in _list("/api/part/category/", {"search": "ANYMUS"}) if "ANYMUS" in c.get("name", "")]
    for c in sorted(cats, key=lambda x: x["pk"], reverse=True):
        _del(f"/api/part/category/{c['pk']}/")


@pytest.fixture
def delete_part(api_client):
    """
    Returns a helper callable `fn(pk)` that deactivates then deletes a part.
    Use in test files that create parts inline (not via created_part fixture).
    """
    def _fn(pk):
        _delete_part(api_client, pk)
    return _fn


@pytest.fixture(scope="session", autouse=True)
def pre_suite_cleanup(api_client):
    """
    Runs before the first test: wipes leftover ANYMUS data from previous failed runs.
    Runs after the last test: final sweep for any fixtures that failed to tear down.
    Skipped automatically in MOCK_MODE (no real server).
    """
    if MOCK_MODE:
        yield
        return

    _delete_anymus_data(api_client)   # pre-suite
    yield
    _delete_anymus_data(api_client)   # post-suite


# ---------------------------------------------------------------------------
# Allure — auto-labelling and HTTP request/response capture
# Zero changes needed in individual test files.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _allure_labels(request):
    """
    Automatically applies Allure feature/story/severity labels to every test
    based on the test file name and pytest marks.
    Works silently if allure-pytest is not installed.
    """
    if not _ALLURE_AVAILABLE:
        yield
        return

    # Feature from file name
    stem = request.fspath.purebasename
    feature = _FILE_FEATURE.get(stem, "Other")
    allure.dynamic.feature(feature)

    # Story from test class name (strip Test prefix)
    cls = request.cls
    if cls:
        story = cls.__name__.replace("Test", "").replace("_", " ").strip()
        if story:
            allure.dynamic.story(story)

    # Severity from pytest mark
    for mark_name, severity in _MARK_SEVERITY.items():
        if request.node.get_closest_marker(mark_name):
            allure.dynamic.severity(severity)
            break

    # Tag from docstring (first line becomes Allure description)
    doc = request.node.obj.__doc__
    if doc:
        allure.dynamic.description(doc.strip())

    yield


@pytest.fixture(autouse=True)
def _allure_api_capture(request, api_client):
    """
    Hooks into the requests.Session to capture every HTTP request/response
    made during the test and attaches it to the Allure report.
    Skipped in MOCK_MODE (mock tests use responses library, not real HTTP).
    """
    if not _ALLURE_AVAILABLE or MOCK_MODE:
        yield
        return

    captured = []

    def _on_response(resp, *args, **kwargs):
        captured.append(resp)

    api_client.hooks["response"].append(_on_response)
    yield
    api_client.hooks["response"].remove(_on_response)

    for resp in captured:
        req = resp.request
        try:
            req_body = json.loads(req.body) if req.body else None
            req_body_str = json.dumps(req_body, indent=2) if req_body else "(no body)"
        except Exception:
            req_body_str = str(req.body or "(no body)")

        try:
            resp_body_str = json.dumps(resp.json(), indent=2)
        except Exception:
            resp_body_str = resp.text[:1000] if resp.text else "(no body)"

        label = f"{req.method} {req.path_url.split('?')[0].rstrip('/')}"
        allure.attach(
            f"━━ REQUEST ━━\n{req.method} {req.url}\n\nBody:\n{req_body_str}"
            f"\n\n━━ RESPONSE ━━\nStatus: {resp.status_code}\n\n{resp_body_str}",
            name=label,
            attachment_type=allure.attachment_type.TEXT,
        )
