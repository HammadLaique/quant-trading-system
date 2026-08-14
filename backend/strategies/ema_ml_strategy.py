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
import numpy as np
from collections import deque
from typing import Optional, Deque
from loguru import logger

from config import settings
from features.engineering import calculate_features, get_live_features, get_live_signal
from ml.predictor import predictor
from ml.trainer import train_model_for_symbol, model_exists
from data.binance_client import fetch_klines_full, get_ticker_price
from core.order_manager import order_manager
from core.portfolio import portfolio


class EMAMLStrategy:
    """
    Per-symbol strategy instance.
    Maintains a rolling buffer of 1-minute candles and runs on each close.
    """

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
        Fetch historical data (or generate synthetic buffer), load ML model,
        and set strategy initialized state unconditionally.
        """
        logger.info(f"[{self.symbol}] Initializing strategy...")

        # ── Step 1: Check if model exists ──────────────────────────────
        has_model = model_exists(self.symbol)
        fetch_days = 2

        # ── Step 2: Fetch historical data ──────────────────────────────
        df_hist = pd.DataFrame()
        try:
            df_hist = await fetch_klines_full(
                self.symbol,
                interval=settings.TIMEFRAME,
                days=fetch_days,
            )
        except Exception as e:
            logger.warning(f"[{self.symbol}] Could not fetch REST klines ({e}). Using synthetic buffer.")

        # If REST fetch returns empty/insufficient candles, generate synthetic historical buffer
        if df_hist.empty or len(df_hist) < 300:
            logger.warning(f"[{self.symbol}] Generating fallback candle buffer...")
            df_hist = await self._generate_fallback_buffer()

        # ── Step 3: Train or load ML model ─────────────────────────────
        if has_model:
            self.model_ready = predictor.load(self.symbol)
        elif not df_hist.empty and len(df_hist) >= 500:
            logger.info(f"[{self.symbol}] No model found. Training from scratch...")
            result = train_model_for_symbol(df_hist, self.symbol)
            self.model_ready = result is not None

        if not self.model_ready:
            logger.info(f"[{self.symbol}] Running in signal-only mode (EMA20/200 crossover).")

        # ── Step 4: Pre-fill candle buffer ─────────────────────────────
        recent = df_hist.tail(self.BUFFER_SIZE)
        for ts, row in recent.iterrows():
            self.buffer.append({
                "open_time": ts,
                "Open": float(row["Open"]),
                "High": float(row["High"]),
                "Low": float(row["Low"]),
                "Close": float(row["Close"]),
                "Volume": float(row["Volume"]),
            })

        # Set initialized unconditionally so WebSocket streams connect immediately
        self.initialized = True
        logger.success(f"[{self.symbol}] [OK] Strategy ready. Buffer: {len(self.buffer)} candles. Model: {self.model_ready}")

    async def _generate_fallback_buffer(self) -> pd.DataFrame:
        """Generate a 1,500 candle synthetic buffer based on current market price."""
        base_price = await get_ticker_price(self.symbol)
        now = pd.Timestamp.now(tz="UTC")
        timestamps = [now - pd.Timedelta(minutes=i) for i in range(self.BUFFER_SIZE, 0, -1)]

        # Generate realistic random walk around current price
        noise = np.random.normal(0, 0.0008, self.BUFFER_SIZE)
        price_series = base_price * np.exp(np.cumsum(noise))

        rows = []
        for ts, price in zip(timestamps, price_series):
            high = price * (1 + abs(np.random.normal(0, 0.0005)))
            low = price * (1 - abs(np.random.normal(0, 0.0005)))
            rows.append({
                "open_time": ts,
                "Open": price,
                "High": max(price, high),
                "Low": min(price, low),
                "Close": price,
                "Volume": float(np.random.uniform(10, 100)),
            })

        df = pd.DataFrame(rows)
        df.set_index("open_time", inplace=True)
        return df

    async def on_candle(self, candle: dict):
        """
        Called on every incoming kline event from Binance WebSocket.
        Checks exits on live price ticks and evaluates crossover signals on closed candles.
        """
        if not self.initialized:
            return

        current_price = candle["close"]
        await order_manager.on_price_tick(
            self.symbol, current_price, is_closed=candle["is_closed"]
        )

        if not candle["is_closed"]:
            return

        self.buffer.append({
            "open_time": candle["open_time"],
            "Open": candle["open"],
            "High": candle["high"],
            "Low": candle["low"],
            "Close": candle["close"],
            "Volume": candle["volume"],
        })

        if len(self.buffer) < settings.EMA_SLOW + 20:
            return

        df = pd.DataFrame(list(self.buffer))
        df.set_index("open_time", inplace=True)
        df.index = pd.DatetimeIndex(df.index)

        try:
            df = calculate_features(df)
        except Exception as e:
            logger.error(f"[{self.symbol}] Feature calc error: {e}")
            return

        signal = get_live_signal(df)

        if signal == 0 or signal == self.last_signal:
            return

        self.last_signal = signal

        existing = portfolio.get_positions_by_symbol(self.symbol)
        if any(p.direction == signal for p in existing):
            return

        # ── ML Gate ────────────────────────────────────────────────────
        win_prob = 0.5
        should_trade = True

        if self.model_ready:
            features = get_live_features(df)
            win_prob, should_trade = predictor.predict(self.symbol, features)

        if not should_trade:
            logger.debug(f"[{self.symbol}] ML rejected trade (prob={win_prob:.3f} < {settings.WIN_PROB_THRESHOLD})")
            return

        # ── Execute Trade ───────────────────────────────────────────────
        direction_str = "LONG" if signal == 1 else "SHORT"
        logger.info(f"[{self.symbol}] [SIGNAL] {direction_str} | Price: {current_price:.4f} | Win prob: {win_prob:.3f}")

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
        return {
            "symbol": self.symbol,
            "initialized": self.initialized,
            "model_ready": self.model_ready,
            "leverage": self.leverage,
            "buffer_size": len(self.buffer),
            "last_signal": self.last_signal,
            "open_positions": len(portfolio.get_positions_by_symbol(self.symbol)),
        }
