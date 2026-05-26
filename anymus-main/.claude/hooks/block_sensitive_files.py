#!/usr/bin/env python3
"""
Claude Code PreToolUse hook — guard sensitive credential files.

Blocks Read / Write / Edit / Grep / Glob / Bash tool calls that target
files containing real credentials or secrets.

Rules:
  - .env             BLOCKED  (real credentials)
  - .env.local       BLOCKED  (environment overrides with real values)
  - .env.production  BLOCKED
  - .env.example     ALLOWED  (safe placeholder template)
  - *.pem / *.key    BLOCKED  (certificates & private keys)
  - secrets.json     BLOCKED
  - credentials.*    BLOCKED
  - cat .env (Bash)  BLOCKED

Exit codes used by Claude Code:
  0  — allow the tool call to proceed
  1  — block; stdout is shown to the agent as context/error
"""

import json
import re
import sys

# ---------------------------------------------------------------------------
# Patterns matched against the normalised (forward-slash) file path
# ---------------------------------------------------------------------------

BLOCKED_PATH_RE = [
    # .env exactly — but NOT .env.example
    r"(^|[/\\])\.env$",
    # .env.<suffix> where suffix does NOT start with "example"
    r"(^|[/\\])\.env\.(?!example)[^/\\]+$",
    # Secrets / credentials files (json, yaml, yml, env, ini, cfg, txt)
    r"(^|[/\\])secrets?\.(json|ya?ml|env|ini|cfg|txt)$",
    r"(^|[/\\])credentials?\.(json|ya?ml|env|ini|cfg|txt)$",
    # Auth token files
    r"(^|[/\\])auth[_-]?tokens?\.(json|ya?ml|txt)$",
    # Private key / certificate files
    r"\.(pem|key|p12|pfx|crt|cer|der)$",
    # SSH private keys
    r"(^|[/\\])id_(rsa|ecdsa|ed25519|dsa)$",
    # .netrc (stores HTTP/FTP credentials)
    r"(^|[/\\])\.netrc$",
]

# Bash command patterns that suggest reading a .env credential file
BLOCKED_BASH_RE = [
    # cat / type / less / more reading .env (but not .env.example)
    r"\b(cat|type|less|more|head|tail)\s+['\"]?[^\s]*\.env(?!\.example)['\"]?",
    # Redirect into .env — e.g.  echo "PASS=x" >> .env
    r">+\s*['\"]?[^\s]*\.env['\"]?\s*$",
    # source / . (dot) to load .env into shell
    r"\b(source|\.)\s+['\"]?[^\s]*\.env(?!\.example)['\"]?",
]

_PATH_COMPILED = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATH_RE]
_BASH_COMPILED = [re.compile(p, re.IGNORECASE) for p in BLOCKED_BASH_RE]


def _normalise(path: str) -> str:
    return path.replace("\\", "/")


def is_sensitive_path(path: str) -> bool:
    norm = _normalise(path)
    return any(pat.search(norm) for pat in _PATH_COMPILED)


def is_sensitive_bash(command: str) -> bool:
    return any(pat.search(command) for pat in _BASH_COMPILED)


def block(reason: str) -> None:
    print(f"[security-hook] BLOCKED — {reason}", flush=True)
    print(
        "Use .env.example for templates, or access credentials via "
        "environment variables / python-dotenv in code.",
        flush=True,
    )
    sys.exit(1)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)  # Malformed hook input — fail open

    tool = payload.get("tool_name", "")
    params = payload.get("tool_input", {})

    # ── File-based tools ────────────────────────────────────────────────────
    if tool in ("Read", "Write", "Edit", "NotebookEdit"):
        path = params.get("file_path", "")
        if path and is_sensitive_path(path):
            block(f"'{path}' matches a sensitive-file pattern")

    # ── Glob — block patterns that explicitly target .env files ────────────
    elif tool == "Glob":
        pattern = params.get("pattern", "")
        if pattern and is_sensitive_path(pattern):
            block(f"Glob pattern '{pattern}' targets sensitive files")

    # ── Grep — block when the search path is a credential file ─────────────
    elif tool == "Grep":
        path = params.get("path", "")
        if path and is_sensitive_path(path):
            block(f"Grep targeting sensitive path '{path}'")

    # ── Bash — block commands that read or overwrite .env files ────────────
    elif tool == "Bash":
        command = params.get("command", "")
        if command and is_sensitive_bash(command):
            block("Bash command appears to read or write a .env credential file")

    sys.exit(0)


if __name__ == "__main__":
    main()
