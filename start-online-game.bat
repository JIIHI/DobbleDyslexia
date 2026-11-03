@echo off
rem Double-click on Windows to start the Word Spot online game server.
cd /d "%~dp0"
py -m pip install --quiet -r requirements-server.txt
py -m wordspot.online
pause
