@echo off
title LOGIX-ETA Intelligent Logistics Control Tower
cd /d "%~dp0"

echo ====================================================================
echo   Starting LOGIX-ETA System (Dashboard + API Backend)...
echo ====================================================================

python start_all.py

pause
