@echo off
title LOGIX-ETA Streamlit Dashboard
cd /d "%~dp0"

echo ====================================================================
echo   Starting LOGIX-ETA Streamlit Dashboard...
echo ====================================================================

python -m streamlit run dashboard/app.py --server.port 8501

pause
