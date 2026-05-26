#!/bin/sh
# ANYMUS — Test Runner Entrypoint
#
# Validates the Docker network environment and then starts the QA pipeline.
# All environment variables (INVENTREE_URL, INVENTREE_API_URL, etc.) should
# be set by docker-compose.tests.yml before this script runs.

echo "[entrypoint] INVENTREE_URL     = ${INVENTREE_URL:-<not set>}"
echo "[entrypoint] INVENTREE_API_URL = ${INVENTREE_API_URL:-<not set>}"

exec python scripts/run_pipeline.py "$@"
