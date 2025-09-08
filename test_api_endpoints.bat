@echo off
echo ===========================================
echo Testing FOReporting v2 API Endpoints
echo ===========================================
echo.

echo 1. Starting Docker containers...
docker-compose up -d
timeout /t 10 /nobreak > nul

echo.
echo 2. Checking container status...
docker-compose ps

echo.
echo 3. Testing Health Endpoint...
curl -s http://localhost:8000/health | python -m json.tool

echo.
echo 4. Testing PE Health Endpoint...
curl -s http://localhost:8000/pe/health | python -m json.tool

echo.
echo 5. Testing Documents Endpoint...
curl -s http://localhost:8000/documents | python -m json.tool

echo.
echo 6. Testing PE Capital Account Series (will fail without valid fund_id)...
curl -s http://localhost:8000/pe/capital-account-series/550e8400-e29b-41d4-a716-446655440000 | python -m json.tool

echo.
echo 7. Creating test data in database...
docker-compose exec postgres psql -U system -d foreporting_db -c "INSERT INTO pe_fund_master (fund_id, fund_code, fund_name) VALUES ('550e8400-e29b-41d4-a716-446655440000', 'TEST001', 'Test Fund') ON CONFLICT DO NOTHING;"

docker-compose exec postgres psql -U system -d foreporting_db -c "INSERT INTO pe_capital_account (account_id, fund_id, investor_id, as_of_date, beginning_balance, ending_balance, total_commitment) VALUES ('660e8400-e29b-41d4-a716-446655440000', '550e8400-e29b-41d4-a716-446655440000', 'test-investor-001', '2023-12-31', 35000000, 40700000, 50000000) ON CONFLICT DO NOTHING;"

echo.
echo 8. Testing PE Capital Account Series with test data...
curl -s http://localhost:8000/pe/capital-account-series/550e8400-e29b-41d4-a716-446655440000 | python -m json.tool

echo.
echo 9. Testing PE RAG endpoint...
curl -X POST http://localhost:8000/pe/rag -H "Content-Type: application/json" -d "{\"query\": \"What is the NAV?\"}" -s | python -m json.tool

echo.
echo 10. Checking backend logs for errors...
docker-compose logs backend --tail 20

echo.
echo ===========================================
echo API testing complete!
echo.
echo If any endpoints failed:
echo 1. Check Docker is running: docker ps
echo 2. Check backend logs: docker-compose logs backend
echo 3. Verify database migration: docker-compose exec backend alembic current
echo ===========================================
pause