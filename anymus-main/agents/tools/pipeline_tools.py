"""
agents/tools/pipeline_tools.py
-------------------------------
Tools for running the ANYMUS QA pipeline stages.
"""

import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
PIPELINE_SCRIPT = ROOT / "scripts" / "run_pipeline.py"


def run_pipeline(
    base_url: str = "http://inventree.localhost",
    api_only: bool = False,
    stage: int | None = None,
    mock_mode: bool = False,
) -> dict:
    """
    Run run_pipeline.py and return structured results.

    Args:
        base_url:  InvenTree base URL
        api_only:  If True, pass --api-only (stages 1-4)
        stage:     Run a single stage (1-6); overrides api_only
        mock_mode: If True, set MOCK_MODE=true env var (for stage 4)

    Returns:
        {
          "all_pass": bool,
          "stages": {stage_num: exit_code, ...},
          "duration": str,
          "output": str (last 3000 chars of combined stdout/stderr),
          "returncode": int
        }
    """
    python_bin = _find_python()
    cmd = [python_bin, str(PIPELINE_SCRIPT), "--base-url", base_url]

    if stage is not None:
        cmd += ["--stage", str(stage)]
    elif api_only:
        cmd.append("--api-only")

    import os
    env = {**os.environ, "MOCK_MODE": "true" if mock_mode else "false"}

    t0 = time.monotonic()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
    )
    duration = f"{time.monotonic() - t0:.1f}s"
    combined = result.stdout + result.stderr

    stages = _parse_stage_results(combined)

    return {
        "all_pass": result.returncode == 0,
        "stages": stages,
        "duration": duration,
        "output": combined[-3000:] if len(combined) > 3000 else combined,
        "returncode": result.returncode,
    }


def _parse_stage_results(output: str) -> dict:
    """
    Parse the pipeline summary table from run_pipeline.py output.
    Returns {stage_num: exit_code} where exit_code is 0 (pass), 1 (fail), or None (skip).
    """
    stages = {}
    # Match lines like "✓  PASS" or "✗  FAIL" after stage labels
    pass_pattern = re.compile(r"(✓|✗|─)\s+(PASS|FAIL|SKIP)", re.UNICODE)

    stage_headers = {
        "Env Check": 0,
        "D3 Health": 1,
        "Contract": 2,
        "API Suite": 3,
        "D2 Mock": 4,
        "UI Suite": 5,
        "D1 Visual": 6,
    }

    for line in output.splitlines():
        for label, num in stage_headers.items():
            if label in line:
                m = pass_pattern.search(line)
                if m:
                    symbol = m.group(1)
                    stages[num] = 0 if symbol == "✓" else (None if symbol == "─" else 1)
                break

    return stages


def _find_python() -> str:
    """Find python binary — prefer API venv, fallback to system."""
    api_venv_python = ROOT / "automation" / "api" / ".venv" / "bin" / "python"
    if api_venv_python.exists():
        return str(api_venv_python)
    return sys.executable
