"""
EMA + ML Strategy.
The main trading strategy based on:
- EMA20/EMA200 crossover signal
- 5-minute EMA200 higher-timeframe trend filter
- RandomForest ML gate (win probability threshold)
- 1:2 Risk-Reward ratio with breakeven trailing stop
"""

import asyncio
import pandas as pd
from collections import deque
from typing import Optional, Deque
from loguru import logger

from config import settings
from features.engineering import calculate_features, get_live_features, get_live_signal
from ml.predictor import predictor
from ml.trainer import train_model_for_symbol, model_exists
from data.binance_client import fetch_klines_full
from core.order_manager import order_manager
from core.portfolio import portfolio


class EMAMLStrategy:
    """
    Per-symbol strategy instance.
    Maintains a rolling buffer of 1-minute candles and runs on each close.
    """

    # Number of 1m candles to keep in buffer (enough for EMA200 + 5m EMA200)
    BUFFER_SIZE = 1500

    def __init__(self, symbol: str, leverage: int = None):
        self.symbol = symbol
        self.leverage = leverage or settings.DEFAULT_LEVERAGE
        self.buffer: Deque[dict] = deque(maxlen=self.BUFFER_SIZE)
        self.initialized = False
        self.model_ready = False
        self.last_signal = 0

    async def initialize(self):
        """
        Fetch historical data, train (or load) the model,
        and pre-fill the candle buffer.
        """
        logger.info(f"[{self.symbol}] Initializing strategy...")

        # ── Step 1: Check if model exists ──────────────────────────────
        has_model = model_exists(self.symbol)
        fetch_days = 2 if has_model else settings.HISTORICAL_DAYS

        # ── Step 2: Fetch historical data ──────────────────────────────
        try:
            df_hist = await fetch_klines_full(
                self.symbol,
                interval=settings.TIMEFRAME,
                days=fetch_days,
            )
        except Exception as e:
            logger.error(f"[{self.symbol}] Failed to fetch historical data: {e}")
            return

        if df_hist.empty or len(df_hist) < 500:
            logger.warning(f"[{self.symbol}] Insufficient historical data. Skipping.")
            return

        # ── Step 3: Train or load ML model ─────────────────────────────
        if not has_model:
            logger.info(f"[{self.symbol}] No model found. Training from scratch...")
            result = train_model_for_symbol(df_hist, self.symbol)
            self.model_ready = result is not None
        else:
            self.model_ready = predictor.load(self.symbol)

        if not self.model_ready:
            logger.warning(f"[{self.symbol}] Strategy will run WITHOUT ML filter (signal-only mode).")

        # ── Step 4: Pre-fill buffer with recent candles ─────────────────
        recent = df_hist.tail(self.BUFFER_SIZE)
        for ts, row in recent.iterrows():
            self.buffer.append({
                "open_time": ts,
                "Open": row["Open"],
                "High": row["High"],
                "Low": row["Low"],
                "Close": row["Close"],
                "Volume": row["Volume"],
            })

        self.initialized = True
        logger.success(f"[{self.symbol}] [OK] Strategy ready. Buffer: {len(self.buffer)} candles. Model: {self.model_ready}")

    async def on_candle(self, candle: dict):
        """
        Called on every incoming kline event from Binance WebSocket.
        Only processes logic on closed candles.
        """
        if not self.initialized:
            return

        # Always update SL/TP checks with latest price
        current_price = candle["close"]
        await order_manager.on_price_tick(
            self.symbol, current_price, is_closed=candle["is_closed"]
        )

        # Only process closed candles for signal generation
        if not candle["is_closed"]:
            return

        # Add closed candle to buffer
        self.buffer.append({
            "open_time": candle["open_time"],
            "Open": candle["open"],
            "High": candle["high"],
            "Low": candle["low"],
            "Close": candle["close"],
            "Volume": candle["volume"],
        })

        # Need at least EMA_SLOW + some bars
        if len(self.buffer) < settings.EMA_SLOW + 50:
            return

        # Build DataFrame from buffer
        df = pd.DataFrame(list(self.buffer))
        df.set_index("open_time", inplace=True)
        df.index = pd.DatetimeIndex(df.index)

        # Calculate features
        try:
            df = calculate_features(df)
        except Exception as e:
            logger.error(f"[{self.symbol}] Feature calc error: {e}")
            return

        # Get current signal
        signal = get_live_signal(df)

        # Skip if no signal or same as previous
        if signal == 0:
            return

        # Avoid duplicate signals (only act once per new crossover)
        if signal == self.last_signal:
            return

        self.last_signal = signal

        # Check if already has a position in same direction
        existing = portfolio.get_positions_by_symbol(self.symbol)
        if any(p.direction == signal for p in existing):
            logger.debug(f"[{self.symbol}] Already have {signal} position. Skipping.")
            return

        # ── ML Gate ────────────────────────────────────────────────────
        win_prob = 0.5
        should_trade = True  # Default: trade without ML if no model

        if self.model_ready:
            features = get_live_features(df)
            win_prob, should_trade = predictor.predict(self.symbol, features)
            logger.debug(f"[{self.symbol}] Signal: {signal} | Win prob: {win_prob:.3f} | Trade: {should_trade}")

        if not should_trade:
            logger.debug(f"[{self.symbol}] ML rejected trade (prob={win_prob:.3f} < {settings.WIN_PROB_THRESHOLD})")
            return

        # ── Execute Trade ───────────────────────────────────────────────
        direction_str = "LONG [LONG]" if signal == 1 else "SHORT [SHORT]"
        logger.info(f"[{self.symbol}] [SIGNAL] {direction_str} signal | Price: {current_price:.4f} | Win prob: {win_prob:.3f}")

        order_manager.open_trade(
            symbol=self.symbol,
            direction=signal,
            entry_price=current_price,
            atr=float(df["ATR"].iloc[-1]),
            df_slice=df,
            leverage=self.leverage,
            win_probability=win_prob,
        )

    def get_status(self) -> dict:
        """Return current strategy status."""
        return {
            "symbol": self.symbol,
            "initialized": self.initialized,
            "model_ready": self.model_ready,
            "leverage": self.leverage,
            "buffer_size": len(self.buffer),
            "last_signal": self.last_signal,
            "open_positions": len(portfolio.get_positions_by_symbol(self.symbol)),
        }

