"""
agents/tools/__init__.py
------------------------
Exposes TOOL_SCHEMAS (Anthropic format), to_openai_tools() (OpenAI/DIAL format),
and dispatch() (for executing tools).

Tool inventory:
    check_aut_running          Is InvenTree already live?
    spin_up_aut                docker compose up -d
    wait_for_healthy           Poll health_check.py until 6/6 up
    run_pipeline               Run run_pipeline.py, parse summary table
    generate_and_serve_report  allure generate + allure serve
    read_run_history           Load last N run-*.json, detect failure patterns   ← NEW
    save_run_report            Write run-*.json + run-*.md narrative
    create_jira_ticket         POST Jira REST API v2, tag [ANYMUS]               ← NEW
"""

from agents.tools.docker_tools import (
    check_aut_running,
    spin_up_aut,
    wait_for_healthy,
    tear_down_aut,
)
from agents.tools.pipeline_tools import run_pipeline
from agents.tools.report_tools import (
    generate_and_serve_report,
    read_run_history,
    save_run_report,
)
from agents.tools.jira_tools import create_jira_ticket

# ---------------------------------------------------------------------------
# Tool schemas — passed to client.messages.create(tools=TOOL_SCHEMAS)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "check_aut_running",
        "description": (
            "Check whether the InvenTree Application Under Test is already running "
            "by pinging its /api/ endpoint. Returns {running, base_url, detail}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "base_url": {
                    "type": "string",
                    "description": "InvenTree base URL",
                    "default": "http://inventree.localhost",
                }
            },
            "required": [],
        },
    },
    {
        "name": "spin_up_aut",
        "description": (
            "Start the InvenTree AUT stack using docker compose up -d. "
            "Returns {success, elapsed, output, returncode}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "compose_file": {
                    "type": "string",
                    "description": "Path to the compose file (relative to project root)",
                    "default": "docker-compose.yml",
                }
            },
            "required": [],
        },
    },
    {
        "name": "wait_for_healthy",
        "description": (
            "Poll health_check.py until all InvenTree API endpoints are healthy or "
            "timeout is reached. Returns {healthy, waited_seconds, endpoints_up, endpoints_total, detail}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "base_url": {
                    "type": "string",
                    "description": "InvenTree base URL",
                    "default": "http://inventree.localhost",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Maximum seconds to wait before giving up",
                    "default": 180,
                },
                "poll_interval": {
                    "type": "integer",
                    "description": "Seconds between health check polls",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
    {
        "name": "run_pipeline",
        "description": (
            "Run the ANYMUS QA pipeline (run_pipeline.py) and return structured results. "
            "Use stage=4 with mock_mode=true to run D2 mock tests as a diagnostic. "
            "Returns {all_pass, stages, duration, output, returncode}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "base_url": {
                    "type": "string",
                    "description": "InvenTree base URL",
                    "default": "http://inventree.localhost",
                },
                "api_only": {
                    "type": "boolean",
                    "description": "If true, run stages 1-4 only (no UI/visual)",
                    "default": False,
                },
                "stage": {
                    "type": "integer",
                    "description": "Run a single stage (0-6). Omit to run the full pipeline.",
                },
                "mock_mode": {
                    "type": "boolean",
                    "description": "If true, set MOCK_MODE=true (for D2 mock stage)",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    {
        "name": "generate_and_serve_report",
        "description": (
            "Generate the Allure HTML report from allure-results/ and start serving it "
            "in the background. Returns {url, generated, serve_pid, detail}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "port": {
                    "type": "integer",
                    "description": "Port to serve the Allure report on",
                    "default": 5050,
                },
                "open_browser": {
                    "type": "boolean",
                    "description": "Whether to open the report in the default browser",
                    "default": True,
                },
            },
            "required": [],
        },
    },
    {
        "name": "read_run_history",
        "description": (
            "Load the last N run logs from agents/conversation-logs/ and analyze failure "
            "patterns. Use this BEFORE running tests to establish historical context. "
            "If a stage has failed in ≥60% of recent runs it is classified as 'systemic' — "
            "meaning the failure is persistent, not flaky. "
            "Returns {runs_analyzed, overall_pass_rate, stage_failure_rates, "
            "systemic_failures, pattern, newest_run, oldest_run}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "last_n": {
                    "type": "integer",
                    "description": "Number of most recent runs to analyze (default 5)",
                    "default": 5,
                }
            },
            "required": [],
        },
    },
    {
        "name": "save_run_report",
        "description": (
            "Persist the run results as both a JSON file and a Markdown narrative to "
            "agents/conversation-logs/. Always call this as the LAST tool, even on failure. "
            "Returns {saved_json, saved_md}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Natural-language narrative of the run (Claude's analysis)",
                },
                "results": {
                    "type": "object",
                    "description": "Structured results: {stages, all_pass, duration}",
                },
                "allure_url": {
                    "type": "string",
                    "description": "URL where the Allure report is served",
                    "default": "",
                },
            },
            "required": ["summary", "results"],
        },
    },
    {
        "name": "tear_down_aut",
        "description": (
            "Stop the InvenTree AUT stack using docker compose down. "
            "Only call this when --teardown was explicitly requested by the user. "
            "Returns {success, elapsed, output}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "compose_file": {
                    "type": "string",
                    "description": "Path to the compose file (relative to project root)",
                    "default": "docker-compose.yml",
                }
            },
            "required": [],
        },
    },
    {
        "name": "create_jira_ticket",
        "description": (
            "Create a Jira bug ticket via REST API v2 when the pipeline has failures. "
            "Only call this when run_pipeline returned all_pass=false. "
            "Requires JIRA_BASE_URL, JIRA_TOKEN, JIRA_PROJECT_KEY env vars — if missing, "
            "returns created=false gracefully (do not abort the run). "
            "Returns {created, ticket_key, url, error}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "One-line failure summary for the Jira ticket title",
                },
                "description": {
                    "type": "string",
                    "description": (
                        "Full incident report — include which stages failed, "
                        "mock diagnostic result, and root-cause hypothesis"
                    ),
                },
                "affected_stages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Names of failing stages e.g. ['API Suite', 'D2 Mock Tests']",
                },
                "allure_url": {
                    "type": "string",
                    "description": "Allure report URL to embed in the ticket",
                    "default": "",
                },
                "issue_type": {
                    "type": "string",
                    "description": "Jira issue type (default: Bug)",
                    "default": "Bug",
                },
            },
            "required": ["summary", "description", "affected_stages"],
        },
    },
]

# ---------------------------------------------------------------------------
# Dispatch — maps tool name → function call
# ---------------------------------------------------------------------------

_TOOL_MAP = {
    "check_aut_running":          check_aut_running,
    "spin_up_aut":                spin_up_aut,
    "wait_for_healthy":           wait_for_healthy,
    "tear_down_aut":              tear_down_aut,
    "run_pipeline":               run_pipeline,
    "generate_and_serve_report":  generate_and_serve_report,
    "read_run_history":           read_run_history,
    "save_run_report":            save_run_report,
    "create_jira_ticket":         create_jira_ticket,
}


def dispatch(tool_name: str, inputs: dict) -> dict:
    """
    Execute a tool by name with the given inputs dict.
    Raises ValueError for unknown tools.
    """
    fn = _TOOL_MAP.get(tool_name)
    if fn is None:
        raise ValueError(f"Unknown tool: {tool_name!r}. Available: {list(_TOOL_MAP)}")
    return fn(**inputs)


def to_openai_tools(schemas=None):
    """
    Convert Anthropic-format tool schemas to OpenAI function-calling format.

    Anthropic format:
        {"name": ..., "description": ..., "input_schema": {...}}

    OpenAI format:
        {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}
    """
    src = schemas if schemas is not None else TOOL_SCHEMAS
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["input_schema"],
            },
        }
        for s in src
    ]
