@echo off
REM Song Automation - Auto-start script
REM This runs the song automation service using the venv Python

cd /d "C:\Users\vishal\Documents\Song Automation"

REM Add mpv and deno to PATH
set PATH=%PATH%;C:\Program Files\MPV Player;%USERPROFILE%\.deno\bin

REM Wait a few seconds for network on boot
timeout /t 10 /nobreak >nul

REM Regenerate playlists (picks up any new songs)
"C:\Users\vishal\Documents\Song Automation\.venv\Scripts\python.exe" scripts\generate_playlists.py

REM Start the automation service (unbuffered output for logging)
set PYTHONUNBUFFERED=1
"C:\Users\vishal\Documents\Song Automation\.venv\Scripts\python.exe" -m song_automation.main --config config\automation.yaml
