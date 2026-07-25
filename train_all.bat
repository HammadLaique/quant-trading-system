@echo off
chcp 65001 > nul
title Quant Trading System - Model Training
echo ================================================================
echo   Pre-Training ML Models for Top 100 Coins
echo   (Run this ONCE before starting the trading system)
echo ================================================================
echo.
echo This will:
echo   1. Fetch 90 days of historical 1-min data from Binance
echo   2. Engineer features (EMA20/200, ATR, MACD, 5m Filter, etc.)
echo   3. Label trade outcomes (1:2 R:R with trailing SL)
echo   4. Apply SMOTE to balance Win/Loss classes
echo   5. Train RandomForest classifier per coin
echo   6. Save models to D:\quant_trading_system\backend\ml\models\
echo.
echo Training 100 coins in batches of 3. This takes ~2-3 hours.
echo You can press Ctrl+C to stop. Partially trained coins will be
echo skipped on re-run (already saved models are preserved).
echo.
echo ================================================================
echo Press any key to start training, or Ctrl+C to cancel...
pause > nul
echo.
echo Starting training...
cd /d D:\quant_trading_system
.\venv\Scripts\python.exe -X utf8 scripts\train_models.py
echo.
echo ================================================================
echo Training complete! You can now launch the trading system.
echo Run: start_all.bat
echo ================================================================
pause
