@echo off
echo ============================================================
echo FOReporting v2 - Complete Local Setup for Windows
echo ============================================================
echo.

REM Step 1: Stop any Docker containers
echo Step 1: Ensuring Docker containers are stopped...
docker-compose down 2>nul
echo.

REM Step 2: Check Python
echo Step 2: Checking Python installation...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python not found! Please install Python 3.12
    pause
    exit /b 1
)

REM Step 3: Check .env file
echo.
echo Step 3: Checking .env configuration...
if not exist .env (
    echo Creating .env from env_example.txt...
    copy env_example.txt .env
)

REM Update DATABASE_URL for local
echo Updating DATABASE_URL for localhost...
powershell -Command "(Get-Content .env) -replace '@postgres:5432', '@localhost:5432' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'DEPLOYMENT_MODE=docker', 'DEPLOYMENT_MODE=local' | Set-Content .env"

REM Add DEPLOYMENT_MODE if not exists
findstr /C:"DEPLOYMENT_MODE" .env >nul
if %errorlevel% neq 0 (
    echo DEPLOYMENT_MODE=local >> .env
)

REM Step 4: Check PostgreSQL
echo.
echo Step 4: Checking local PostgreSQL...
psql -h localhost -p 5432 -U postgres -c "SELECT version();" 2>nul
if %errorlevel% neq 0 (
    echo.
    echo ERROR: PostgreSQL is not running locally!
    echo.
    echo Please install PostgreSQL:
    echo 1. Download from https://www.postgresql.org/download/windows/
    echo 2. Install with default settings
    echo 3. Remember the postgres user password
    echo 4. Add PostgreSQL bin folder to PATH
    echo.
    echo Or if already installed, start the service:
    echo   net start postgresql-x64-15  (or your version)
    echo.
    pause
    exit /b 1
)

REM Step 5: Create database
echo.
echo Step 5: Setting up database...
echo Creating user 'system'...
psql -h localhost -p 5432 -U postgres -c "CREATE USER system WITH PASSWORD 'BreslauerPlatz4' CREATEDB SUPERUSER;" 2>nul
if %errorlevel% equ 0 (
    echo User created successfully
) else (
    echo User might already exist
)

echo Creating database 'foreporting_db'...
psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE foreporting_db OWNER system ENCODING 'UTF8';" 2>nul
if %errorlevel% equ 0 (
    echo Database created successfully
) else (
    echo Database might already exist
)

REM Step 6: Install Python dependencies
echo.
echo Step 6: Installing Python dependencies...
pip install --upgrade pip
pip install -r requirements.txt

REM Step 7: Run database migrations
echo.
echo Step 7: Running database migrations...
set DEPLOYMENT_MODE=local
alembic upgrade head

REM Step 8: Create startup scripts
echo.
echo Step 8: Creating startup scripts...

REM Backend startup script
echo @echo off > start_backend_local.bat
echo echo Starting FOReporting v2 Backend locally... >> start_backend_local.bat
echo set DEPLOYMENT_MODE=local >> start_backend_local.bat
echo python run.py >> start_backend_local.bat
echo pause >> start_backend_local.bat

REM Frontend startup script  
echo @echo off > start_frontend_local.bat
echo echo Starting FOReporting v2 Frontend locally... >> start_frontend_local.bat
echo set DEPLOYMENT_MODE=local >> start_frontend_local.bat
echo streamlit run app/frontend/dashboard.py >> start_frontend_local.bat
echo pause >> start_frontend_local.bat

REM File watcher startup script
echo @echo off > start_watcher_local.bat
echo echo Starting FOReporting v2 File Watcher locally... >> start_watcher_local.bat
echo set DEPLOYMENT_MODE=local >> start_watcher_local.bat
echo python app/services/watcher_runner.py >> start_watcher_local.bat
echo pause >> start_watcher_local.bat

REM All-in-one startup script
echo @echo off > start_all_local.bat
echo echo Starting all FOReporting v2 services locally... >> start_all_local.bat
echo start "Backend" start_backend_local.bat >> start_all_local.bat
echo timeout /t 5 /nobreak ^> nul >> start_all_local.bat
echo start "Frontend" start_frontend_local.bat >> start_all_local.bat
echo start "Watcher" start_watcher_local.bat >> start_all_local.bat
echo echo All services started! >> start_all_local.bat
echo pause >> start_all_local.bat

echo.
echo ============================================================
echo LOCAL SETUP COMPLETE!
echo ============================================================
echo.
echo Created startup scripts:
echo   - start_backend_local.bat  (API on http://localhost:8000)
echo   - start_frontend_local.bat (UI on http://localhost:8501)
echo   - start_watcher_local.bat  (File monitoring)
echo   - start_all_local.bat      (Start everything)
echo.
echo To start all services: run start_all_local.bat
echo.
echo To test individual components:
echo   python test_end_to_end.py
echo   python test_extraction.py
echo.
pause