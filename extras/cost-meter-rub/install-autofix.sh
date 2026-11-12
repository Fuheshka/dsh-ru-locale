#!/bin/bash
# Install or remove the launchd auto-fixer for the dsh-cost-meter RUB patch.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.fuheshka.dsh-cost-meter-rub-autofix"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
USER_ID="$(id -u)"

xml_escape() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

if [[ "${1:-}" == "--uninstall" ]]; then
  launchctl bootout "gui/$USER_ID/$LABEL" >/dev/null 2>&1 || true
  rm -f "$PLIST"
  echo "Auto-fixer removed."
  exit 0
fi

NODE_BIN="${NODE_BIN:-$(command -v node || true)}"
if [[ -z "$NODE_BIN" || ! -x "$NODE_BIN" ]]; then
  echo "node not found; install Node.js 20+ first" >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$DIR/backup"
launchctl bootout "gui/$USER_ID/$LABEL" >/dev/null 2>&1 || true
launchctl bootout "gui/$USER_ID" "$PLIST" >/dev/null 2>&1 || true

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(xml_escape "$NODE_BIN")</string>
    <string>$(xml_escape "$DIR/autofix.mjs")</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$(xml_escape "$DIR")</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>60</integer>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>ProcessType</key>
  <string>Background</string>
  <key>LowPriorityIO</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$(xml_escape "$DIR/autofix.launchd.log")</string>
  <key>StandardErrorPath</key>
  <string>$(xml_escape "$DIR/autofix.launchd.log")</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST" >/dev/null
launchctl bootstrap "gui/$USER_ID" "$PLIST"
launchctl enable "gui/$USER_ID/$LABEL" >/dev/null 2>&1 || true
launchctl kickstart -k "gui/$USER_ID/$LABEL" >/dev/null 2>&1 || true

echo "Auto-fixer installed: $LABEL"
echo "Runs every 60 seconds; log: $DIR/autofix.log"
