"""
Binance FUTURES public data client.
Uses Binance Perpetual Futures (USDM) endpoints:
- REST:  https://fapi.binance.com/fapi/v1/
- WS:    wss://fstream.binance.com/ws
No API key needed for public market data (klines, ticker, price).
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


# ── Futures REST endpoints (with fallback) ───────────────────────────────────
FAPI_ENDPOINTS = [
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
]

# ── Futures WebSocket endpoints ───────────────────────────────────────────────
FSTREAM_ENDPOINTS = [
    "wss://fstream.binance.com/ws",
    "wss://fstream1.binance.com/ws",
]


async def fetch_klines(
    symbol: str,
    interval: str = "1m",
    limit: int = 500,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> pd.DataFrame:
    """
    Fetch historical klines from Binance Futures REST API.
    Uses /fapi/v1/klines endpoint with 1.5s timeout.
    """
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    if start_time:
        params["startTime"] = start_time
    if end_time:
        params["endTime"] = end_time

    for base_url in FAPI_ENDPOINTS:
        url = f"{base_url}/fapi/v1/klines"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=1.5)) as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and isinstance(data, list):
                            return _klines_to_df(data)
        except Exception:
            continue

    return pd.DataFrame()


async def fetch_klines_full(
    symbol: str,
    interval: str = "1m",
    days: int = 2,
) -> pd.DataFrame:
    """
    Fetch multiple pages of futures klines to cover `days` of history.
    """
    all_dfs: List[pd.DataFrame] = []
    end_time = int(time.time() * 1000)
    interval_ms = _interval_to_ms(interval)
    start_time = end_time - (days * 24 * 60 * 60 * 1000)

    logger.info(f"[{symbol}] Fetching {days}d of {interval} futures data...")
    current_start = start_time

    for _ in range(15):
        if current_start >= end_time:
            break
        batch_end = min(current_start + 1000 * interval_ms, end_time)
        df = await fetch_klines(
            symbol, interval, limit=1000,
            start_time=current_start, end_time=batch_end
        )
        if df.empty:
            break
        all_dfs.append(df)
        current_start = int(df.index[-1].timestamp() * 1000) + interval_ms
        await asyncio.sleep(0.05)

    if not all_dfs:
        return pd.DataFrame()

    result = pd.concat(all_dfs)
    result = result[~result.index.duplicated(keep="last")]
    result.sort_index(inplace=True)
    logger.success(f"[{symbol}] Fetched {len(result)} candles ({days}d {interval} futures)")
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

    return df[["Open", "High", "Low", "Close", "Volume"]]


def _interval_to_ms(interval: str) -> int:
    """Convert timeframe string to milliseconds."""
    units = {"m": 60, "h": 3600, "d": 86400}
    unit = interval[-1]
    val = int(interval[:-1])
    return val * units[unit] * 1000


# ─────────────────────────────────────────────────────────────────────────────
# WEBSOCKET CLIENT – Live Futures Stream
# ─────────────────────────────────────────────────────────────────────────────

class BinanceStreamManager:
    """
    Manages WebSocket connection to Binance FUTURES stream (fstream.binance.com).
    Subscribes in batches of 50 streams via JSON payload to avoid URI limits.
    Fires a callback on every closed kline event.
    """

    def __init__(self, symbols: List[str], on_kline_close: Callable):
        self.symbols = [s.lower() for s in symbols]
        self.on_kline_close = on_kline_close
        self._ws = None
        self._running = False

    async def start(self):
        self._running = True
        endpoint_idx = 0
        logger.info(f"Connecting to Binance Futures WS for {len(self.symbols)} symbols...")

        while self._running:
            url = FSTREAM_ENDPOINTS[endpoint_idx % len(FSTREAM_ENDPOINTS)]
            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                    max_size=10_000_000,
                ) as ws:
                    self._ws = ws
                    logger.success(f"[OK] Futures WebSocket connected: {url}")

                    # Subscribe in batches of 50 streams
                    all_streams = [f"{s}@kline_{settings.TIMEFRAME}" for s in self.symbols]
                    for i in range(0, len(all_streams), 50):
                        chunk = all_streams[i: i + 50]
                        await ws.send(json.dumps({
                            "method": "SUBSCRIBE",
                            "params": chunk,
                            "id": i + 1,
                        }))
                        await asyncio.sleep(0.05)

                    logger.info(f"Subscribed to {len(all_streams)} futures kline streams")

                    async for message in ws:
                        await self._handle_message(message)

            except websockets.ConnectionClosed as e:
                logger.warning(f"Futures WS closed: {e}. Reconnecting in 3s...")
                endpoint_idx += 1
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Futures WS error: {e}. Reconnecting in 5s...")
                endpoint_idx += 1
                await asyncio.sleep(5)

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _handle_message(self, raw: str):
        """Parse incoming kline message and fire callback."""
        try:
            msg = json.loads(raw)

            # Skip subscription ack messages
            if "result" in msg and "id" in msg:
                return

            # Futures WS sends kline directly (not nested under "data")
            data = msg.get("data", msg)
            kline = data.get("k", {})

            if not kline:
                return

            symbol = kline.get("s", "").upper()
            is_closed = kline.get("x", False)

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

            await self.on_kline_close(candle)

        except Exception as e:
            logger.error(f"Error parsing Futures WS message: {e}")


# ── Price Ticker (Futures) ────────────────────────────────────────────────────
_bulk_prices_cache: Dict[str, float] = {}
TICKER_REST_ENDPOINTS = [
    "https://fapi.binance.com/fapi/v1/ticker/price",
    "https://data-api.binance.vision/api/v3/ticker/price",
    "https://api.binance.com/api/v3/ticker/price",
]


async def fetch_all_ticker_prices() -> Dict[str, float]:
    """Fetch live ticker prices with automatic CDN fallback."""
    global _bulk_prices_cache
    for url in TICKER_REST_ENDPOINTS:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4)) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list) and len(data) > 10:
                            res = {}
                            for item in data:
                                sym = item.get("symbol", "")
                                if sym.endswith("USDT"):
                                    res[sym] = float(item["price"])
                            _bulk_prices_cache = res
                            logger.info(f"[Prices] Loaded {len(res)} prices from {url}")
                            return res
        except Exception:
            continue
    return _bulk_prices_cache


async def get_ticker_price(symbol: str) -> float:
    """Fetch current price for a symbol using bulk cache, fallback REST, or defaults."""
    global _bulk_prices_cache
    sym = symbol.upper()
    if sym in _bulk_prices_cache:
        return _bulk_prices_cache[sym]

    for base_url in TICKER_REST_ENDPOINTS:
        url = base_url if "/ticker/price" in base_url else f"{base_url}/api/v3/ticker/price"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as session:
                async with session.get(url, params={"symbol": sym}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, dict) and "price" in data:
                            price = float(data["price"])
                            _bulk_prices_cache[sym] = price
                            return price
        except Exception:
            continue

    defaults = {
        "BTCUSDT": 64000.0, "ETHUSDT": 2450.0, "SOLUSDT": 140.0,
        "BNBUSDT": 560.0, "XRPUSDT": 0.58, "DOGEUSDT": 0.11,
        "ADAUSDT": 0.36, "AVAXUSDT": 26.0, "DOTUSDT": 4.3,
        "SUIUSDT": 0.82, "NEARUSDT": 4.1, "LINKUSDT": 11.2,
    }
    return defaults.get(sym, 10.0)
