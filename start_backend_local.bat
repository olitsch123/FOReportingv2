@echo off 
title FOReporting Backend 
echo Starting FOReporting v2 Backend locally... 
chcp 65001 >nul 
set DEPLOYMENT_MODE=local 
set PGCLIENTENCODING=UTF8 
set PYTHONUTF8=1 
set PYTHONPATH=. 
python run.py 
pause 
