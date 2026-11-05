#!/bin/bash
# Install (or update) the Word Spot online game server on a Mac that stays on.
# Paste into Terminal:
#   curl -fsSL https://raw.githubusercontent.com/JIIHI/DobbleDyslexia/word-spot-app/deploy/mac/install-roony.sh | bash
# Run it again any time to update to the latest version.
set -euo pipefail

APP="$HOME/word-spot"                      # the code (not in Dropbox)
VENV="$HOME/PythonEnv/word-spot"           # Python environment (not in Dropbox)
BRANCH="word-spot-app"
REPO="https://github.com/JIIHI/DobbleDyslexia.git"
PORT="${PORT:-8000}"
LABEL="org.wordspot.server"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/wordspot.log"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

# 1. git (comes with Apple's command line tools)
if ! xcode-select -p >/dev/null 2>&1; then
  say "Apple's command line tools are needed. A window will pop up - click Install,"
  say "wait for it to finish, then paste the same command again."
  xcode-select --install || true
  exit 1
fi

# 2. Python 3.10 or newer
PY=""
for cand in python3.13 python3.12 python3.11 python3.10 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$(command -v "$cand")"; break
  fi
done
if [ -z "$PY" ]; then
  say "Python 3.10 or newer is needed."
  echo "Install it from https://www.python.org/downloads/macos/ (the big yellow button),"
  echo "then paste the same command again."
  exit 1
fi
echo "Using $("$PY" --version) at $PY"

# 3. Get or update the code
say "Getting Word Spot from GitHub..."
if [ -d "$APP/.git" ]; then
  git -C "$APP" fetch -q origin "$BRANCH"
  git -C "$APP" checkout -q "$BRANCH"
  git -C "$APP" reset -q --hard "origin/$BRANCH"
else
  git clone -q --branch "$BRANCH" "$REPO" "$APP"
fi

# 4. Python environment
say "Installing what it needs (first time takes a minute)..."
mkdir -p "$(dirname "$VENV")"
[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install -q --upgrade pip
"$VENV/bin/python" -m pip install -q -r "$APP/requirements-server.txt"

# 5. Keep it running: start at login, restart if it stops
say "Setting it to run in the background..."
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV/bin/python</string>
    <string>-m</string>
    <string>wordspot.online</string>
    <string>--port</string>
    <string>$PORT</string>
  </array>
  <key>WorkingDirectory</key><string>$APP</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLISTEOF
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

# 6. Check it answers
ok=""
for _ in $(seq 1 20); do
  if curl -fs "http://localhost:$PORT/api/info" >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done
HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s).local"
IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
if [ -n "$ok" ]; then
  say "Word Spot is running! 🎉"
  echo "On the iPads (same wifi), open in Safari:"
  echo "    http://$HOST:$PORT"
  [ -n "$IP" ] && echo "or  http://$IP:$PORT"
  echo
  echo "If the Mac asks whether Python may accept incoming connections, click Allow."
  echo "Log file: $LOG"
else
  say "It didn't start. The last lines of the log:"
  tail -n 25 "$LOG" 2>/dev/null || true
  exit 1
fi
