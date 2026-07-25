"""
Feature Engineering Pipeline.
Calculates all technical indicators used by the ML model and signal generator.
Matches exactly the feature set from the original strategy:
  EMA20, EMA200, ATR, MACD_Hist, ema_200_5m, Price_Momentum, Volatility, EMA_Slope, MACD_Divergence
"""

import numpy as np
import pandas as pd
from loguru import logger
from config import settings


def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a clean OHLCV DataFrame (indexed by datetime), compute all features.
    Returns the same DataFrame with new feature columns added.
    """
    if len(df) < settings.EMA_SLOW + 50:
        logger.warning(f"Not enough data ({len(df)} rows) for feature calculation. Need >{settings.EMA_SLOW + 50}")
        return df

    df = df.copy()

    # ── 1. Exponential Moving Averages ────────────────────────────────────
    df["EMA20"] = df["Close"].ewm(span=settings.EMA_FAST, adjust=False).mean()
    df["EMA200"] = df["Close"].ewm(span=settings.EMA_SLOW, adjust=False).mean()

    # ── 2. ATR (Average True Range) ───────────────────────────────────────
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift(1)).abs()
    low_close = (df["Low"] - df["Close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR"] = true_range.ewm(span=settings.ATR_PERIOD, adjust=False).mean()

    # ── 3. Volume Change ──────────────────────────────────────────────────
    df["Volume_Change"] = df["Volume"].pct_change()

    # ── 4. EMA Distance ───────────────────────────────────────────────────
    df["EMA_Distance"] = df["EMA20"] - df["EMA200"]

    # ── 5. MACD ───────────────────────────────────────────────────────────
    ema_fast = df["Close"].ewm(span=settings.MACD_FAST, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=settings.MACD_SLOW, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_Signal"] = df["MACD"].ewm(span=settings.MACD_SIGNAL, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # ── 6. 5-Minute EMA200 Filter ─────────────────────────────────────────
    df["ema_200_5m"] = _calculate_htf_ema200(df)

    # ── 7. Momentum Features (v2) ─────────────────────────────────────────
    df["Price_Momentum"] = df["Close"].pct_change(5)
    df["Volatility"] = df["ATR"] / df["Close"]
    df["EMA_Slope"] = df["EMA20"].diff(5)
    df["MACD_Divergence"] = _calculate_macd_divergence(df).astype(float)

    # ── 8. Signal Generation ──────────────────────────────────────────────
    df = _generate_signals(df)

    # ── 9. Clean up NaN/Inf ───────────────────────────────────────────────
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.ffill(inplace=True)
    df.fillna(0, inplace=True)

    return df


def _calculate_htf_ema200(df_1m: pd.DataFrame) -> pd.Series:
    """
    Resample 1-minute data to 5-minute, calculate EMA200,
    then forward-fill back to 1-minute index.
    """
    # Resample to 5m OHLCV
    df_5m = df_1m["Close"].resample("5min").last().dropna()

    # EMA200 on 5m close
    ema_5m = df_5m.ewm(span=settings.EMA_HTF, adjust=False).mean()

    # Reindex back to 1m, forward fill
    ema_5m_on_1m = ema_5m.reindex(df_1m.index, method="ffill")
    return ema_5m_on_1m


def _calculate_macd_divergence(df: pd.DataFrame) -> pd.Series:
    """
    MACD Divergence: True when MACD direction differs from price direction.
    Bullish divergence: price falling but MACD rising.
    Bearish divergence: price rising but MACD falling.
    """
    price_dir = df["Close"].diff(3).apply(lambda x: 1 if x > 0 else -1)
    macd_dir = df["MACD_Hist"].diff(3).apply(lambda x: 1 if x > 0 else -1)
    return price_dir != macd_dir


def _generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Primary Signal: EMA20/EMA200 crossover
        +1 = EMA20 crosses above EMA200 (bullish)
        -1 = EMA20 crosses below EMA200 (bearish)
         0 = no signal

    Filtered Signal: only keep if price is on correct side of 5m EMA200
    """
    # EMA crossover detection
    above = df["EMA20"] > df["EMA200"]
    cross_up = above & ~above.shift(1).fillna(False)    # just crossed up
    cross_down = ~above & above.shift(1).fillna(True)   # just crossed down

    df["Signal"] = 0
    df.loc[cross_up, "Signal"] = 1
    df.loc[cross_down, "Signal"] = -1

    # HTF filter
    df["Signal_Filtered"] = 0
    long_ok = (df["Signal"] == 1) & (df["Close"] > df["ema_200_5m"])
    short_ok = (df["Signal"] == -1) & (df["Close"] < df["ema_200_5m"])
    df.loc[long_ok, "Signal_Filtered"] = 1
    df.loc[short_ok, "Signal_Filtered"] = -1

    return df


def label_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each filtered signal, determine the trade outcome (Win=1/Loss=0)
    using 1:2 Risk-Reward ratio and trailing stop logic.
    This is used during training only.
    """
    df = df.copy()
    df["Outcome_Filtered"] = np.nan

    signal_idx = df.index[df["Signal_Filtered"] != 0].tolist()

    for idx in signal_idx:
        i = df.index.get_loc(idx)
        direction = df["Signal_Filtered"].iloc[i]
        entry_price = df["Close"].iloc[i]

        # Determine SL from recent high/low
        lookback_slice = df.iloc[max(0, i - settings.SL_LOOKBACK): i]

        if direction == 1:  # Long
            sl_price = lookback_slice["Low"].min()
            risk = entry_price - sl_price
            if risk <= 0:
                continue
            tp_price = entry_price + (risk * settings.RR_RATIO)
            breakeven_target = entry_price + risk  # 1R profit → move SL to BE
        else:  # Short
            sl_price = lookback_slice["High"].max()
            risk = sl_price - entry_price
            if risk <= 0:
                continue
            tp_price = entry_price - (risk * settings.RR_RATIO)
            breakeven_target = entry_price - risk

        # Look forward to determine outcome
        future = df.iloc[i + 1: i + 1 + settings.MAX_BARS_LOOKFORWARD]
        outcome = _simulate_trade(
            direction, entry_price, sl_price, tp_price,
            breakeven_target, risk, future
        )
        df.at[idx, "Outcome_Filtered"] = outcome

    return df


def _simulate_trade(
    direction: int,
    entry: float,
    sl: float,
    tp: float,
    be_target: float,
    risk: float,
    future: pd.DataFrame,
) -> float:
    """Simulate a trade through future candles. Returns 1.0 (win) or 0.0 (loss)."""
    current_sl = sl
    reached_be = False

    for _, candle in future.iterrows():
        high = candle["High"]
        low = candle["Low"]

        if direction == 1:  # Long
            # Check SL hit
            if low <= current_sl:
                return 0.0
            # Check TP hit
            if high >= tp:
                return 1.0
            # Check breakeven activation
            if not reached_be and high >= be_target:
                current_sl = entry  # move SL to entry
                reached_be = True
        else:  # Short
            if high >= current_sl:
                return 0.0
            if low <= tp:
                return 1.0
            if not reached_be and low <= be_target:
                current_sl = entry
                reached_be = True

    # Trade still open after max_bars: check current price
    last_close = future["Close"].iloc[-1] if not future.empty else entry
    if direction == 1:
        unrealized_r = (last_close - entry) / risk
    else:
        unrealized_r = (entry - last_close) / risk

    return 1.0 if unrealized_r > 1.0 else 0.0


def get_live_features(df: pd.DataFrame) -> dict:
    """
    Extract the latest row's ML features from a fully calculated DataFrame.
    Returns a dict ready for model.predict_proba().
    """
    latest = df.iloc[-1]
    return {feat: latest.get(feat, 0.0) for feat in settings.ML_FEATURES}


def get_live_signal(df: pd.DataFrame) -> int:
    """Get the current filtered signal from the latest candle."""
    return int(df["Signal_Filtered"].iloc[-1]) if "Signal_Filtered" in df.columns else 0

