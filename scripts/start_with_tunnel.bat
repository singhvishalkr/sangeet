@echo off
REM Sangeet — Start with public tunnel
REM Double-click this to start Sangeet + get a public URL for your phone

cd /d "C:\Users\vishal\Documents\Song Automation"

set PATH=%PATH%;C:\Program Files\MPV Player;%USERPROFILE%\.deno\bin
set PYTHONUNBUFFERED=1

REM Wait for network on boot
timeout /t 5 /nobreak >nul

REM Regenerate playlists
".venv\Scripts\python.exe" scripts\generate_playlists.py 2>nul

REM Start Sangeet in background
echo Starting Sangeet...
start /b "" ".venv\Scripts\python.exe" -m song_automation.main --config config\automation.yaml

REM Give the server a moment to start
timeout /t 3 /nobreak >nul

REM Start Cloudflare Tunnel — prints the public URL
echo.
echo ============================================
echo   Your public URL will appear below.
echo   Open it on your phone to control music.
echo   Press Ctrl+C to stop everything.
echo ============================================
echo.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8765
