@echo off
echo ========================================================
echo Starting TaskFlow Pro (Backend + Frontend)
echo ========================================================

cd /d "%~dp0"

echo [1/2] Starting FastAPI Backend on http://127.0.0.1:8000...
start "TaskFlow Pro - Backend" cmd /k "cd backend && .venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Starting Vite Frontend on http://127.0.0.1:5173...
start "TaskFlow Pro - Frontend" cmd /k "cd frontend && npm run dev -- --host 127.0.0.1 --port 5173"

echo.
echo Both servers are launching!
echo Backend API Docs: http://127.0.0.1:8000/docs
echo Frontend Kanban:  http://127.0.0.1:5173/
echo.
pause
