@echo off
chcp 65001 > nul
title Quant Trading System Launcher
echo =======================================================
echo   Launching Autonomous Quant Trading System
echo =======================================================
echo.
echo [1/2] Starting Python FastAPI Backend (UTF-8 mode)...
start "Quant Trading Backend" cmd /k "chcp 65001 && cd /d D:\quant_trading_system\backend && ..\venv\Scripts\python.exe -X utf8 main.py"

echo.
echo [2/2] Starting Next.js Dashboard...
start "Quant Trading Dashboard" cmd /k "cd /d D:\quant_trading_system\frontend && npm.cmd run dev"

echo.
echo =======================================================
echo   Both servers launched!
echo.
echo   Dashboard (Frontend) : http://localhost:3000
echo   Backend API Docs     : http://localhost:8000/docs
echo   Live Logs            : D:\quant_trading_system\logs
echo =======================================================
pause
