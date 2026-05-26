#!/usr/bin/env python3
"""
ANYMUS Results Dashboard
========================
Serves a live QA run dashboard on http://localhost:9090.
Reads agents/conversation-logs/run-*.json automatically — no config needed.

Usage:
    python scripts/serve_dashboard.py              # port 9090
    python scripts/serve_dashboard.py --port 8080
    python scripts/serve_dashboard.py --open       # auto-open browser

In Docker: launched by anymus-dashboard service in docker-compose.tests.yml.
Volume mount provides live access to run logs as tests execute.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent.parent
LOGS_DIR = ROOT / "agents" / "conversation-logs"
DASHBOARD_DIR = ROOT / "dashboard"

STAGE_LABELS = {
    "0": "Env Check",
    "1": "D3 Health Check",
    "2": "Contract Tests",
    "3": "API Suite",
    "4": "D2 Mock Tests",
    "5": "UI Suite",
    "6": "D1 Visual",
}


def load_runs(last_n: int = 10) -> list:
    """Load the most recent N run JSON logs, newest first."""
    if not LOGS_DIR.exists():
        return []
    files = sorted(LOGS_DIR.glob("run-*.json"), reverse=True)[:last_n]
    runs = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            data["_file"] = f.name
            runs.append(data)
        except Exception:
            continue
    return runs


def build_pulse_context(latest: dict, runs: list) -> str:
    """Build a pre-formatted context block for pasting into Cursor / Claude Code."""
    stage_lines = []
    for num, label in STAGE_LABELS.items():
        code = (latest.get("stages") or {}).get(num)
        if code is None:
            status = "SKIP  (not executed)"
        elif code == 0:
            status = "PASS ✓"
        else:
            status = f"FAIL ✗  (exit code {code})"
        stage_lines.append(f"  Stage {num}  {label:<22} {status}")

    overall = "ALL PASS ✓" if latest.get("all_pass") else "FAILED ✗"
    run_at = latest.get("run_at", "unknown")
    duration = latest.get("duration", "—")
    allure_url = latest.get("allure_url") or "not available"
    summary = latest.get("summary") or "no summary recorded"

    pass_count = sum(1 for r in runs[:5] if r.get("all_pass"))
    trend_text = (
        f"Last {min(5, len(runs))} runs: {pass_count} passed, "
        f"{min(5, len(runs)) - pass_count} failed"
    )

    return (
        f"=== ANYMUS QA Run Report ===\n"
        f"Run at:   {run_at}\n"
        f"Result:   {overall}\n"
        f"Duration: {duration}\n"
        f"Trend:    {trend_text}\n"
        f"\nStage Breakdown:\n" + "\n".join(stage_lines) +
        f"\n\nNarrative:\n{summary}"
        f"\n\nAllure Report: {allure_url}"
        f"\n\n---\n"
        f"Please analyse this QA run and give me the pulse:\n"
        f"1. What failed and why (root cause hypothesis)?\n"
        f"2. Is this a new regression or a known pattern?\n"
        f"3. What is the recommended next action?\n"
    )


def build_dashboard_data() -> dict:
    runs = load_runs(10)

    if not runs:
        return {
            "runs": [],
            "latest": None,
            "stage_labels": STAGE_LABELS,
            "trend": [],
            "pulse_context": (
                "No runs found yet.\n\n"
                "Run the pipeline first:\n"
                "  python scripts/run_pipeline.py --api-only\n\n"
                "Then refresh this page."
            ),
        }

    latest = runs[0]

    # Trend: last 5, oldest → newest (left → right in the UI)
    trend = [
        {
            "run_at": r.get("run_at", ""),
            "all_pass": r.get("all_pass", False),
            "duration": r.get("duration", "—"),
            "file": r.get("_file", ""),
        }
        for r in reversed(runs[:5])
    ]

    return {
        "runs": runs[:10],
        "latest": latest,
        "stage_labels": STAGE_LABELS,
        "trend": trend,
        "pulse_context": build_pulse_context(latest, runs),
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Only log errors, not every GET
        if args and str(args[1]) not in ("200", "304"):
            sys.stderr.write(f"[dashboard] {fmt % args}\n")

    def do_OPTIONS(self):
        """Handle CORS preflight for the AI proxy."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _read_json_body(self):
        """Read the request body and parse as JSON. Returns (payload, error_str)."""
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw), None
        except Exception as exc:
            return None, str(exc)

    @staticmethod
    def _safe_json_body(raw: bytes, status_code: int) -> bytes:
        """Guarantee the response body is valid JSON even when DIAL returns plain text."""
        try:
            json.loads(raw)          # already JSON — pass through unchanged
            return raw
        except Exception:
            text = raw.decode("utf-8", errors="replace").strip()
            return json.dumps({"error": text, "status": status_code}).encode()

    @staticmethod
    def _dial_request(url: str, api_key: str, data: bytes | None = None,
                      method: str = "GET") -> tuple[bytes, int]:
        """Fire a request to EPAM DIAL. Returns (body_bytes, http_status)."""
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Api-Key", api_key)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.read(), 200
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            return DashboardHandler._safe_json_body(raw, exc.code), exc.code
        except Exception as exc:
            return json.dumps({"error": str(exc)}).encode(), 502

    # ── POST dispatcher ───────────────────────────────────────────────────────

    def do_POST(self):
        path = urlparse(self.path).path

        # ── /api/ai-proxy  (chat completion) ─────────────────────────────────
        if path == "/api/ai-proxy":
            payload, err = self._read_json_body()
            if err:
                self._respond(400, "application/json",
                              json.dumps({"error": f"Invalid JSON: {err}"}).encode())
                return

            api_key  = payload.get("api_key", "").strip()
            model    = payload.get("model", "").strip()
            messages = payload.get("messages", [])

            if not api_key or not model or not messages:
                self._respond(400, "application/json",
                              json.dumps({"error": "api_key, model and messages are required"}).encode())
                return

            dial_url = (
                f"https://ai-proxy.lab.epam.com/openai/deployments/{model}"
                f"/chat/completions?api-version=2024-02-01"
            )
            dial_body = json.dumps({
                "messages": messages,
                "max_tokens": 2048,
                "temperature": 0.3,
            }).encode()

            body, status = self._dial_request(dial_url, api_key, data=dial_body, method="POST")
            self._respond(status, "application/json", body,
                          extra_headers={"Access-Control-Allow-Origin": "*"})

        # ── /api/ai-models  (list available models) ───────────────────────────
        elif path == "/api/ai-models":
            payload, err = self._read_json_body()
            if err:
                self._respond(400, "application/json",
                              json.dumps({"error": f"Invalid JSON: {err}"}).encode())
                return

            api_key = payload.get("api_key", "").strip()
            if not api_key:
                self._respond(400, "application/json",
                              json.dumps({"error": "api_key is required"}).encode())
                return

            body, status = self._dial_request(
                "https://ai-proxy.lab.epam.com/openai/models", api_key
            )
            self._respond(status, "application/json", body,
                          extra_headers={"Access-Control-Allow-Origin": "*"})

        else:
            self._respond(404, "text/plain", b"Not found")

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/data":
            data = build_dashboard_data()
            body = json.dumps(data, default=str).encode()
            self._respond(200, "application/json", body, extra_headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
            })

        elif path in ("/", "/index.html"):
            html_file = DASHBOARD_DIR / "index.html"
            body = html_file.read_bytes() if html_file.exists() else (
                b"<h1>dashboard/index.html not found</h1>"
                b"<p>Ensure you run from the project root.</p>"
            )
            self._respond(200, "text/html; charset=utf-8", body)

        else:
            self._respond(404, "text/plain", b"Not found")

    def _respond(self, code: int, content_type: str, body: bytes, extra_headers: dict = None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(
        description="ANYMUS Results Dashboard — serves live QA run data on localhost"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("DASHBOARD_PORT", "9090")),
        help="Port to listen on (default: 9090, env: DASHBOARD_PORT)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        dest="open_browser",
        help="Auto-open the dashboard in the default browser",
    )
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), DashboardHandler)

    print(f"\n{'='*54}")
    print(f"  ANYMUS Results Dashboard — INITIALISED")
    print(f"{'='*54}")
    print(f"  URL:      http://localhost:{args.port}")
    print(f"  API:      http://localhost:{args.port}/api/data")
    print(f"  Logs dir: {LOGS_DIR}")
    print(f"  Auto-refreshes every 10s. Press Ctrl+C to stop.")
    print(f"{'='*54}\n")
    sys.stdout.flush()

    if args.open_browser:
        import threading
        import webbrowser
        threading.Timer(0.6, lambda: webbrowser.open(f"http://localhost:{args.port}")).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    main()
