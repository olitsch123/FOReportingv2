@echo off 
title FOReporting File Watcher 
echo Starting FOReporting v2 File Watcher locally... 
chcp 65001 >nul 
set DEPLOYMENT_MODE=local 
set PGCLIENTENCODING=UTF8 
set PYTHONUTF8=1 
set PYTHONPATH=. 
python app/services/watcher_runner.py 
pause 
