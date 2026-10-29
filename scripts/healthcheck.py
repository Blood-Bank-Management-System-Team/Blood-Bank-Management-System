"""Container healthcheck: GET /api/health/ and exit 0 only on HTTP 200.

Sends the first DJANGO_ALLOWED_HOSTS entry as the Host header so Django's host
validation accepts the request.
"""
import os
import sys
import urllib.request

hosts = [h.strip().lstrip(".") for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")]
host = next((h for h in hosts if h and h != "*"), "localhost")

request = urllib.request.Request("http://127.0.0.1:8000/api/health/", headers={"Host": host})
try:
    with urllib.request.urlopen(request, timeout=4) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception as exc:
    print(f"healthcheck failed: {exc}", file=sys.stderr)
    sys.exit(1)
