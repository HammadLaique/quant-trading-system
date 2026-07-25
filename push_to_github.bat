@echo off
chcp 65001 > nul
title Push Quant Trading System to GitHub
echo ================================================================
echo   Pushing Quant Trading System to your GitHub Repository
echo ================================================================
echo.
echo Please make sure you have:
echo   1. Opened github.com in your browser
echo   2. Created a new Private repository named "quant-trading-system"
echo.
set /p REPO_URL="Enter your GitHub Repository URL (e.g. https://github.com/your-username/quant-trading-system.git): "
echo.
echo Setting remote repository...
D:\quant_trading_system\mingit\cmd\git.exe remote remove origin 2>nul
D:\quant_trading_system\mingit\cmd\git.exe remote add origin %REPO_URL%
echo.
echo Pushing to GitHub...
echo.
echo Note: A Windows popup may appear asking you to log into GitHub.
echo Click "Sign in with your browser" and click "Authorize" in your browser.
echo.
D:\quant_trading_system\mingit\cmd\git.exe push -u origin main
echo.
echo ================================================================
echo   Pushed successfully!
echo   You can now connect this GitHub repository to Render and Vercel.
echo ================================================================
pause
