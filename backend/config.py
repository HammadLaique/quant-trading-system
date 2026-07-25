"""
Global configuration for the Quant Trading System.
All settings are centralized here. Edit this file to tune the system.
"""

import os
from pydantic_settings import BaseSettings
from typing import List


class TradingConfig(BaseSettings):
    # ─── SERVER ──────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"  # CORS origin

    # ─── DEMO ACCOUNT ────────────────────────────────────────
    INITIAL_BALANCE_USDT: float = 100_000.0       # Starting paper money
    MAX_LEVERAGE: int = 50                         # Max allowed leverage
    DEFAULT_LEVERAGE: int = 10                     # Default leverage per trade
    RISK_PER_TRADE_PERCENT: float = 1.0            # % of balance risked per trade (before leverage)
    MAX_OPEN_TRADES: int = 10                      # Max simultaneous positions
    MAX_DRAWDOWN_PERCENT: float = 20.0             # Emergency stop if drawdown exceeds this

    # ─── STRATEGY ────────────────────────────────────────────
    TIMEFRAME: str = "1m"                          # Primary timeframe
    HIGHER_TIMEFRAME: str = "5m"                  # HTF EMA filter
    EMA_FAST: int = 20
    EMA_SLOW: int = 200
    EMA_HTF: int = 200                             # EMA period on 5m
    ATR_PERIOD: int = 14
    RSI_PERIOD: int = 14
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    SL_LOOKBACK: int = 20                          # Bars to look back for SL
    RR_RATIO: float = 2.0                          # Risk:Reward ratio (1:2)
    MAX_BARS_LOOKFORWARD: int = 200
    WIN_PROB_THRESHOLD: float = 0.52               # Minimum ML confidence to trade

    # ─── ML MODEL ────────────────────────────────────────────
    RF_N_ESTIMATORS: int = 300
    RF_MAX_DEPTH: int = 8
    HISTORICAL_DAYS: int = 90                      # Days of history for training
    TRAIN_TEST_SPLIT: float = 0.70
    # Docker WORKDIR is /app (= the backend folder), so models are at /app/ml/models
    # Locally on Windows, backend is a subdirectory, so models are at backend/ml/models
    MODELS_DIR: str = os.environ.get(
        "MODELS_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ml", "models")
    )

    # ─── BINANCE ─────────────────────────────────────────────
    BINANCE_REST_URL: str = "https://api.binance.com"
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443"
    TOP_N_COINS: int = 100                         # How many coins to track
    QUOTE_ASSET: str = "USDT"                      # Base quote currency

    # ─── DATABASE ────────────────────────────────────────────
    DB_PATH: str = os.environ.get(
        "DB_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "trading.db")
    )
    DB_URL: str = os.environ.get("DB_URL", "")

    # ─── FEATURES USED BY ML MODEL ───────────────────────────
    ML_FEATURES: List[str] = [
        "EMA20", "EMA200", "ATR", "MACD_Hist",
        "ema_200_5m", "Price_Momentum", "Volatility",
        "EMA_Slope", "MACD_Divergence"
    ]

    class Config:
        # Look for .env in the same directory as config.py, then parent
        _here = os.path.dirname(os.path.abspath(__file__))
        _parent = os.path.dirname(_here)
        env_file = (
            os.path.join(_parent, ".env")
            if os.path.exists(os.path.join(_parent, ".env"))
            else os.path.join(_here, ".env")
        )
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton instance used throughout the app
settings = TradingConfig()

