@echo off
echo ==========================================
echo FOReporting v2 Production Deployment Test
echo ==========================================
echo.

echo 1. Testing production Docker configuration...
docker-compose -f docker-compose.prod.yml config

echo.
echo 2. Building production images...
docker-compose -f docker-compose.prod.yml build

echo.
echo 3. Starting production containers...
docker-compose -f docker-compose.prod.yml up -d

echo.
echo 4. Waiting for services to start...
timeout /t 20 /nobreak > nul

echo.
echo 5. Checking production container status...
docker-compose -f docker-compose.prod.yml ps

echo.
echo 6. Testing production health endpoints...
echo.
echo Backend Health:
curl -s http://localhost:8000/health | python -m json.tool

echo.
echo PE Health:
curl -s http://localhost:8000/pe/health | python -m json.tool

echo.
echo Frontend Health (should return HTML):
curl -s http://localhost:8501 | findstr /i "streamlit"

echo.
echo 7. Checking production logs for errors...
docker-compose -f docker-compose.prod.yml logs backend --tail 20

echo.
echo 8. Running production database migration check...
docker-compose -f docker-compose.prod.yml exec backend alembic current

echo.
echo 9. Testing file watcher service...
docker-compose -f docker-compose.prod.yml logs watcher --tail 10

echo.
echo 10. Checking resource usage...
docker stats --no-stream

echo.
echo ==========================================
echo Production Deployment Test Complete!
echo.
echo To stop production:
echo docker-compose -f docker-compose.prod.yml down
echo.
echo For continuous monitoring:
echo docker-compose -f docker-compose.prod.yml logs -f
echo ==========================================
pause