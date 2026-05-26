"""
agents/tools/docker_tools.py
----------------------------
Tools for managing the InvenTree AUT Docker lifecycle.
"""

import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def check_aut_running(base_url: str = "http://inventree.localhost") -> dict:
    """
    Check whether InvenTree is already running.

    Returns:
        {"running": bool, "base_url": str, "detail": str}
    """
    try:
        req = urllib.request.Request(
            f"{base_url}/api/",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
        if status in (200, 401, 403):
            return {
                "running": True,
                "base_url": base_url,
                "detail": f"GET /api/ returned HTTP {status}",
            }
        return {
            "running": False,
            "base_url": base_url,
            "detail": f"GET /api/ returned unexpected HTTP {status}",
        }
    except (urllib.error.URLError, OSError) as exc:
        return {
            "running": False,
            "base_url": base_url,
            "detail": f"Connection failed: {exc}",
        }


def spin_up_aut(compose_file: str = "docker-compose.yml") -> dict:
    """
    Run `docker compose up -d` using the given compose file.

    Returns:
        {"success": bool, "elapsed": str, "output": str}
    """
    compose_path = ROOT / compose_file
    t0 = time.monotonic()
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "up", "-d"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    elapsed = f"{time.monotonic() - t0:.1f}s"
    success = result.returncode == 0
    output = (result.stdout + result.stderr).strip()
    return {
        "success": success,
        "elapsed": elapsed,
        "output": output[:2000] if len(output) > 2000 else output,
        "returncode": result.returncode,
    }


def wait_for_healthy(
    base_url: str = "http://inventree.localhost",
    timeout_seconds: int = 180,
    poll_interval: int = 10,
) -> dict:
    """
    Poll scripts/health_check.py until all endpoints are healthy or timeout is reached.

    Returns:
        {"healthy": bool, "waited_seconds": int, "endpoints_up": int, "endpoints_total": int, "detail": str}
    """
    health_script = ROOT / "scripts" / "health_check.py"
    import sys
    python_bin = _find_python()

    t0 = time.monotonic()
    last_output = ""

    while True:
        elapsed = int(time.monotonic() - t0)
        result = subprocess.run(
            [python_bin, str(health_script), "--base-url", base_url],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        last_output = (result.stdout + result.stderr).strip()

        if result.returncode == 0:
            return {
                "healthy": True,
                "waited_seconds": elapsed,
                "endpoints_up": 6,
                "endpoints_total": 6,
                "detail": "All endpoints responded successfully",
            }

        if elapsed >= timeout_seconds:
            # Parse how many endpoints were up from the output
            up_count = last_output.count("UP")
            return {
                "healthy": False,
                "waited_seconds": elapsed,
                "endpoints_up": up_count,
                "endpoints_total": 6,
                "detail": f"Timed out after {timeout_seconds}s. Last output: {last_output[:500]}",
            }

        time.sleep(poll_interval)


def tear_down_aut(compose_file: str = "docker-compose.yml") -> dict:
    """
    Run `docker compose down` to stop the AUT stack.

    Returns:
        {"success": bool, "elapsed": str, "output": str}
    """
    compose_path = ROOT / compose_file
    t0 = time.monotonic()
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "down"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    elapsed = f"{time.monotonic() - t0:.1f}s"
    output = (result.stdout + result.stderr).strip()
    return {
        "success": result.returncode == 0,
        "elapsed": elapsed,
        "output": output[:2000] if len(output) > 2000 else output,
    }


def _find_python() -> str:
    """Find python binary — prefer API venv, fallback to system."""
    import sys
    api_venv_python = ROOT / "automation" / "api" / ".venv" / "bin" / "python"
    if api_venv_python.exists():
        return str(api_venv_python)
    return sys.executable
