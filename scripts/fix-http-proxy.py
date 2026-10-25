#!/usr/bin/env python3
"""Ensure Home Assistant trusts the cluster ingress proxy.

Home Assistant 2026.8+ stores HTTP server settings in .storage/http and ignores
the old http: block in configuration.yaml. This script is idempotent and runs
before Home Assistant starts.
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone

STORAGE = "/config/.storage/http"

raw_proxies = os.environ.get(
    "HTTP_TRUSTED_PROXIES", "10.42.0.0/16,10.43.0.0/16"
)
trusted_proxies = [item.strip() for item in raw_proxies.split(",") if item.strip()]
if not trusted_proxies:
    print("fix-http-proxy: no trusted proxies configured", file=sys.stderr)
    sys.exit(1)

timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
now = datetime.now(timezone.utc).isoformat()

if os.path.exists(STORAGE):
    with open(STORAGE, encoding="utf-8") as handle:
        data = json.load(handle)
    existed = True
else:
    data = {
        "version": 2,
        "minor_version": 2,
        "key": "http",
        "data": {
            "stable": {},
            "pending": None,
            "yaml_migration_done": True,
        },
    }
    existed = False

data.setdefault("version", 2)
data.setdefault("minor_version", 2)
data["key"] = "http"

body = data.setdefault("data", {})
stable = body.setdefault("stable", {})

stable.setdefault("server_port", 8123)
stable.setdefault("cors_allowed_origins", ["https://cast.home-assistant.io"])
stable.setdefault("login_attempts_threshold", -1)
stable.setdefault("ip_ban_enabled", True)
stable.setdefault("ssl_profile", "modern")
stable.setdefault("use_x_frame_options", True)
stable.setdefault("created_at", now)
stable.setdefault("error", None)
stable.setdefault("error_message", None)

changed = False
if stable.get("use_x_forwarded_for") is not True:
    stable["use_x_forwarded_for"] = True
    changed = True
if stable.get("trusted_proxies") != trusted_proxies:
    stable["trusted_proxies"] = trusted_proxies
    changed = True
if body.get("pending") is not None:
    body["pending"] = None
    changed = True
if body.get("yaml_migration_done") is not True:
    body["yaml_migration_done"] = True
    changed = True

if not changed:
    print("fix-http-proxy: already configured")
    sys.exit(0)

os.makedirs(os.path.dirname(STORAGE), exist_ok=True)
if existed:
    backup = f"{STORAGE}.bak-{timestamp}"
    shutil.copy2(STORAGE, backup)
else:
    backup = "(new file)"

fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(STORAGE), prefix=".http.")
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
    handle.write("\n")
os.replace(tmp_path, STORAGE)

print(
    "fix-http-proxy: enabled X-Forwarded-For for "
    f"{', '.join(trusted_proxies)}; backup {backup}"
)
