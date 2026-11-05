#!/bin/bash
# Stop Word Spot on this Mac and remove it from starting at login.
# (Leaves the code in ~/word-spot and the Python environment in ~/PythonEnv/word-spot.)
PLIST="$HOME/Library/LaunchAgents/org.wordspot.server.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "Word Spot stopped and won't start at login any more."
