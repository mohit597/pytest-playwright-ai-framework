import os
from dotenv import load_dotenv

load_dotenv()

# INVENTREE_API_URL bypasses the Caddy proxy (which strips token auth responses)
# and talks directly to the Django backend. Falls back to INVENTREE_URL for local dev.
BASE_URL = os.getenv("INVENTREE_API_URL") or os.getenv("INVENTREE_URL", "http://localhost:8000")
USERNAME = os.getenv("INVENTREE_USER", "admin")
PASSWORD = os.getenv("INVENTREE_PASS", "inventree")
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

# Endpoints used by health check (D3)
# Note: /api/part/parameter/ was removed in InvenTree v1.3 — replaced by /api/part/category/parameters/
HEALTH_ENDPOINTS = [
    "/api/",
    "/api/part/",
    "/api/part/category/",
    "/api/part/category/tree/",
    "/api/part/category/parameters/",
    "/api/part/test-template/",
]

# Healthy = 200 or 401 (auth required but service is up). 5xx / ConnectionError = DOWN.
HEALTHY_STATUS_CODES = {200, 201, 401}
