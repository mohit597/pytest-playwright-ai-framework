"""
agents/tools/jira_tools.py
---------------------------
Tool for creating Jira bug tickets from QA run failures.

Required environment variables:
    JIRA_BASE_URL     e.g. https://jiraeu.epam.com
    JIRA_TOKEN        Bearer token (Personal Access Token)
    JIRA_PROJECT_KEY  e.g. EPMCDMETST

All three must be set for ticket creation to succeed.
If any are missing the tool returns created=false with a clear error —
it never raises, so the agent loop continues regardless.
"""

import os
import urllib.error
import urllib.request
import json
from typing import Any


def create_jira_ticket(
    summary: str,
    description: str,
    affected_stages: list[str],
    allure_url: str = "",
    issue_type: str = "Bug",
) -> dict[str, Any]:
    """
    Create a Jira bug ticket via the Jira REST API v2.

    The ticket is tagged with labels ["ANYMUS", "automated-qa"] so it is
    easy to filter and distinguish from manually filed bugs.

    Args:
        summary:         One-line summary of the failure (will be prefixed with [ANYMUS])
        description:     Claude's failure narrative — the full incident report text
        affected_stages: List of stage names that failed e.g. ["API Suite", "D2 Mock Tests"]
        allure_url:      URL of the Allure report for this run
        issue_type:      Jira issue type (default: "Bug")

    Returns:
        {
          "created":    bool,
          "ticket_key": str | None,   e.g. "EPMCDMETST-37884"
          "url":        str | None,   e.g. "https://jiraeu.epam.com/browse/EPMCDMETST-37884"
          "error":      str | None,
        }
    """
    base_url    = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    token       = os.environ.get("JIRA_TOKEN", "")
    project_key = os.environ.get("JIRA_PROJECT_KEY", "")

    if not base_url or not token or not project_key:
        missing = [
            v for v, val in [
                ("JIRA_BASE_URL", base_url),
                ("JIRA_TOKEN", token),
                ("JIRA_PROJECT_KEY", project_key),
            ] if not val
        ]
        return {
            "created": False,
            "ticket_key": None,
            "url": None,
            "error": f"Missing required env vars: {', '.join(missing)}. "
                     "Set them to enable automatic Jira ticket creation.",
        }

    # Build the full description
    body_parts = [description]

    if affected_stages:
        body_parts.append(
            "\n*Failing stages:* " + ", ".join(affected_stages)
        )
    if allure_url:
        body_parts.append(f"\n*Allure Report:* {allure_url}")

    body_parts.append(
        "\n\n_This ticket was created automatically by the ANYMUS QA Orchestration Agent._"
    )

    payload = {
        "fields": {
            "project":     {"key": project_key},
            "summary":     f"[ANYMUS] {summary}",
            "description": "\n".join(body_parts),
            "issuetype":   {"name": issue_type},
            "labels":      ["ANYMUS", "automated-qa"],
        }
    }

    api_url = f"{base_url}/rest/api/2/issue"
    data    = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

    try:
        req  = urllib.request.Request(api_url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            body     = json.loads(resp.read().decode("utf-8"))
            ticket_key = body.get("key", "")
            return {
                "created":    True,
                "ticket_key": ticket_key,
                "url":        f"{base_url}/browse/{ticket_key}",
                "error":      None,
            }

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")[:400]
        return {
            "created":    False,
            "ticket_key": None,
            "url":        None,
            "error":      f"HTTP {exc.code}: {raw}",
        }
    except Exception as exc:
        return {
            "created":    False,
            "ticket_key": None,
            "url":        None,
            "error":      str(exc),
        }
