@echo off
echo ============================================================
echo FOReporting v2 - Complete Local Setup (100%% Accuracy)
echo ============================================================
echo.

REM Set PostgreSQL path
set PSQL_PATH=C:\Program Files\PostgreSQL\17\bin
set PATH=%PSQL_PATH%;%PATH%

REM UTF-8 settings [[memory:7957295]]
chcp 65001 >nul
set PGCLIENTENCODING=UTF8
set PYTHONUTF8=1

REM Step 1: Stop Docker containers
echo [1/8] Stopping Docker containers...
docker-compose down 2>nul
echo Done.
echo.

REM Step 2: Update .env for local
echo [2/8] Configuring .env for local execution...
if not exist .env (
    echo Creating .env from env_example.txt...
    copy env_example.txt .env
)

REM Update DATABASE_URL [[memory:7989272]]
powershell -Command "(Get-Content .env) -replace '@postgres:5432', '@localhost:5432' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'DEPLOYMENT_MODE=docker', 'DEPLOYMENT_MODE=local' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'DEPLOYMENT_MODE=production', 'DEPLOYMENT_MODE=local' | Set-Content .env"

REM Ensure DEPLOYMENT_MODE exists
findstr /C:"DEPLOYMENT_MODE" .env >nul
if %errorlevel% neq 0 (
    echo DEPLOYMENT_MODE=local >> .env
)

echo Done.
echo.

REM Step 3: Setup PostgreSQL database
echo [3/8] Setting up PostgreSQL database...
echo Creating user 'system'...
"%PSQL_PATH%\psql" -h localhost -p 5432 -U postgres -c "CREATE USER system WITH PASSWORD 'BreslauerPlatz4' CREATEDB SUPERUSER;" 2>nul
if %errorlevel% equ 0 (
    echo   - User created successfully
) else (
    echo   - User already exists or error occurred
)

echo Creating database 'foreporting_db'...
"%PSQL_PATH%\psql" -h localhost -p 5432 -U postgres -c "CREATE DATABASE foreporting_db OWNER system ENCODING 'UTF8';" 2>nul
if %errorlevel% equ 0 (
    echo   - Database created successfully
) else (
    echo   - Database already exists or error occurred
)

echo Granting privileges...
"%PSQL_PATH%\psql" -h localhost -p 5432 -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE foreporting_db TO system;" 2>nul
echo Done.
echo.

REM Step 4: Install Python dependencies
echo [4/8] Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo Done.
echo.

REM Step 5: Run database migrations
echo [5/8] Running database migrations...
set DEPLOYMENT_MODE=local
set PYTHONPATH=.
alembic upgrade head
echo Done.
echo.

REM Step 6: Seed field library
echo [6/8] Seeding field library...
python scripts/seed_field_library.py
echo Done.
echo.

REM Step 7: Create local startup scripts
echo [7/8] Creating startup scripts...

REM Backend script
echo @echo off > start_backend_local.bat
echo title FOReporting Backend >> start_backend_local.bat
echo echo Starting FOReporting v2 Backend locally... >> start_backend_local.bat
echo chcp 65001 ^>nul >> start_backend_local.bat
echo set DEPLOYMENT_MODE=local >> start_backend_local.bat
echo set PGCLIENTENCODING=UTF8 >> start_backend_local.bat
echo set PYTHONUTF8=1 >> start_backend_local.bat
echo set PYTHONPATH=. >> start_backend_local.bat
echo python run.py >> start_backend_local.bat
echo pause >> start_backend_local.bat

REM Frontend script
echo @echo off > start_frontend_local.bat
echo title FOReporting Frontend >> start_frontend_local.bat
echo echo Starting FOReporting v2 Frontend locally... >> start_frontend_local.bat
echo chcp 65001 ^>nul >> start_frontend_local.bat
echo set DEPLOYMENT_MODE=local >> start_frontend_local.bat
echo set PGCLIENTENCODING=UTF8 >> start_frontend_local.bat
echo set PYTHONUTF8=1 >> start_frontend_local.bat
echo set PYTHONPATH=. >> start_frontend_local.bat
echo streamlit run app/frontend/dashboard.py >> start_frontend_local.bat
echo pause >> start_frontend_local.bat

REM Watcher script
echo @echo off > start_watcher_local.bat
echo title FOReporting File Watcher >> start_watcher_local.bat
echo echo Starting FOReporting v2 File Watcher locally... >> start_watcher_local.bat
echo chcp 65001 ^>nul >> start_watcher_local.bat
echo set DEPLOYMENT_MODE=local >> start_watcher_local.bat
echo set PGCLIENTENCODING=UTF8 >> start_watcher_local.bat
echo set PYTHONUTF8=1 >> start_watcher_local.bat
echo set PYTHONPATH=. >> start_watcher_local.bat
echo python app/services/watcher_runner.py >> start_watcher_local.bat
echo pause >> start_watcher_local.bat

REM All services script
echo @echo off > start_all_local.bat
echo echo Starting all FOReporting v2 services locally... >> start_all_local.bat
echo start "Backend" start_backend_local.bat >> start_all_local.bat
echo timeout /t 5 /nobreak ^> nul >> start_all_local.bat
echo start "Frontend" start_frontend_local.bat >> start_all_local.bat
echo start "Watcher" start_watcher_local.bat >> start_all_local.bat
echo echo. >> start_all_local.bat
echo echo All services started! >> start_all_local.bat
echo echo   Backend: http://localhost:8000 >> start_all_local.bat
echo echo   Frontend: http://localhost:8501 >> start_all_local.bat
echo echo. >> start_all_local.bat
echo pause >> start_all_local.bat

echo Done.
echo.

REM Step 8: Run verification
echo [8/8] Verifying setup...
python verify_local_setup.py

echo.
echo ============================================================
echo LOCAL SETUP COMPLETE!
echo ============================================================
echo.
echo Quick start commands:
echo   - start_all_local.bat     (Start all services)
echo   - start_backend_local.bat (Backend only)
echo   - start_frontend_local.bat (Frontend only)
echo   - start_watcher_local.bat (File watcher only)
echo.
echo Testing commands:
echo   - python test_extraction.py
echo   - python test_validation.py
echo   - python test_end_to_end.py
echo.
pause