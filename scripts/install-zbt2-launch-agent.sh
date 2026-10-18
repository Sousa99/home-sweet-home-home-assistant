#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
uv_bin=${UV_BIN:-$(command -v uv || true)}
if [ -z "$uv_bin" ]; then
  printf '%s\n' "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

label=com.home-sweet-home.zbt2-serial-bridge
agent_dir="$HOME/Library/LaunchAgents"
plist="$agent_dir/$label.plist"
mkdir -p "$agent_dir"

cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>$uv_bin</string>
    <string>run</string>
    <string>--directory</string>
    <string>$repo_dir</string>
    <string>scripts/zbt2-serial-bridge.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>/tmp/home-sweet-home-zbt2-bridge.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/home-sweet-home-zbt2-bridge.log</string>
</dict>
</plist>
EOF

uid=$(id -u)
launchctl bootout "gui/$uid" "$plist" 2>/dev/null || true
launchctl bootstrap "gui/$uid" "$plist"
launchctl kickstart -k "gui/$uid/$label"
printf 'Installed and started %s\n' "$label"
