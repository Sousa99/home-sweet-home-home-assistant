#!/usr/bin/env python3
"""Point ZHA at the cluster serial device after restoring a state bundle."""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone

ENTRIES = "/config/.storage/core.config_entries"

path = os.environ.get("ZHA_SERIAL_PATH", "").strip()
if not path:
    sys.exit(0)

flow_control = os.environ.get("ZHA_FLOW_CONTROL", "hardware")
baudrate = int(os.environ.get("ZHA_BAUDRATE", "460800"))

if not os.path.exists(ENTRIES):
    print("fix-zha-serial: no core.config_entries, nothing to patch")
    sys.exit(0)

with open(ENTRIES, encoding="utf-8") as handle:
    data = json.load(handle)

changed = False
for entry in data.get("data", {}).get("entries", []):
    if entry.get("domain") != "zha":
        continue

    device = entry.setdefault("data", {}).setdefault("device", {})
    desired = {
        "path": path,
        "flow_control": flow_control,
        "baudrate": baudrate,
    }
    for key, value in desired.items():
        if device.get(key) != value:
            device[key] = value
            changed = True

if not changed:
    print(f"fix-zha-serial: ZHA already uses {path}")
    sys.exit(0)

timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup = f"{ENTRIES}.bak-{timestamp}"
shutil.copy2(ENTRIES, backup)

directory = os.path.dirname(ENTRIES)
fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".core.config_entries.")
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
    handle.write("\n")
os.replace(tmp_path, ENTRIES)

print(f"fix-zha-serial: updated ZHA to {path} ({flow_control}, {baudrate}); backup {backup}")
