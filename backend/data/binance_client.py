"""
Binance public data client.
- REST: fetch historical klines (no API key required)
- WebSocket: subscribe to live 1-minute kline streams
"""

import asyncio
import json
import time
from typing import Callable, Dict, List, Optional
import aiohttp
import websockets
import pandas as pd
import numpy as np
from loguru import logger
from config import settings


# ─────────────────────────────────────────────────────────────────────────────
# REST CLIENT – Historical Data
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_klines(
    symbol: str,
    interval: str = "1m",
    limit: int = 1000,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> pd.DataFrame:
    """
    Fetch historical klines (OHLCV) from Binance REST API.
    Returns a clean pandas DataFrame indexed by datetime (UTC).
    """
    url = f"{settings.BINANCE_REST_URL}/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    if start_time:
        params["startTime"] = start_time
    if end_time:
        params["endTime"] = end_time

    max_retries = 5
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return _klines_to_df(data)
                    elif resp.status in (429, 418):
                        wait_time = (attempt + 1) * 10
                        logger.warning(f"[{symbol}] Binance rate limit ({resp.status}). Waiting {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                    else:
                        text = await resp.text()
                        logger.warning(f"[{symbol}] Binance REST status {resp.status}: {text}. Retrying in 2s...")
                        await asyncio.sleep(2)
        except Exception as e:
            wait_time = (attempt + 1) * 2
            logger.warning(f"[{symbol}] Connection error ({e}). Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)

    raise RuntimeError(f"[{symbol}] Max retries exceeded for fetching klines")


async def fetch_klines_full(
    symbol: str,
    interval: str = "1m",
    days: int = 90,
) -> pd.DataFrame:
    """
    Fetch multiple pages of klines to cover `days` of history.
    Binance returns max 1000 candles per request.
    """
    all_dfs: List[pd.DataFrame] = []
    end_time = int(time.time() * 1000)
    # ms per candle
    interval_ms = _interval_to_ms(interval)
    start_time = end_time - (days * 24 * 60 * 60 * 1000)

    logger.info(f"[{symbol}] Fetching {days}d of {interval} data...")

    current_start = start_time
    consecutive_errors = 0

    while current_start < end_time:
        batch_end = min(current_start + 1000 * interval_ms, end_time)
        try:
            df = await fetch_klines(symbol, interval, limit=1000,
                                    start_time=current_start, end_time=batch_end)
            if df.empty:
                break
            all_dfs.append(df)
            current_start = int(df.index[-1].timestamp() * 1000) + interval_ms
            consecutive_errors = 0
            await asyncio.sleep(0.05)  # rate limit courtesy
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"[{symbol}] Error fetching historical batch (consecutive: {consecutive_errors}): {e}")
            if consecutive_errors >= 3:
                logger.error(f"[{symbol}] Too many consecutive errors. Breaking fetch loop.")
                break
            await asyncio.sleep(3)

    if not all_dfs:
        return pd.DataFrame()

    result = pd.concat(all_dfs)
    result = result[~result.index.duplicated(keep="last")]
    result.sort_index(inplace=True)
    logger.success(f"[{symbol}] Fetched {len(result)} candles ({days}d {interval})")
    return result


def _klines_to_df(raw: list) -> pd.DataFrame:
    """Convert raw Binance kline list to a clean OHLCV DataFrame."""
    if not raw:
        return pd.DataFrame()

    cols = [
        "Open_Time", "Open", "High", "Low", "Close", "Volume",
        "Close_Time", "Quote_Volume", "Trades",
        "Taker_Buy_Base", "Taker_Buy_Quote", "Ignore"
    ]
    df = pd.DataFrame(raw, columns=cols)
    df["Open_Time"] = pd.to_datetime(df["Open_Time"], unit="ms", utc=True)
    df.set_index("Open_Time", inplace=True)

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = df[col].astype(float)

    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df.sort_index(inplace=True)
    return df


def _interval_to_ms(interval: str) -> int:
    """Convert interval string (e.g. '1m', '5m', '1h') to milliseconds."""
    unit = interval[-1]
    value = int(interval[:-1])
    multipliers = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}
    return value * multipliers.get(unit, 60_000)


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket CLIENT – Live Streaming
# ─────────────────────────────────────────────────────────────────────────────

class BinanceStreamManager:
    """
    Manages a single combined WebSocket stream for multiple symbols.
    Calls `on_kline_close` callback whenever a 1-minute candle closes.
    """

    def __init__(self, symbols: List[str], on_kline_close: Callable):
        self.symbols = [s.lower() for s in symbols]
        self.on_kline_close = on_kline_close
        self._running = False
        self._ws = None

    def _build_stream_url(self) -> str:
        """Build combined stream URL for up to 100 symbols."""
        streams = [f"{s}@kline_1m" for s in self.symbols]
        combined = "/".join(streams)
        return f"{settings.BINANCE_WS_URL}/stream?streams={combined}"

    async def start(self):
        """Start the WebSocket connection and listen forever."""
        self._running = True
        url = self._build_stream_url()
        logger.info(f"Connecting to Binance WS for {len(self.symbols)} symbols...")

        while self._running:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self._ws = ws
                    logger.success("[OK] Binance WebSocket connected")
                    async for message in ws:
                        await self._handle_message(message)
            except websockets.ConnectionClosed as e:
                logger.warning(f"WS connection closed: {e}. Reconnecting in 3s...")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"WS error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _handle_message(self, raw: str):
        """Parse incoming kline message and fire callback on candle close."""
        try:
            msg = json.loads(raw)
            data = msg.get("data", {})
            kline = data.get("k", {})

            if not kline:
                return

            is_closed = kline.get("x", False)  # True when candle is closed
            symbol = kline.get("s", "").upper()

            candle = {
                "symbol": symbol,
                "open_time": pd.Timestamp(kline["t"], unit="ms", tz="UTC"),
                "open": float(kline["o"]),
                "high": float(kline["h"]),
                "low": float(kline["l"]),
                "close": float(kline["c"]),
                "volume": float(kline["v"]),
                "is_closed": is_closed,
            }

            # Always fire for live price updates; strategy checks is_closed
            await self.on_kline_close(candle)

        except Exception as e:
            logger.error(f"Error parsing WS message: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY: Get exchange info for a symbol
# ─────────────────────────────────────────────────────────────────────────────

async def get_ticker_price(symbol: str) -> float:
    """Fetch current price for a symbol."""
    url = f"{settings.BINANCE_REST_URL}/api/v3/ticker/price"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params={"symbol": symbol.upper()}) as resp:
            data = await resp.json()
            return float(data["price"])


async def get_24h_stats(symbol: str) -> dict:
    """Fetch 24h stats for a symbol."""
    url = f"{settings.BINANCE_REST_URL}/api/v3/ticker/24hr"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params={"symbol": symbol.upper()}) as resp:
            return await resp.json()

