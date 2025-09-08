@echo off 
echo Starting all FOReporting v2 services locally... 
start "Backend" start_backend_local.bat 
timeout /t 5 /nobreak > nul 
start "Frontend" start_frontend_local.bat 
start "Watcher" start_watcher_local.bat 
echo. 
echo All services started! 
echo   Backend: http://localhost:8000 
echo   Frontend: http://localhost:8501 
echo. 
pause 
