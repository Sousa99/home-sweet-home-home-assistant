#!/bin/sh
set -eu

import_dir=/config/import
applied_dir="$import_dir/applied"

mkdir -p "$import_dir" "$applied_dir"

for archive in "$import_dir"/*.tar.gz; do
    [ -e "$archive" ] || continue

    base=$(basename "$archive")
    checksum_file="$archive.sha256"

    if [ ! -f "$checksum_file" ]; then
        echo "restore-state: missing checksum file for $base" >&2
        exit 1
    fi

    expected=$(awk '{print $1; exit}' "$checksum_file")
    if [ -z "$expected" ]; then
        echo "restore-state: empty checksum file for $base" >&2
        exit 1
    fi

    if command -v sha256sum >/dev/null 2>&1; then
        actual=$(sha256sum "$archive" | awk '{print $1}')
    else
        actual=$(shasum -a 256 "$archive" | awk '{print $1}')
    fi

    if [ "$expected" != "$actual" ]; then
        echo "restore-state: checksum mismatch for $base" >&2
        exit 1
    fi

    marker="$applied_dir/$base.sha256"
    if [ -f "$marker" ] && [ "$(cat "$marker")" = "$actual" ]; then
        echo "restore-state: already applied $base"
        continue
    fi

    if command -v python3 >/dev/null 2>&1; then
        if ! python3 - "$archive" <<'PY'
import sys
import tarfile

try:
    with tarfile.open(sys.argv[1], "r:gz") as archive:
        for member in archive.getmembers():
            name = member.name
            if name.startswith("/") or ".." in name.split("/"):
                raise SystemExit(1)
            if member.issym() or member.islnk():
                link = member.linkname
                if link.startswith("/") or ".." in link.split("/"):
                    raise SystemExit(1)
except Exception:
    raise SystemExit(1)
PY
        then
            echo "restore-state: refusing unsafe paths in $base" >&2
            exit 1
        fi
    elif tar -tzf "$archive" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
        echo "restore-state: refusing unsafe paths in $base" >&2
        exit 1
    fi

    echo "restore-state: extracting $base"
    tar -xzf "$archive" -C /config

    if [ -n "${ZHA_SERIAL_PATH:-}" ] && [ -x /usr/local/bin/fix-zha-serial.py ]; then
        /usr/local/bin/fix-zha-serial.py
    fi

    printf '%s\n' "$actual" > "$marker"
    mv "$archive" "$applied_dir/$base"
    rm -f "$checksum_file"
done
