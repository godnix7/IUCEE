@echo off
echo ============================================
echo  AI-Powered Pixel Annotation Studio
echo ============================================
echo.

echo [1/2] Starting FastAPI backend on port 8000...
start "Backend" cmd /c "cd /d %~dp0backend && python run.py"

timeout /t 2 /nobreak >nul

echo [2/2] Starting Vite React frontend...
start "Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

echo.
echo === Both servers are running! ===
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Close the terminal windows to stop the servers.
pause
