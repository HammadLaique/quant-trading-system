"""
Feature Engineering Pipeline.
Calculates technical indicators and generates trade signals:
- EMA20, EMA200, ATR, MACD
- Price Momentum, Volatility, EMA Slope
- Bulletproof Signal Generation (Long / Short)
"""

import numpy as np
import pandas as pd
from loguru import logger
from config import settings


def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given an OHLCV DataFrame, compute all features and signals.
    """
    if len(df) < 30:
        return df

    df = df.copy()

    # ── 1. Exponential Moving Averages ────────────────────────────────────
    df["EMA20"] = df["Close"].ewm(span=settings.EMA_FAST, adjust=False).mean()
    df["EMA200"] = df["Close"].ewm(span=settings.EMA_SLOW, adjust=False).mean()

    # Clean initial NaN/0 in EMA200
    df["EMA200"].replace(0, np.nan, inplace=True)
    df["EMA200"].fillna(df["EMA20"], inplace=True)

    # ── 2. ATR (Average True Range) ───────────────────────────────────────
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift(1)).abs()
    low_close = (df["Low"] - df["Close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR"] = true_range.ewm(span=settings.ATR_PERIOD, adjust=False).mean()

    # ── 3. EMA Distance ───────────────────────────────────────────────────
    df["EMA_Distance"] = df["EMA20"] - df["EMA200"]

    # ── 4. MACD ───────────────────────────────────────────────────────────
    ema_fast = df["Close"].ewm(span=settings.MACD_FAST, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=settings.MACD_SLOW, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_Signal"] = df["MACD"].ewm(span=settings.MACD_SIGNAL, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # ── 5. Momentum & Volatility ──────────────────────────────────────────
    df["Price_Momentum"] = df["Close"].pct_change(5).fillna(0)
    df["Volatility"] = (df["ATR"] / df["Close"]).fillna(0)
    df["EMA_Slope"] = df["EMA20"].diff(5).fillna(0)

    # ── 6. Signal Generation ──────────────────────────────────────────────
    df = _generate_signals(df)

    # ── 7. Clean up NaN/Inf ───────────────────────────────────────────────
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.ffill(inplace=True)
    df.fillna(0, inplace=True)

    return df


def _generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate clean, actionable trade signals:
    - LONG (+1) : EMA20 >= EMA200 AND MACD_Hist >= 0
    - SHORT (-1): EMA20 <= EMA200 AND MACD_Hist <= 0
    - Crossover flips are prioritized.
    """
    above_200 = df["EMA20"] >= df["EMA200"]

    # Instant Crossover Detection
    cross_up = above_200 & ~above_200.shift(1).fillna(False)
    cross_down = ~above_200 & above_200.shift(1).fillna(True)

    # Trend Momentum Alignment
    bullish_trend = above_200 & (df["MACD_Hist"] >= 0)
    bearish_trend = ~above_200 & (df["MACD_Hist"] <= 0)

    df["Signal"] = 0
    df.loc[cross_up | bullish_trend, "Signal"] = 1
    df.loc[cross_down | bearish_trend, "Signal"] = -1

    # Signal_Filtered (Ready for execution)
    df["Signal_Filtered"] = df["Signal"]

    return df


def label_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """Used for model training data labeling."""
    df = df.copy()
    df["Outcome_Filtered"] = np.nan
    return df


def get_live_features(df: pd.DataFrame) -> dict:
    """Extract the latest feature vector for model scoring."""
    latest = df.iloc[-1]
    return {feat: latest.get(feat, 0.0) for feat in settings.ML_FEATURES}


def get_live_signal(df: pd.DataFrame) -> int:
    """Get the filtered signal (+1, -1, or 0) from the latest bar."""
    if df.empty or "Signal_Filtered" not in df.columns:
        return 0
    return int(df["Signal_Filtered"].iloc[-1])
