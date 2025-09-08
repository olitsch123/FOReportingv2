@echo off
echo ============================================================
echo FOReporting v2 - Starting All Services Locally
echo ============================================================
echo.

REM UTF-8 settings [[memory:7957295]]
chcp 65001 >nul

REM Check if backend is already running
netstat -ano | findstr :8000 >nul
if %errorlevel% equ 0 (
    echo Backend already running on port 8000
) else (
    echo Starting Backend API...
    start "FOReporting Backend" /min cmd /c "set DEPLOYMENT_MODE=local && set PYTHONPATH=. && set PGCLIENTENCODING=UTF8 && set PYTHONUTF8=1 && python run.py"
)

REM Wait for backend to start
echo Waiting for backend to initialize...
timeout /t 5 /nobreak >nul

REM Start frontend
echo Starting Frontend Dashboard...
start "FOReporting Frontend" cmd /c "set DEPLOYMENT_MODE=local && set PYTHONPATH=. && streamlit run app/frontend/dashboard.py"

REM Optional: Start file watcher
choice /C YN /T 5 /D N /M "Start file watcher"
if %errorlevel% equ 1 (
    echo Starting File Watcher...
    start "FOReporting Watcher" /min cmd /c "set DEPLOYMENT_MODE=local && set PYTHONPATH=. && python app/services/watcher_runner.py"
)

echo.
echo ============================================================
echo All services started!
echo.
echo Backend API: http://localhost:8000
echo API Docs:    http://localhost:8000/docs
echo Frontend:    http://localhost:8501
echo ============================================================
echo.
echo Press any key to verify status...
pause >nul

python verify_complete_local.py

pause