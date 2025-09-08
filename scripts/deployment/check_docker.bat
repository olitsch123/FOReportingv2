@echo off
echo Checking Docker status...
echo.

docker --version
if %errorlevel% neq 0 (
    echo ERROR: Docker is not installed or not in PATH
    exit /b 1
)

echo.
echo Checking Docker Compose...
docker-compose --version

echo.
echo Checking running containers...
docker ps

echo.
echo Starting containers...
docker-compose up -d

echo.
echo Waiting 10 seconds for containers to start...
timeout /t 10 /nobreak > nul

echo.
echo Checking container status...
docker-compose ps

echo.
echo Testing PostgreSQL connection...
docker-compose exec postgres psql -U system -d foreporting_db -c "SELECT version();"

echo.
echo Testing backend health...
curl http://localhost:8000/health

echo.
pause