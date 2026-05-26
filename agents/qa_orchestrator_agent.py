"""
ANYMUS — Agentic QA Orchestrator
=================================
A Claude-powered agent that owns the full InvenTree AUT lifecycle:
  1. Check if InvenTree is already running
  2. Spin up the AUT (if needed)
  3. Wait for all endpoints to become healthy
  4. Run the QA pipeline (API / mock / full)
  5. Generate & serve the Allure report
  6. Save a structured run log (JSON + Markdown)

What makes this agentic (not a script):
  - Claude reads each tool result and decides the next step
  - Skips spin-up if AUT is already live
  - On Stage 3 failure: auto-runs D2 mock to distinguish framework vs logic failures
  - Produces a natural-language narrative explaining what happened and why

Usage:
    python agents/qa_orchestrator_agent.py                  # full lifecycle
    python agents/qa_orchestrator_agent.py --mode api       # API stages only
    python agents/qa_orchestrator_agent.py --mode mock      # mock only (no live server)
    python agents/qa_orchestrator_agent.py --skip-spinup    # AUT already running
    python agents/qa_orchestrator_agent.py --teardown       # tear down AUT after run
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so `agents.tools` resolves correctly
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import anthropic

from agents.tools import TOOL_SCHEMAS, dispatch

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM = """\
You are the ANYMUS QA Orchestration Agent — an autonomous AI that owns the full lifecycle of an \
InvenTree QA run. You do not just run tests: you investigate failures, detect patterns, and \
close the loop back to the team's issue tracker.

## Execution order

1. `read_run_history` — always call this first. Establish whether there are known systemic \
   failures before running anything. If a stage is already systemic, note it prominently.
2. `check_aut_running` — determine if InvenTree is already live.
3. `spin_up_aut` — only if check_aut_running returned running=false AND skip-spinup was not \
   requested.
4. `wait_for_healthy` — only if you just called spin_up_aut. If healthy=false, call \
   save_run_report with the failure and stop.
5. `run_pipeline` — run the QA pipeline according to the requested mode.
6. Mock diagnostic — if run_pipeline returned all_pass=false AND stage 3 (API Suite) failed, \
   immediately call run_pipeline again with stage=4 and mock_mode=true. This answers: \
   "Is the test framework broken, or is the application broken?"
7. `generate_and_serve_report` — always generate the Allure report, even on failure.
8. `create_jira_ticket` — only if run_pipeline returned all_pass=false. Write a structured \
   incident report as the description: include which stages failed, what the mock diagnostic \
   showed, whether this is a new failure or matches a systemic pattern from run history, and \
   your root-cause hypothesis. If env vars are missing, note it but continue.
9. `tear_down_aut` — ONLY if teardown was requested. Call AFTER save_run_report. \
   Pass compose_file="docker-compose.yml".
10. `save_run_report` — always the LAST reporting tool. Include the full narrative: history \
    context, what ran, what failed, mock diagnostic conclusion, Jira ticket key if created.

## Decision rules

- History says stage 3 is systemic + stage 3 fails now → "This is a known persistent defect, \
  not a regression introduced today."
- History says all-green + stage 3 fails now → "This is a new regression. Investigate recent \
  changes."
- Mock passes after live failure → "Test framework is healthy. Failure is in live application \
  behaviour or data."
- Mock also fails → "Test framework itself is broken. Do not file an app bug — fix the \
  framework first."
- Never skip save_run_report, even on infrastructure failure.

## Final text response (after all tools complete)

Write three sections:
  1. **Executive Summary** (2-3 sentences): overall result, confidence level, key finding
  2. **Run Log**: path to saved .md file
  3. **Links**: Allure URL + Jira ticket URL (if created)
"""

# ---------------------------------------------------------------------------
# Agent colours (optional, graceful fallback)
# ---------------------------------------------------------------------------

try:
    from colorama import Fore, Style, init as _init
    _init(autoreset=True)
    _CYAN   = Fore.CYAN + Style.BRIGHT
    _GREEN  = Fore.GREEN + Style.BRIGHT
    _YELLOW = Fore.YELLOW + Style.BRIGHT
    _RED    = Fore.RED + Style.BRIGHT
    _RESET  = Style.RESET_ALL
except ImportError:
    _CYAN = _GREEN = _YELLOW = _RED = _RESET = ""


def _print_tool_call(name: str, inputs: dict):
    print(f"\n{_CYAN}[Agent → Tool]{_RESET} {name}")
    if inputs:
        for k, v in inputs.items():
            print(f"    {k}: {v}")


def _print_tool_result(name: str, result: dict):
    print(f"{_GREEN}[Tool → Agent]{_RESET} {name} result:")
    # Print a compact summary (avoid flooding terminal with full output)
    summary = {k: v for k, v in result.items() if k != "output"}
    print(f"    {json.dumps(summary, default=str)}")
    if "output" in result and result["output"]:
        tail = result["output"][-400:]
        print(f"    output (tail): ...{tail}")


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def run_agent(
    mode: str = "full",
    skip_spinup: bool = False,
    teardown: bool = False,
    base_url: str = "http://inventree.localhost",
) -> int:
    """
    Run the agentic QA orchestration loop.

    Returns exit code: 0 = all pass, 1 = failure.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Build the initial user message based on CLI flags
    mode_descriptions = {
        "full":  "all stages including UI and visual regression",
        "api":   "API stages only (stages 1–4, no UI or visual)",
        "mock":  "D2 mock tests only (no live server required)",
    }
    mode_desc = mode_descriptions.get(mode, mode)

    skip_note = " InvenTree is already running — skip spin-up." if skip_spinup else ""
    teardown_note = " After the run, tear down the InvenTree AUT." if teardown else ""

    initial_message = (
        f"Run the ANYMUS QA pipeline in {mode!r} mode ({mode_desc}).{skip_note}{teardown_note} "
        f"Target: {base_url}. "
        "Follow your decision rules and execution order (steps 1–10 in the system prompt). "
        "Make decisions based on each tool result. After all tools complete, give me the final executive summary."
    )

    messages = [{"role": "user", "content": initial_message}]

    print(f"\n{_CYAN}{'═'*64}")
    print("  ANYMUS — Agentic QA Orchestrator")
    print("  Powered by claude-sonnet-4-6 (Anthropic tool_use)")
    print(f"{'═'*64}{_RESET}")
    print(f"  Mode:       {mode} ({mode_desc})")
    print(f"  Target:     {base_url}")
    print(f"  Skip-spinup:{skip_spinup}")
    print(f"  Teardown:   {teardown}")

    round_num = 0
    allure_url = ""
    saved_md = ""
    jira_url = ""
    all_pass = False

    while True:
        round_num += 1
        print(f"\n{_YELLOW}── Round {round_num} ──{_RESET}")

        response = client.messages.create(
            model="claude-sonnet-4-6",
            tools=TOOL_SCHEMAS,
            system=SYSTEM,
            messages=messages,
            max_tokens=4096,
        )

        # Collect assistant content for the next messages turn
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extract final text
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text = block.text
                    break
            print(f"\n{_GREEN}{'═'*64}")
            print("  Agent Final Response")
            print(f"{'═'*64}{_RESET}")
            print(final_text)
            break

        if response.stop_reason != "tool_use":
            print(f"{_RED}Unexpected stop_reason: {response.stop_reason}{_RESET}")
            break

        # Execute all tool_use blocks
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            tool_name = block.name
            tool_inputs = block.input or {}

            _print_tool_call(tool_name, tool_inputs)

            try:
                result = dispatch(tool_name, tool_inputs)
            except Exception as exc:
                result = {"error": str(exc)}

            _print_tool_result(tool_name, result)

            # Track key results for exit code and final summary
            if tool_name == "run_pipeline" and isinstance(result, dict):
                all_pass = result.get("all_pass", False)
            if tool_name == "generate_and_serve_report" and isinstance(result, dict):
                allure_url = result.get("url", "")
            if tool_name == "save_run_report" and isinstance(result, dict):
                saved_md = result.get("saved_md", "")
            if tool_name == "create_jira_ticket" and isinstance(result, dict):
                jira_url = result.get("url") or ""
                if result.get("created"):
                    print(f"  {_GREEN}Jira ticket created:{_RESET} {jira_url}")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, default=str),
            })

        # Teardown hook: if agent called spin_up_aut and --teardown requested,
        # we don't interfere — Claude will handle it via the system prompt note.
        # The teardown_note in the initial message instructs Claude to do it.

        messages.append({"role": "user", "content": tool_results})

    return 0 if all_pass else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ANYMUS Agentic QA Orchestrator — Claude-powered full lifecycle runner"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "api", "mock"],
        default="full",
        help="Pipeline mode: full (default), api (stages 1-4), mock (D2 only)",
    )
    parser.add_argument(
        "--skip-spinup",
        action="store_true",
        help="Skip docker compose up (InvenTree is already running)",
    )
    parser.add_argument(
        "--teardown",
        action="store_true",
        help="Tear down InvenTree AUT after the run",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("INVENTREE_URL", "http://inventree.localhost"),
        help="InvenTree base URL (default: http://inventree.localhost)",
    )
    args = parser.parse_args()

    exit_code = run_agent(
        mode=args.mode,
        skip_spinup=args.skip_spinup,
        teardown=args.teardown,
        base_url=args.base_url,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
