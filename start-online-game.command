#!/bin/bash
# Double-click on a Mac to start the Word Spot online game server.
cd "$(dirname "$0")"
python3 -m pip install --quiet -r requirements-server.txt
python3 -m wordspot.online
