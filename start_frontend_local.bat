@echo off 
title FOReporting Frontend 
echo Starting FOReporting v2 Frontend locally... 
chcp 65001 >nul 
set DEPLOYMENT_MODE=local 
set PGCLIENTENCODING=UTF8 
set PYTHONUTF8=1 
set PYTHONPATH=. 
streamlit run app/frontend/dashboard.py 
pause 
