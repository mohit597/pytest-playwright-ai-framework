"""
ANYMUS — Pre-flight API Health Check (Differentiator D3)

Pings all critical InvenTree Part API endpoints and reports their health.
Used as the gate before API and UI test suites run in CI/CD.

Usage:
    python scripts/health_check.py
    python scripts/health_check.py --base-url http://localhost:8000
    python scripts/health_check.py --base-url http://localhost:8000 --timeout 10

Exit codes:
    0 — all critical endpoints healthy
    1 — one or more endpoints are down
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests
from colorama import Fore, Style, init
from tabulate import tabulate

init(autoreset=True)

CRITICAL_ENDPOINTS = [
    "/api/",
    "/api/part/",
    "/api/part/category/",
    "/api/part/category/tree/",
    "/api/part/category/parameters/",
    "/api/part/test-template/",
]

# 200 or 401 = service is UP (401 = auth required, but server is responding)
HEALTHY_CODES = {200, 201, 401}


def check_endpoint(base_url: str, path: str, timeout: int) -> dict:
    url = f"{base_url}{path}"
    start = time.monotonic()
    try:
        response = requests.get(url, timeout=timeout)
        latency_ms = int((time.monotonic() - start) * 1000)
        healthy = response.status_code in HEALTHY_CODES
        return {
            "path": path,
            "url": url,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "healthy": healthy,
            "error": None,
        }
    except requests.ConnectionError as e:
        return {
            "path": path,
            "url": url,
            "status_code": None,
            "latency_ms": None,
            "healthy": False,
            "error": "CONNECTION REFUSED",
        }
    except requests.Timeout:
        return {
            "path": path,
            "url": url,
            "status_code": None,
            "latency_ms": timeout * 1000,
            "healthy": False,
            "error": f"TIMEOUT (>{timeout}s)",
        }


def run_health_check(base_url: str, timeout: int) -> list:
    results = []
    for path in CRITICAL_ENDPOINTS:
        result = check_endpoint(base_url, path, timeout)
        results.append(result)
    return results


def print_report(results: list, base_url: str):
    print(f"\n{Style.BRIGHT}ANYMUS — Pre-flight Health Check")
    print(f"Target: {base_url}")
    print("=" * 60)

    rows = []
    for r in results:
        status = str(r["status_code"]) if r["status_code"] else r["error"]
        latency = f"{r['latency_ms']}ms" if r["latency_ms"] is not None else "—"
        health = (
            f"{Fore.GREEN}✓ UP{Style.RESET_ALL}"
            if r["healthy"]
            else f"{Fore.RED}✗ DOWN{Style.RESET_ALL}"
        )
        rows.append([r["path"], status, latency, health])

    print(
        tabulate(
            rows,
            headers=["Endpoint", "Status", "Latency", "Health"],
            tablefmt="simple",
        )
    )

    down = [r for r in results if not r["healthy"]]
    up = [r for r in results if r["healthy"]]

    print()
    if not down:
        print(f"{Fore.GREEN}{Style.BRIGHT}Result: ALL SYSTEMS GO ✓  ({len(up)}/{len(results)} endpoints healthy)")
    else:
        print(
            f"{Fore.RED}{Style.BRIGHT}Result: DEGRADED — {len(down)} endpoint(s) DOWN ✗"
        )
        for r in down:
            print(f"  {Fore.RED}✗ {r['path']}  →  {r['error'] or r['status_code']}")
    print()


def write_json_report(results: list, base_url: str):
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "overall": "healthy" if all(r["healthy"] for r in results) else "degraded",
        "endpoints": results,
    }
    with open("health_report.json", "w") as f:
        json.dump(report, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="ANYMUS pre-flight health check for InvenTree API endpoints"
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("INVENTREE_URL", "http://localhost:8000"),
        help="InvenTree base URL (default: INVENTREE_URL env var or http://localhost:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Request timeout in seconds (default: 5)",
    )
    args = parser.parse_args()

    results = run_health_check(args.base_url, args.timeout)
    print_report(results, args.base_url)
    write_json_report(results, args.base_url)

    all_healthy = all(r["healthy"] for r in results)
    sys.exit(0 if all_healthy else 1)


if __name__ == "__main__":
    main()
