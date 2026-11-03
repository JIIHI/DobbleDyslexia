#!/bin/bash
# Fetch the latest Word Spot from GitHub and restart it if anything changed.
set -euo pipefail
BASE=/opt/wordspot
APP=$BASE/app
source $BASE/branch
git -C $APP fetch -q origin "$BRANCH"
if [ "$(git -C $APP rev-parse HEAD)" != "$(git -C $APP rev-parse origin/$BRANCH)" ] || [ "${1:-}" = "--force" ]; then
  git -C $APP reset -q --hard "origin/$BRANCH"
  docker compose -f $APP/deploy/compose.yaml --env-file $BASE/.env up -d --build
  docker image prune -f > /dev/null
  echo "$(date): updated to $(git -C $APP rev-parse --short HEAD)"
else
  echo "$(date): already up to date"
fi
